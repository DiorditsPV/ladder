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
import secrets
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import (
    COOKIE_NAME,
    current_user,
    hash_password,
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
from .sync import sync_pools
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
_sync = sync_pools(db, resolve_tenant(), CONTENT_DIR)
log.info("content sync: created=%s updated=%s nodes=%d hidden=%d conflicts=%d errors=%d",
         _sync["created"], _sync["updated"], _sync["nodes_upserted"], len(_sync["hidden"]), len(_sync["conflicts"]), len(_sync["errors"]))
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
    """Создание пользователя owner'ом: email + пароль + роль."""

    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    role: str = Field(default="member", pattern="^(owner|member|viewer)$")


class ImportFile(BaseModel):
    filename: str = Field(min_length=1)
    content: str
    pool: Optional[str] = None


class NodeCreate(BaseModel):
    """Создание вопроса из UI: id генерится сервером, остальное валидируется."""

    pool: Optional[str] = None
    block: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    kind: Kind = "question"
    title: Optional[str] = None
    question: str = Field(min_length=1)
    answer: str = ""
    tags: List[str] = Field(default_factory=list)


class NodeUpdate(BaseModel):
    """Структурная правка вопроса — только переданные поля (None = не менять)."""

    title: Optional[str] = None
    difficulty: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None


class PoolCreate(BaseModel):
    """Новое направление: из пресета (копируются колонки и вопросы) ИЛИ со своими колонками."""

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


# ---------- users (управление пользователями — owner) ----------
@app.get("/api/users")
def list_users(request: Request, _owner: dict = Depends(require_owner)) -> list:
    return db.list_users(resolve_tenant(request))


@app.post("/api/users")
def create_user(body: UserCreate, request: Request, _owner: dict = Depends(require_owner)) -> dict:
    """Завести пользователя в тенанте owner'а. 409 при дубликате email."""
    import sqlite3

    tenant = resolve_tenant(request)
    if db.get_user_by_email(tenant, body.email) is not None:
        raise HTTPException(status_code=409, detail="email already exists")
    try:
        user = db.create_user(tenant, body.email, hash_password(body.password), body.role)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="email already exists")
    return _public_user(user)


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


def _pool_out(request: Request, p: PoolCfg, user: dict) -> dict:
    """Форма направления для API: конфиг + счётчик вопросов + сводка чек-листа юзера."""
    tenant = resolve_tenant(request)
    return {
        **p.to_dict(),
        "counts": {"nodes": db.count_nodes(tenant, pool=p.id)},
        "progress": db.progress_summary(tenant, user["id"], p.id),
    }


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


@app.get("/api/pools")
def get_pools(request: Request, _user: dict = Depends(current_user)) -> list:
    return [_pool_out(request, p, _user) for p in _pools(request).values()]


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
def sync_content(request: Request, _owner: dict = Depends(require_owner)) -> dict:
    """Перечитать content/: новые направления, обновлённые конфиги и seed-ноды; user-ноды не трогаются."""
    return sync_pools(db, resolve_tenant(request), CONTENT_DIR)


@app.get("/api/graph", response_model=GraphResponse)
def get_graph(
    request: Request,
    pool: Optional[str] = None,
    include_hidden: bool = False,
    _user: dict = Depends(current_user),
) -> GraphResponse:
    # Вопросы читаются из БД (а не с диска) — рантайм-правки переживают деплой.
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
import re  # noqa: E402 — локальный хелпер slug для генерации id новых нод


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


@app.post("/api/nodes")
def add_node(body: NodeCreate, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Создать новый вопрос в банке пула (БД, source='user'). id генерится из topic/title."""
    tenant = resolve_tenant(request)
    pool = _pool_or_404(request, body.pool)
    _difficulty_or_422(pool, body.difficulty)
    base = _slugify(body.topic or body.title or body.block)
    node_id = _unique_node_id(tenant, base)
    node = Node.model_validate({**body.model_dump(exclude={"pool"}), "pool": pool.id, "id": node_id})
    try:
        validate_against_pool(node, pool)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    saved = db.upsert_node(tenant, node.model_dump(by_alias=True), source="user")
    return {"id": saved["id"], "block": saved["block"], "title": saved.get("title") or ""}


@app.put("/api/nodes/{node_id}")
def edit_node(
    node_id: str, body: NodeUpdate, request: Request, _user: dict = Depends(require_member)
) -> dict:
    """Обновить структурные поля вопроса. 404 если нет, 422 если результат невалиден."""
    tenant = resolve_tenant(request)
    existing = db.get_node(tenant, node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    fields = body.model_dump(exclude_none=True)
    if "difficulty" in fields:
        _difficulty_or_422(_pool_or_404(request, existing["pool"]), fields["difficulty"])
    merged = {**existing, **fields}
    # existing несёт БД-поля (source/hidden/timestamps), которых нет в Node (extra=forbid):
    # валидируем только подмножество полей Node, а в БД пишем полный merged (db читает по .get).
    try:
        node = Node.model_validate({k: v for k, v in merged.items() if k in _NODE_FIELDS})
        pools = _pools(request)
        if merged["pool"] in pools:
            validate_against_pool(node, pools[merged["pool"]])
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError / block вне пула → 422
        raise HTTPException(status_code=422, detail=str(exc))
    # правка из UI делает ноду пользовательской: файлы content/ её больше не перетирают (см. sync.py).
    saved = db.upsert_node(tenant, merged, source="user")
    return {"updated": saved["id"]}


@app.delete("/api/nodes/{node_id}")
def remove_node(node_id: str, request: Request, _user: dict = Depends(require_member)) -> dict:
    """Удалить вопрос из банка. 404, если нет.

    Seed-нода (source='seed') — не DELETE, а tombstone (hidden=1, source='user'): файл в content/
    остаётся источником этой ноды, и обычный DELETE её воскресил бы при следующем sync (sync
    пропускает только user-ноды). Пользовательская нода (source='user') удаляется как раньше.
    """
    tenant = resolve_tenant(request)
    existing = db.get_node(tenant, node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    if existing["source"] == "seed":
        db.tombstone_node(tenant, node_id)
        return {"deleted": node_id, "tombstoned": True}
    db.delete_node(tenant, node_id)
    return {"deleted": node_id, "tombstoned": False}


# ---------- progress (чек-лист разбора) ----------
# Ruling C4: значения статуса — один источник (Database.PROGRESS_STATUSES), а не дублирующийся паттерн.
class ProgressIn(BaseModel):
    status: str = Field(pattern="^(" + "|".join(Database.PROGRESS_STATUSES) + ")$")


@app.get("/api/progress")
def get_progress(request: Request, pool: Optional[str] = None, user: dict = Depends(current_user)) -> dict:
    p = _pool_or_404(request, pool)
    return db.get_progress(resolve_tenant(request), user["id"], p.id)


@app.put("/api/progress/{node_id}")
def set_progress(node_id: str, body: ProgressIn, request: Request, user: dict = Depends(require_member)) -> dict:
    """Статус карточки для текущего пользователя. Гость (по ссылке) статусы не ставит — 403 из require_member."""
    tenant = resolve_tenant(request)
    if db.get_node(tenant, node_id) is None:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    return db.set_progress(tenant, user["id"], node_id, body.status)


@app.delete("/api/progress/{node_id}")
def clear_progress(node_id: str, request: Request, user: dict = Depends(require_member)) -> dict:
    return {"cleared": db.clear_progress(resolve_tenant(request), user["id"], node_id)}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "content_dir": str(CONTENT_DIR), "db": str(DB_PATH)}


# ---------- static frontend (если собран) ----------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
