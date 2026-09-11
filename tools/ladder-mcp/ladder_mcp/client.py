"""HTTP-клиент Ladder API для MCP-сервера.

Вход — email/пароль (`POST /api/auth/login`), дальше HttpOnly cookie-сессия внутри httpx.AsyncClient.
Сессия могла протухнуть или быть отозвана (смена пароля) — на 401 один повторный вход.
Ошибки API превращаются в LadderError(status, detail) с читаемым detail (включая ошибки валидации 422).
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

import httpx


class LadderError(Exception):
    """Ответ API с кодом >= 400 (или неудачный вход)."""

    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


def seg(value: str) -> str:
    """Сегмент пути: id направления, карточки, топика — экранируем целиком (топик может содержать что угодно)."""
    return quote(value, safe="")


def _detail(resp: httpx.Response) -> str:
    try:
        detail = resp.json().get("detail")
    except (ValueError, AttributeError):
        return resp.text[:300] or resp.reason_phrase
    if isinstance(detail, list):  # ошибки валидации pydantic/FastAPI
        parts = []
        for err in detail:
            loc = ".".join(str(x) for x in (err.get("loc") or [])[1:])
            parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        return "; ".join(parts)
    return str(detail)


class LadderClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 30.0,
    ):
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), transport=transport, timeout=timeout)
        self._email = email
        self._password = password
        self._authed = False

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _login(self) -> None:
        resp = await self._http.post("/api/auth/login", json={"email": self._email, "password": self._password})
        if resp.status_code != 200:
            self._authed = False
            raise LadderError(resp.status_code, "login failed: check LADDER_EMAIL / LADDER_PASSWORD")
        self._authed = True

    async def request(
        self, method: str, path: str, *, json: Any = None, params: Optional[dict] = None
    ) -> Any:
        if not self._authed:
            await self._login()
        query = {k: v for k, v in (params or {}).items() if v is not None}
        resp = await self._http.request(method, path, json=json, params=query)
        if resp.status_code == 401:  # сессия протухла или отозвана — один повторный вход
            await self._login()
            resp = await self._http.request(method, path, json=json, params=query)
        if resp.status_code >= 400:
            raise LadderError(resp.status_code, _detail(resp))
        return resp.json()
