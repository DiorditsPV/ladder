"""FastAPI-приложение Ladder: направления, доска вопросов и чек-лист разбора.

Запуск:  uvicorn app.main:app --reload  (из каталога backend/)
Конфиг через переменные окружения:
    INTERVIEW_CONTENT_DIR  — каталог с *.md/*.json (по умолч. ../content)
    INTERVIEW_DB_PATH      — путь к SQLite (по умолч. ./interview.db)
    INTERVIEW_FRONTEND_DIR — каталог собранного фронта (по умолч. ../frontend/dist)
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .auth import (
    COOKIE_NAME,
    current_user,
    hash_password,
    optional_user,
    require_member,
    require_owner,
    verify_password,
)
from .db import SESSION_MAX_AGE, Database
from .importer import parse_file, validate_against_pool
from .models import GraphResponse, Kind, Node
from .pools import (
    DEFAULT_LEVELS,
    PoolCfg,
    PoolConfigError,
    blocks_to_json,
    default_pool_id,
    levels_to_json,
    load_pools,
    normalize_blocks,
    normalize_levels,
    parse_blocks,
    parse_levels,
    pool_from_row,
    slug_from_label,
)
from .seed import seed_owner_if_empty
from .sync import UnknownPoolError, sync_pools
from .tags import CONCEPT_TAGS
from .tenancy import resolve_tenant

log = logging.getLogger("ladder")

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                              # ladder/
CONTENT_DIR = Path(os.environ.get("INTERVIEW_CONTENT_DIR", PROJECT_DIR / "content"))
DB_PATH = Path(os.environ.get("INTERVIEW_DB_PATH", BASE_DIR / "interview.db"))
FRONTEND_DIR = Path(os.environ.get("INTERVIEW_FRONTEND_DIR", PROJECT_DIR / "frontend" / "dist"))
# Креды первого owner-аккаунта для тенанта default (сид при первом старте, см. ниже).
OWNER_EMAIL = os.environ.get("INTERVIEW_OWNER_EMAIL", "owner@interview.local")


def _resolve_owner_password() -> tuple[str, bool]:
    """Пароль owner-аккаунта: из env или случайный.

    Если `INTERVIEW_OWNER_PASSWORD` не задан — НЕ используем известный дефолт (иначе
    публичный логин-барьер бутафорский), а генерим случайный и сигналим, что он
    сгенерирован (залогируется один раз при сиде). Возвращает (пароль, сгенерирован_ли).
    """
    env = os.environ.get("INTERVIEW_OWNER_PASSWORD")
    if env:
        return env, False
    return secrets.token_urlsafe(24), True


OWNER_PASSWORD, _OWNER_PASSWORD_GENERATED = _resolve_owner_password()

app = FastAPI(title="Ladder", version="0.1.0")

# CORS для dev-режима Vite (localhost:5173). allow_credentials=True — фронт шлёт session-cookie
# (credentials:'include'); со списком явных origin это валидно (с "*" — нет).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database(DB_PATH)
app.state.db = db  # auth-зависимости берут db отсюда (request.app.state.db)

# Пулы направлений: content/<pool>/pool.yaml — источник конфига и seed-нод (источник правды
# в рантайме — БД, см. _pools: направления создаются/правятся/удаляются из UI). На старте —
# та же синхронизация, что и по POST /api/pools/sync: новые направления создаются, существующие
# обновляются конфигом без каскадных удалений, seed-ноды upsert-ятся, user-ноды не трогаются.
_CONTENT_POOLS: Dict[str, PoolCfg] = load_pools(CONTENT_DIR)
if not _CONTENT_POOLS:
    log.warning("no pools found in %s — /api/pools will be empty until a pool is created", CONTENT_DIR)
# Засев: только новое из файлов (пресеты на свежей установке); накопленное в БД не перезаписывается и не прячется.
_sync = sync_pools(db, resolve_tenant(), CONTENT_DIR)
log.info("content seed: created=%s extended=%s new_nodes=%d skipped=%d errors=%d",
         _sync["created"], _sync["updated"], _sync["nodes_upserted"], _sync["skipped"], len(_sync["errors"]))
if _sync["errors"]:
    log.warning("content import errors: %s", _sync["errors"])
# Сид первого owner-аккаунта для тенанта default — иначе после включения auth некому войти.
if seed_owner_if_empty(db, resolve_tenant(), OWNER_EMAIL, OWNER_PASSWORD):
    log.info("seeded owner account %s", OWNER_EMAIL)
    if _OWNER_PASSWORD_GENERATED:
        # Пароль не задан через env — показываем сгенерированный ОДИН раз, иначе войти нельзя.
        log.warning(
            "INTERVIEW_OWNER_PASSWORD не задан — сгенерирован случайный пароль owner-аккаунта "
            "%s: %s  (задайте INTERVIEW_OWNER_PASSWORD, чтобы управлять им)",
            OWNER_EMAIL,
            OWNER_PASSWORD,
        )


# ---------- request models ----------
class LoginIn(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserCreate(BaseModel):
    """Аккаунт от owner'а: без password сервер генерирует одноразовый и отдаёт его один раз."""

    email: str = Field(min_length=3)
    password: Optional[str] = Field(default=None, min_length=6)
    role: str = Field(default="viewer", pattern="^(owner|member|viewer)$")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ImportFile(BaseModel):
    filename: str = Field(min_length=1)
    content: str
    pool: Optional[str] = None


# Slug: id направлений, карточек и теги — латиница в нижнем регистре, цифры и дефис.
_SLUG = r"^[a-z0-9][a-z0-9-]*$"


class NodeCreate(BaseModel):
    """Создание карточки (UI, MCP): id — явный (slug, свободный) или генерится сервером из topic/title."""

    model_config = ConfigDict(populate_by_name=True)

    pool: Optional[str] = None
    id: Optional[str] = Field(default=None, pattern=_SLUG, max_length=120)
    block: str = Field(min_length=1)
    subblock: Optional[str] = None
    topic: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    kind: Kind = "question"
    title: Optional[str] = None
    question: str = Field(min_length=1)
    answer: str = ""
    tags: List[str] = Field(default_factory=list)
    weight: int = Field(default=1, ge=0)
    starter_code: Optional[str] = Field(default=None, alias="starterCode")
    rubric: List[str] = Field(default_factory=list)


class NodeUpdate(BaseModel):
    """Правка карточки — только переданные поля (None = не менять). Перенос — `pool`/`block`/`subblock`/`difficulty`.
    Пустая строка в `subblock`, `title`, `starterCode` снимает значение."""

    model_config = ConfigDict(populate_by_name=True)

    pool: Optional[str] = None
    block: Optional[str] = None
    subblock: Optional[str] = None
    topic: Optional[str] = None
    title: Optional[str] = None
    difficulty: Optional[str] = None
    kind: Optional[Kind] = None
    weight: Optional[int] = Field(default=None, ge=0)
    question: Optional[str] = None
    answer: Optional[str] = None
    starter_code: Optional[str] = Field(default=None, alias="starterCode")
    rubric: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class TopicRename(BaseModel):
    """Новый топик для всех карточек направления (или только колонки `block`)."""

    topic: str = Field(min_length=1)
    block: Optional[str] = None


class PoolCreate(BaseModel):
    """Новое направление: из пресета (копируются колонки и вопросы) ИЛИ со своими колонками."""

    id: Optional[str] = Field(default=None, pattern=_SLUG, max_length=80)  # явный id; без него — из названия
    label: str = Field(min_length=1)
    description: str = ""
    preset: Optional[str] = None  # id существующего направления
    blocks: Optional[List[dict]] = None  # [{label, color, subblocks?: [{label}]}] — см. pools.normalize_blocks
    levels: Optional[List[dict]] = None  # [{label}] — см. pools.normalize_levels; без preset и без levels → DEFAULT_LEVELS


class PoolUpdate(BaseModel):
    """Правка направления: название, описание, колонки (id новых генерятся, вопросы удалённых колонок уходят)."""

    label: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    blocks: Optional[List[dict]] = None
    levels: Optional[List[dict]] = None


# ---------- auth (login / logout / me) ----------
def _public_user(user: dict) -> dict:
    """Поля пользователя наружу — без password_hash."""
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    """Проверить email+пароль, выдать server-side сессию в HttpOnly-cookie."""
    tenant = resolve_tenant(request)  # без сессии → default (single-workspace)
    user = db.get_user_by_email(tenant, body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = db.create_auth_session(tenant, user["id"])
    # Без Secure: сервис локальный (http) — Secure-cookie не пересылалась бы по http.
    # max_age = TTL сессии (см. SESSION_MAX_AGE): cookie протухает синхронно с server-side.
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", path="/", max_age=SESSION_MAX_AGE
    )
    return _public_user(user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.delete_auth_session(token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request, user: dict = Depends(current_user)) -> dict:
    return _public_user(user)


@app.post("/api/auth/password")
def change_password(body: PasswordChange, request: Request, user: dict = Depends(current_user)) -> dict:
    """Сменить свой пароль. Неверный текущий — 403 (не 401: фронт на 401 перезагружает страницу).
    Остальные сессии пользователя отзываются, текущая остаётся."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=403, detail="wrong current password")
    db.update_password(user["tenant_id"], user["id"], hash_password(body.new_password))
    db.delete_user_sessions(user["tenant_id"], user["id"], except_token=request.cookies.get(COOKIE_NAME))
    return {"ok": True}


# ---------- users (управление пользователями — owner) ----------
def _one_time_password() -> str:
    return secrets.token_urlsafe(9)  # 12 символов; показывается владельцу один раз


@app.get("/api/users")
def list_users(request: Request, _owner: dict = Depends(require_owner)) -> list:
    return db.list_users(resolve_tenant(request))


@app.post("/api/users")
def create_user(body: UserCreate, request: Request, _owner: dict = Depends(require_owner)) -> dict:
    """Завести пользователя в тенанте owner'а (роль по умолчанию viewer). 409 при дубликате email.

    Без password сервер генерирует одноразовый пароль и отдаёт его в ответе один раз (поле password).
    """
    import sqlite3

    tenant = resolve_tenant(request)
    email = body.email.strip()
    if db.get_user_by_email(tenant, email) is not None:
        raise HTTPException(status_code=409, detail="email already exists")
    password = body.password or _one_time_password()
    try:
        user = db.create_user(tenant, email, hash_password(password), body.role)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="email already exists")
    out = _public_user(user)
    if body.password is None:
        out["password"] = password
    return out


@app.post("/api/users/{user_id}/password")
def reset_user_password(user_id: str, request: Request, owner: dict = Depends(require_owner)) -> dict:
    """Новый одноразовый пароль пользователю; его сессии отзываются. Свой — через /api/auth/password."""
    tenant = resolve_tenant(request)
    if user_id == owner["id"]:
        raise HTTPException(status_code=400, detail="use /api/auth/password for your own account")
    if db.get_user_by_id(tenant, user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    password = _one_time_password()
    db.update_password(tenant, user_id, hash_password(password))
    db.delete_user_sessions(tenant, user_id)
    return {"id": user_id, "password": password}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, request: Request, owner: dict = Depends(require_owner)) -> dict:
    """Удалить аккаунт с его сессиями и чек-листом. Себя удалить нельзя (400)."""
    if user_id == owner["id"]:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    if not db.delete_user(resolve_tenant(request), user_id):
        raise HTTPException(status_code=404, detail="user not found")
    return {"deleted": user_id}


# ---------- graph & content ----------
# Поля, которые понимает models.Node (остальные — tenant_id/source/hidden/таймстемпы —
# живут только в БД-слое; Node их не принимает из-за extra="forbid").
_NODE_FIELDS = set(Node.model_fields)


def _pools(request: Request) -> Dict[str, PoolCfg]:
    """Направления тенанта из БД (источник правды; content/ — сид), в порядке создания."""
    return {row["id"]: pool_from_row(row) for row in db.list_pools(resolve_tenant(request))}


def _pool_or_404(request: Request, pool_id: Optional[str]) -> PoolCfg:
    """Пул по id; без id — пул по умолчанию (data-engineer или первый по алфавиту)."""
    pools = _pools(request)
    pid = pool_id or default_pool_id(pools)
    if pid is None or pid not in pools:
        raise HTTPException(status_code=404, detail=f"pool '{pool_id}' not found")
    return pools[pid]


def _pool_out(request: Request, p: PoolCfg, user: Optional[dict]) -> dict:
    """Форма направления для API: конфиг + счётчик вопросов + сводка чек-листа (только у вошедшего)."""
    tenant = resolve_tenant(request)
    out = {**p.to_dict(), "counts": {"nodes": db.count_nodes(tenant, pool=p.id)}}
    if user is not None:
        out["progress"] = db.progress_summary(tenant, user["id"], p.id)
    return out


def _db_nodes(request: Request, pool: PoolCfg, include_hidden: bool = False) -> List[Node]:
    """Ноды пула из БД (источник правды) как объекты Node для текущего тенанта.

    По умолчанию скрытые (sync — пропавшая из файлов seed-нода, или tombstone удалённой из UI)
    на доску не попадают; include_hidden=True оставлен для служебных вызовов и тестов.
    """
    tenant = resolve_tenant(request)
    return [
        Node.model_validate({k: v for k, v in row.items() if k in _NODE_FIELDS})
        for row in db.list_nodes(tenant, pool=pool.id, include_hidden=include_hidden)
    ]


def _node_out(row: dict) -> dict:
    """Карточка для API: поля Node (starterCode — по alias) + служебные hidden/source из БД."""
    node = Node.model_validate({k: v for k, v in row.items() if k in _NODE_FIELDS})
    return {**node.model_dump(by_alias=True), "hidden": bool(row.get("hidden")), "source": row.get("source")}


_TAG_RE = re.compile(_SLUG)
MAX_TAGS = 5


def _tags_or_422(tags: List[str]) -> List[str]:
    """Теги карточки: slug в нижнем регистре, дубли схлопываются, не больше MAX_TAGS. Словарь не навязываем —
    у темы вне DE могут быть свои теги (pool.tags); список концептов отдаёт GET /api/tags."""
    out: List[str] = []
    for raw in tags:
        # «Data Modeling» / «data_modeling» из поля UI → data-modeling; не-латиница и символы — 422.
        tag = re.sub(r"[\s_]+", "-", (raw or "").strip().lower())
        if not _TAG_RE.match(tag):
            raise HTTPException(status_code=422, detail=f"tag '{raw}' must be a lowercase slug [a-z0-9-]")
        if tag not in out:
            out.append(tag)
    if len(out) > MAX_TAGS:
        raise HTTPException(status_code=422, detail=f"at most {MAX_TAGS} tags per card")
    return out


@app.get("/api/pools")
def get_pools(request: Request, user: Optional[dict] = Depends(optional_user)) -> list:
    pools = _pools(request).values()
    if user is None:  # демо: тенант default, только направления с demo=true
        return [_pool_out(request, p, None) for p in pools if p.demo]
    return [_pool_out(request, p, user) for p in pools]


@app.get("/api/pools/{pool_id}")
def get_pool(pool_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    """Одно направление: структура (колонки, под-колонки, уровни), счётчик вопросов, сводка чек-листа."""
    return _pool_out(request, _pool_or_404(request, pool_id), user)


@app.get("/api/pools/{pool_id}/topics")
def list_topics(
    pool_id: str,
    request: Request,
    block: Optional[str] = None,
    include_hidden: bool = False,
    _user: dict = Depends(current_user),
) -> list:
    """Топики направления: `[{topic, block, count}]` в порядке колонок, внутри колонки — по алфавиту."""
    pool = _pool_or_404(request, pool_id)
    rows = db.list_nodes(resolve_tenant(request), pool=pool.id, include_hidden=include_hidden)
    counts = Counter((r["block"], r["topic"]) for r in rows if block is None or r["block"] == block)
    order = {b.id: i for i, b in enumerate(pool.blocks)}
    ranked = sorted(counts.items(), key=lambda kv: (order.get(kv[0][0], len(order)), kv[0][0], kv[0][1]))
    return [{"topic": topic, "block": blk, "count": n} for (blk, topic), n in ranked]


@app.put("/api/pools/{pool_id}/topics/{topic}")
def rename_topic(
    pool_id: str, topic: str, body: TopicRename, request: Request, _user: dict = Depends(require_member)
) -> dict:
    """Переименовать топик у всех карточек направления (или только колонки `block`). 404 — таких карточек нет."""
    pool = _pool_or_404(request, pool_id)
    new = body.topic.strip()
    if not new:
        raise HTTPException(status_code=422, detail="topic must not be blank")
    renamed = db.rename_topic(resolve_tenant(request), pool.id, topic, new, block=body.block)
    if renamed == 0:
        raise HTTPException(status_code=404, detail=f"no cards with topic '{topic}' in pool '{pool.id}'")
    return {"renamed": renamed, "topic": new}


@app.delete("/api/pools/{pool_id}/topics/{topic}")
def delete_topic(
    pool_id: str, topic: str, request: Request, block: Optional[str] = None, _user: dict = Depends(require_member)
) -> dict:
    """Удалить карточки топика (seed прячется, пользовательские удаляются — как DELETE /api/nodes/{id})."""
    pool = _pool_or_404(request, pool_id)
    tenant = resolve_tenant(request)
    rows = [
        r for r in db.list_nodes(tenant, pool=pool.id, include_hidden=False)
        if r["topic"] == topic and (block is None or r["block"] == block)
    ]
    if not rows:
        raise HTTPException(status_code=404, detail=f"no cards with topic '{topic}' in pool '{pool.id}'")
    for r in rows:
        _remove_node(tenant, r)
    return {"deleted": [r["id"] for r in rows], "count": len(rows)}


@app.get("/api/tags")
def list_tags(request: Request, pool: Optional[str] = None, _user: dict = Depends(current_user)) -> dict:
    """Словарь сквозных концептов и теги, уже использованные в направлении (по частоте)."""
    used: Counter = Counter()
    if pool:
        p = _pool_or_404(request, pool)
        for r in db.list_nodes(resolve_tenant(request), pool=p.id, include_hidden=False):
            used.update(r.get("tags") or [])
    return {"concepts": list(CONCEPT_TAGS), "used": [{"tag": t, "count": n} for t, n in used.most_common()]}


@app.post("/api/pools")
def create_pool(body: PoolCreate, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Новое направление из пресета: колонки и все вопросы пресета копируются (id с префиксом).

    Id — транслитерация названия; занятый (в том числе tombstone удалённого) — с суффиксом -2, -3…
    """
    import sqlite3

    tenant = resolve_tenant(request)
    label = body.label.strip()
    if not label:
        # Field(min_length=1) пропускает строку из пробелов — иначе родится пул с пустым названием и id 'pool'.
        raise HTTPException(status_code=422, detail="label must not be blank")
    # Ровно один источник колонок: пресет (копируются колонки и вопросы) или свои колонки (без вопросов).
    # Пустой preset считается отсутствующим — иначе _pool_or_404("") подставил бы пул по умолчанию.
    preset_id = (body.preset or "").strip()
    if bool(preset_id) == (body.blocks is not None):
        raise HTTPException(status_code=422, detail="pass exactly one of 'preset' or 'blocks'")
    if preset_id:
        preset = _pool_or_404(request, preset_id)
        blocks = json.loads(blocks_to_json(preset.blocks))
        levels = json.loads(levels_to_json(preset.levels))
        copy_from: Optional[str] = preset.id
    else:
        blocks = _blocks_or_422(body.blocks, ())
        levels = _levels_or_422(body.levels, ()) if body.levels is not None else json.loads(levels_to_json(DEFAULT_LEVELS))
        copy_from = None
    if body.id:
        # Явный id (MCP, скрипты): занятый — в том числе tombstone удалённого направления — 409, без суффиксов.
        if db.get_pool(tenant, body.id) is not None:
            raise HTTPException(status_code=409, detail=f"pool id '{body.id}' is already taken")
        pid = body.id
    else:
        base = slug_from_label(label)
        pid, n = base, 2
        while db.get_pool(tenant, pid) is not None:
            pid, n = f"{base}-{n}", n + 1
    try:
        row = db.create_pool(
            tenant, pid, label, body.description.strip(), blocks, copy_from=copy_from, levels=levels
        )
    except sqlite3.IntegrityError as exc:
        # id копии ноды (<pool>-<id>) занят чужой нодой — транзакция откатилась, пул не создан.
        raise HTTPException(status_code=409, detail=f"node id collision while copying preset: {exc}")
    return _pool_out(request, pool_from_row(row), _user)


def _blocks_or_422(raw: list, existing: tuple) -> list:
    """Колонки из UI: достроить id/вес (normalize_blocks), проверить как pool.yaml (parse_blocks) → список dict."""
    try:
        return json.loads(blocks_to_json(parse_blocks(normalize_blocks(raw, existing))))
    except PoolConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _levels_or_422(raw: list, existing: tuple) -> list:
    """Уровни из UI: достроить id (normalize_levels), проверить как pool.yaml (parse_levels) → список dict."""
    try:
        return json.loads(levels_to_json(parse_levels(normalize_levels(raw, existing))))
    except PoolConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _difficulty_or_422(pool: PoolCfg, difficulty: str) -> str:
    if difficulty not in pool.level_ids:
        raise HTTPException(
            status_code=422,
            detail=f"difficulty '{difficulty}' is not declared in pool '{pool.id}' (allowed: {', '.join(l.id for l in pool.levels)})",
        )
    return difficulty


@app.put("/api/pools/{pool_id}")
def update_pool(
    pool_id: str, body: PoolUpdate, request: Request, _user: dict = Depends(require_member)
) -> dict:
    fields = {k: v.strip() for k, v in body.model_dump(exclude_none=True).items() if isinstance(v, str)}
    if "label" in fields and not fields["label"]:
        raise HTTPException(status_code=422, detail="label must not be blank")
    if body.blocks is not None:
        # Колонки — динамические данные направления: новые получают id из названия, вопросы
        # удалённых колонок удаляются, удалённых под-колонок — остаются без под-колонки (см. db.update_pool).
        fields["blocks"] = _blocks_or_422(body.blocks, _pool_or_404(request, pool_id).blocks)
    if body.levels is not None:
        fields["levels"] = _levels_or_422(body.levels, _pool_or_404(request, pool_id).levels)
    row = db.update_pool(resolve_tenant(request), pool_id, fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"pool '{pool_id}' not found")
    return _pool_out(request, pool_from_row(row), _user)


@app.delete("/api/pools/{pool_id}")
def delete_pool(pool_id: str, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Удалить направление: вопросы удаляются, id остаётся занятым (tombstone)."""
    removed = db.delete_pool(resolve_tenant(request), pool_id)
    if removed is None:
        raise HTTPException(status_code=404, detail=f"pool '{pool_id}' not found")
    return {"deleted": pool_id, "nodes_removed": removed}


@app.post("/api/pools/sync")
def sync_content(
    request: Request,
    pool: Optional[str] = None,
    update: bool = False,
    dry_run: bool = False,
    _owner: dict = Depends(require_owner),
) -> dict:
    """content/ → БД. По умолчанию засев: новые направления и карточки, id которых нет; существующее не трогается.
    update=true — явное обновление из файлов (конфиг из pool.yaml, seed-карточки, скрытие пропавших): лучше с
    pool=<id> и сначала dry_run=true. dry_run — отчёт по прогону на копии БД, живая БД не меняется."""
    try:
        return sync_pools(db, resolve_tenant(request), CONTENT_DIR, update=update, only=pool, dry_run=dry_run)
    except UnknownPoolError:
        raise HTTPException(status_code=404, detail=f"pool '{pool}' has no directory in content/")


@app.get("/api/graph", response_model=GraphResponse)
def get_graph(
    request: Request,
    pool: Optional[str] = None,
    include_hidden: bool = False,
    user: Optional[dict] = Depends(optional_user),
) -> GraphResponse:
    # Вопросы читаются из БД (а не с диска) — рантайм-правки переживают деплой.
    if user is None:
        # Демо: без сессии — только направление с demo=true, без скрытых карточек; иначе (и без ?pool) 401.
        demo_pool = _pools(request).get(pool or "")
        if demo_pool is None or not demo_pool.demo:
            raise HTTPException(status_code=401, detail="not authenticated")
        return GraphResponse(nodes=_db_nodes(request, demo_pool), errors=[])
    return GraphResponse(
        nodes=_db_nodes(request, _pool_or_404(request, pool), include_hidden=include_hidden), errors=[]
    )


@app.post("/api/import")
def import_file(body: ImportFile, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Загрузить .md/.json: распарсить тем же импортёром, валидные новые ноды сохранить в БД.

    Пишем в БД (source='user'), а не на диск content/ — иначе деплой (rsync --delete)
    затёр бы загруженные вопросы. БД переживает деплой (INTERVIEW_DB_PATH).
    """
    name = Path(body.filename).name
    ext = Path(name).suffix.lower()
    if ext not in {".md", ".json"}:
        raise HTTPException(status_code=400, detail="only .md or .json files are supported")

    # Парсим во временной директории, сохраняя ОРИГИНАЛЬНОЕ имя: id-less md берёт id из stem.
    from .importer import _fmt_error  # локально — внутренний хелпер форматирования ошибок

    tenant = resolve_tenant(request)
    pool = _pool_or_404(request, body.pool)
    added: List[dict] = []
    errors: List[dict] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / name
        tmp.write_text(body.content, encoding="utf-8")
        try:
            nodes = parse_file(tmp, pool.id)
        except Exception as exc:  # noqa: BLE001 — любую ошибку парсинга показываем пользователю
            return {"added": [], "errors": [{"file": name, "error": _fmt_error(exc)}]}

    for node in nodes:
        try:
            validate_against_pool(node, pool)
        except ValueError as exc:
            errors.append({"file": name, "error": str(exc)})
            continue
        if db.get_node(tenant, node.id) is not None:
            errors.append({"file": name, "error": f"duplicate id '{node.id}' (already in bank)"})
            continue
        saved = db.upsert_node(tenant, node.model_dump(), source="user")
        added.append({
            "id": saved["id"],
            "block": saved["block"],
            "title": saved.get("title") or "",
        })
    return {"added": added, "errors": errors}


# ---------- node CRUD (банк вопросов в БД) ----------
# Источник правды для вопросов — БД (см. db.py/seed.py). CRUD пишет в БД через DAL,
# а НЕ в content/*.md: иначе рантайм-правки затёр бы деплой (rsync --delete content/).
def _slugify(s: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")
    return slug or "q"


def _unique_node_id(tenant: str, base: str) -> str:
    """Сгенерировать свободный id вида `<base>-NN`, уникальный среди нод тенанта."""
    taken = {n["id"] for n in db.list_nodes(tenant)}
    n = 1
    while f"{base}-{n:02d}" in taken:
        n += 1
    return f"{base}-{n:02d}"


@app.get("/api/nodes")
def list_nodes(
    request: Request,
    pool: str,
    block: Optional[str] = None,
    subblock: Optional[str] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    tag: Optional[str] = None,
    kind: Optional[Kind] = None,
    q: Optional[str] = None,
    include_hidden: bool = False,
    _user: dict = Depends(current_user),
) -> list:
    """Карточки направления с фильтрами (все поля, как GET /api/nodes/{id}). `q` — подстрока в заголовке,
    вопросе или ответе без учёта регистра. Скрытые (tombstone/sync) — только с include_hidden=true."""
    p = _pool_or_404(request, pool)
    needle = (q or "").strip().lower()
    out = []
    for r in db.list_nodes(resolve_tenant(request), pool=p.id, include_hidden=include_hidden):
        if block is not None and r["block"] != block:
            continue
        if subblock is not None and r.get("subblock") != subblock:
            continue
        if difficulty is not None and r["difficulty"] != difficulty:
            continue
        if topic is not None and r["topic"] != topic:
            continue
        if tag is not None and tag not in (r.get("tags") or []):
            continue
        if kind is not None and r["kind"] != kind:
            continue
        if needle and needle not in " ".join(str(r.get(f) or "") for f in ("title", "question", "answer")).lower():
            continue
        out.append(_node_out(r))
    return out


@app.get("/api/nodes/{node_id}")
def get_node(node_id: str, request: Request, _user: dict = Depends(current_user)) -> dict:
    """Одна карточка со всеми полями, в том числе скрытая (поле hidden)."""
    row = db.get_node(resolve_tenant(request), node_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    return _node_out(row)


@app.post("/api/nodes")
def add_node(body: NodeCreate, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Создать карточку в направлении (БД, source='user'). id — явный (409, если занят) или из topic/title.
    Ответ — вся карточка (как GET /api/nodes/{id})."""
    tenant = resolve_tenant(request)
    pool = _pool_or_404(request, body.pool)
    _difficulty_or_422(pool, body.difficulty)
    tags = _tags_or_422(body.tags)
    if body.id:
        if db.get_node(tenant, body.id) is not None:
            raise HTTPException(status_code=409, detail=f"node id '{body.id}' already exists")
        node_id = body.id
    else:
        node_id = _unique_node_id(tenant, _slugify(body.topic or body.title or body.block))
    data = body.model_dump(exclude={"pool", "id"})
    data.update(pool=pool.id, id=node_id, tags=tags, subblock=body.subblock or None)
    node = Node.model_validate(data)
    try:
        validate_against_pool(node, pool)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # model_dump() без alias: DAL читает starter_code, а не starterCode.
    saved = db.upsert_node(tenant, node.model_dump(), source="user")
    return _node_out(saved)


# Пустая строка в этих полях PUT снимает значение (None в NodeUpdate значит «не менять»).
_CLEARABLE = ("subblock", "title", "starter_code")


@app.put("/api/nodes/{node_id}")
def edit_node(
    node_id: str, body: NodeUpdate, request: Request, _user: dict = Depends(require_member)
) -> dict:
    """Правка карточки, в том числе перенос в другое направление/колонку/под-колонку/уровень.
    404 — карточки или целевого направления нет, 422 — результат не проходит проверку направления."""
    tenant = resolve_tenant(request)
    existing = db.get_node(tenant, node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    fields = body.model_dump(exclude_none=True)
    for key in _CLEARABLE:
        if fields.get(key) == "":
            fields[key] = None
    if "tags" in fields:
        fields["tags"] = _tags_or_422(fields["tags"])
    target = _pool_or_404(request, fields.get("pool", existing["pool"]))
    # Перенос в другую колонку/направление без явной под-колонки: прежняя под-колонка там не существует —
    # снимаем её, а не отказываем (карточка встаёт в колонку без под-колонки).
    moved = "block" in fields or "pool" in fields
    if moved and "subblock" not in fields:
        block = fields.get("block", existing["block"])
        if existing.get("subblock") not in target.subblock_ids(block):
            fields["subblock"] = None
    merged = {**existing, **fields}
    _difficulty_or_422(target, merged["difficulty"])
    # existing несёт БД-поля (source/hidden/timestamps), которых нет в Node (extra=forbid):
    # валидируем только подмножество полей Node, а в БД пишем полный merged (db читает по .get).
    try:
        node = Node.model_validate({k: v for k, v in merged.items() if k in _NODE_FIELDS})
        validate_against_pool(node, target)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError / block вне пула → 422
        raise HTTPException(status_code=422, detail=str(exc))
    # правка из UI/API делает ноду пользовательской: файлы content/ её больше не перетирают (см. sync.py).
    saved = db.upsert_node(tenant, merged, source="user")
    return {"updated": saved["id"], "node": _node_out(saved)}


def _remove_node(tenant: str, row: dict) -> bool:
    """Seed-нода (source='seed') — не DELETE, а tombstone (hidden=1, source='user'): файл в content/
    остаётся источником этой ноды, и обычный DELETE её воскресил бы при следующем sync (sync
    пропускает только user-ноды). Пользовательская нода удаляется. Возвращает True для tombstone."""
    if row["source"] == "seed":
        db.tombstone_node(tenant, row["id"])
        return True
    db.delete_node(tenant, row["id"])
    return False


@app.delete("/api/nodes/{node_id}")
def remove_node(node_id: str, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Удалить вопрос из банка (seed — спрятать, см. _remove_node). 404, если нет."""
    tenant = resolve_tenant(request)
    existing = db.get_node(tenant, node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    return {"deleted": node_id, "tombstoned": _remove_node(tenant, existing)}


# ---------- progress (чек-лист разбора) ----------
# Ruling C4: значения статуса — один источник (Database.PROGRESS_STATUSES), а не дублирующийся паттерн.
class ProgressIn(BaseModel):
    status: str = Field(pattern="^(" + "|".join(Database.PROGRESS_STATUSES) + ")$")


@app.get("/api/progress")
def get_progress(request: Request, pool: Optional[str] = None, user: dict = Depends(current_user)) -> dict:
    p = _pool_or_404(request, pool)
    return db.get_progress(resolve_tenant(request), user["id"], p.id)


@app.put("/api/progress/{node_id}")
def set_progress(node_id: str, body: ProgressIn, request: Request, user: dict = Depends(current_user)) -> dict:
    """Статус карточки для текущего пользователя — любая роль (чек-лист личный)."""
    tenant = resolve_tenant(request)
    if db.get_node(tenant, node_id) is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    return db.set_progress(tenant, user["id"], node_id, body.status)


@app.delete("/api/progress/{node_id}")
def clear_progress(node_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
    return {"cleared": db.clear_progress(resolve_tenant(request), user["id"], node_id)}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "content_dir": str(CONTENT_DIR), "db": str(DB_PATH)}


# ---------- static frontend (если собран) ----------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
