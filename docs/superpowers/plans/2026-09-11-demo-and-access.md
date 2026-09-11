# Демо-режим и полный доступ — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сайт без входа открывается как демо (RU/EN, «Дата-инженер» и «Системный аналитик», чек-лист в браузере); полный режим — по незаметному входу, с аккаунтами, сменой пароля и страницей «Люди».

**Architecture:** Бэкенд: флаги направления `demo/lang/translation_of` (pool.yaml → таблица pools), анонимное чтение только демо-направлений через зависимость `optional_user`, несколько сессий на пользователя, ручки паролей и аккаунтов. Фронт: контекст сессии вместо жёсткого гейта входа; режим = есть ли сессия; хранилище прогресса (сервер или localStorage); выбор направления по языку. Контент: полные EN-переводы DE и SA отдельными направлениями.

**Tech Stack:** FastAPI + SQLite + pytest; React + TS + Vite; Playwright smoke; python-frontmatter для контента.

**Spec:** `docs/superpowers/specs/2026-09-11-demo-and-access-design.md`

## Global Constraints
- Без сессии доступны только `GET /api/pools` (демо-направления) и `GET /api/graph?pool=<демо>`; всё остальное — 401, как сейчас.
- Роли: owner — всё; viewer (приглашённые) — чтение + свой чек-лист; member — как сейчас.
- Неверный текущий пароль → 403, не 401 (фронт на 401 перезагружает страницу).
- Новый пароль — от 8 символов; одноразовый пароль сервера — `secrets.token_urlsafe(9)` (12 символов).
- Карточки `content/data-engineer*` не трогать; в `content/data-engineer/pool.yaml` и `content/system-analyst/pool.yaml` — только строка `demo: true`.
- Строки UI — русские ключи через `t(...)`, перевод в `frontend/src/i18n/en.ts`; `npm run i18n:check` зелёный. Новых зависимостей нет.
- Тесты бэкенда как в CI: из `backend/` — `INTERVIEW_DB_PATH=$(mktemp -d)/t.db INTERVIEW_OWNER_PASSWORD=interview-dev pytest -q`.
- Smoke — на свежей БД (`INTERVIEW_DB_PATH` во временный файл) и собранном фронте.

## Режимы исполнения и ветки
| Задачи | Режим | Ветка / worktree | Зависит от |
|---|---|---|---|
| 1–4 бэкенд | один субагент цепочкой (TDD), одно ревью в конце | `feature/demo-access` (основной чекаут) | — |
| 5 EN-контент | параллель: 2 переводчика (DE, SA), без сверки фактов | `feature/demo-en-content`, worktree `../interview-graph-en` от `dev` | — |
| 6–9 фронт | один субагент цепочкой, smoke-гейт, ревью + скриншоты | `feature/demo-access-ui` стеком на `feature/demo-access` | 1–4 |
| 10 выпуск | инлайн | — | всё |

Порядок слияния в `dev`: бэкенд → контент → фронт (фронт перед PR ребейзится на `dev` с контентом, smoke видит EN-пары) → релиз `dev → main` → ручной Deploy.

---

### Task 1: Флаги направления demo / lang / translation_of

**Files:**
- Modify: `backend/app/pools.py` (PoolCfg, `to_dict`, `_parse_pool`, `pool_from_row`)
- Modify: `backend/app/db.py` (`_SCHEMA` pools, `_migrate_pools`, `_row_to_pool`, `upsert_pool_seed`, `set_pool_config`)
- Modify: `backend/app/sync.py` (`_cfg`)
- Test: `backend/tests/test_pools.py`, `backend/tests/test_sync.py`

**Interfaces:**
- Produces: `PoolCfg.demo: bool = False`, `PoolCfg.lang: str = "ru"` (`"ru" | "en"`), `PoolCfg.translation_of: Optional[str] = None`; ключи `demo`, `lang`, `translation_of` в `PoolCfg.to_dict()` и в dict строки `db.get_pool/list_pools` (`demo` — bool).

- [ ] **Step 1: Failing tests.** В конец `backend/tests/test_pools.py`:

```python
def test_pool_flags_default_and_to_dict(tmp_path):
    _mk(tmp_path, "demo", VALID)
    p = load_pools(tmp_path)["demo"]
    assert (p.demo, p.lang, p.translation_of) == (False, "ru", None)
    d = p.to_dict()
    assert (d["demo"], d["lang"], d["translation_of"]) == (False, "ru", None)


def test_pool_flags_parsed(tmp_path):
    _mk(tmp_path, "demo", VALID + "demo: true\nlang: en\ntranslation_of: demo-ru\n")
    p = load_pools(tmp_path)["demo"]
    assert (p.demo, p.lang, p.translation_of) == (True, "en", "demo-ru")


@pytest.mark.parametrize("extra", ["lang: de\n", "demo: maybe later\n", "translation_of: Not An Id\n"])
def test_pool_flags_invalid_skip_pool(tmp_path, extra):
    _mk(tmp_path, "demo", VALID + extra)
    assert "demo" not in load_pools(tmp_path)
```

В конец `backend/tests/test_sync.py`:

```python
def test_sync_carries_and_clears_flags(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    (root / "demo" / "pool.yaml").write_text(POOL + "demo: true\nlang: en\ntranslation_of: demo-ru\n", encoding="utf-8")
    sync_pools(db, "t", root)
    row = db.get_pool("t", "demo")
    assert (row["demo"], row["lang"], row["translation_of"]) == (True, "en", "demo-ru")
    (root / "demo" / "pool.yaml").write_text(POOL, encoding="utf-8")
    sync_pools(db, "t", root)
    row = db.get_pool("t", "demo")
    assert (row["demo"], row["lang"], row["translation_of"]) == (False, "ru", None)
```

- [ ] **Step 2: Run — FAIL.** `pytest -q tests/test_pools.py tests/test_sync.py -k "flags"` → AttributeError / KeyError `demo`.

- [ ] **Step 3: Implement.** `backend/app/pools.py` — поля в конце dataclass (после `dir`) и константа:

```python
LANGS = ("ru", "en")
```

```python
    dir: Optional[Path] = None
    # Демо-режим (spec 2026-09-11): направление видно без входа; язык контента; оригинал перевода.
    demo: bool = False
    lang: str = "ru"
    translation_of: Optional[str] = None
```

В `to_dict()` после `"levels": ...`:

```python
            "demo": self.demo,
            "lang": self.lang,
            "translation_of": self.translation_of,
```

Хелпер рядом с `_req_str` и его вызов в `_parse_pool`:

```python
def _parse_flags(data: dict) -> tuple:
    demo = data.get("demo", False)
    if not isinstance(demo, bool):
        raise PoolConfigError("pool: 'demo' must be true or false")
    lang = str(data.get("lang") or "ru").strip()
    if lang not in LANGS:
        raise PoolConfigError(f"pool: 'lang' must be one of {', '.join(LANGS)}")
    tr = data.get("translation_of")
    if tr is not None and (not isinstance(tr, str) or not _ID_RE.match(tr)):
        raise PoolConfigError("pool: 'translation_of' must be a pool id")
    return demo, lang, tr
```

```python
    demo, lang, translation_of = _parse_flags(data)
    return PoolCfg(
        id=pid,
        ...,
        dir=pool_dir,
        demo=demo,
        lang=lang,
        translation_of=translation_of,
    )
```

`pool_from_row`:

```python
        dir=None,
        demo=bool(row.get("demo")),
        lang=row.get("lang") or "ru",
        translation_of=row.get("translation_of") or None,
```

`backend/app/db.py` — в `CREATE TABLE IF NOT EXISTS pools` после `levels`:

```sql
    demo        INTEGER NOT NULL DEFAULT 0,    -- 1 = видно без входа (демо-режим)
    lang        TEXT NOT NULL DEFAULT 'ru',    -- язык контента направления
    translation_of TEXT,                       -- id оригинала, если это перевод
```

В `_migrate_pools` после добавления `levels`:

```python
        for col, ddl in (
            ("demo", "ALTER TABLE pools ADD COLUMN demo INTEGER NOT NULL DEFAULT 0"),
            ("lang", "ALTER TABLE pools ADD COLUMN lang TEXT NOT NULL DEFAULT 'ru'"),
            ("translation_of", "ALTER TABLE pools ADD COLUMN translation_of TEXT"),
        ):
            if col not in cols:
                conn.execute(ddl)
```

`_row_to_pool`: `d["demo"] = bool(d.get("demo"))`.

`upsert_pool_seed` — колонки и значения:

```python
                INSERT OR IGNORE INTO pools (
                    tenant_id, id, label, description, blocks, levels, demo, lang, translation_of,
                    source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', ?, ?)
                """,
                (
                    tenant_id, pool["id"], pool["label"], pool.get("description") or "",
                    json.dumps(pool["blocks"], ensure_ascii=False),
                    json.dumps(pool.get("levels") or [], ensure_ascii=False),
                    int(bool(pool.get("demo"))), pool.get("lang") or "ru", pool.get("translation_of"),
                    now, now,
                ),
```

`set_pool_config`:

```python
                "UPDATE pools SET label = ?, description = ?, blocks = ?, levels = ?, demo = ?, lang = ?, "
                "translation_of = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                (cfg["label"], cfg.get("description") or "", json.dumps(cfg["blocks"], ensure_ascii=False),
                 json.dumps(cfg["levels"], ensure_ascii=False), int(bool(cfg.get("demo"))),
                 cfg.get("lang") or "ru", cfg.get("translation_of"), _now(), tenant_id, pool_id),
```

`backend/app/sync.py` `_cfg` — три ключа: `"demo": pool.demo, "lang": pool.lang, "translation_of": pool.translation_of`.

- [ ] **Step 4: Run — PASS**, затем весь `pytest -q` зелёный.
- [ ] **Step 5: Commit** `feat(pools): флаги demo/lang/translation_of из pool.yaml в БД`.

---

### Task 2: Анонимное чтение демо-направлений

**Files:**
- Modify: `backend/app/auth.py` (+ `optional_user`), `backend/app/main.py` (`_pool_out`, `get_pools`, `get_graph`), `backend/app/tenancy.py` (docstring)
- Test: Create `backend/tests/test_demo_access.py`

**Interfaces:**
- Consumes: `PoolCfg.demo` (Task 1).
- Produces: `optional_user(request) -> Optional[dict]`; `GET /api/pools` без сессии → только `demo=true`, без ключа `progress`; `GET /api/graph?pool=<id>` без сессии → 200 только для демо, иначе 401 (и без `pool` — 401).

- [ ] **Step 1: Failing test** `backend/tests/test_demo_access.py`:

```python
"""Демо без входа: анонимно читаются только направления с demo=true (spec 2026-09-11)."""

import uuid

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import OWNER_EMAIL, OWNER_PASSWORD, app


def _owner() -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 200
    return c


def _pool(c: TestClient, label: str) -> dict:
    r = c.post("/api/pools", json={"label": label, "blocks": [{"label": "A", "color": "#2563eb"}]})
    assert r.status_code == 200, r.text
    return r.json()


def _set_demo(pool_id: str, value: bool) -> None:
    with main_module.db._conn() as conn:
        conn.execute("UPDATE pools SET demo = ? WHERE tenant_id = 'default' AND id = ?", (int(value), pool_id))


def test_anonymous_reads_only_demo_pools():
    owner = _owner()
    tag = uuid.uuid4().hex[:6]
    demo, private = _pool(owner, f"Demo {tag}"), _pool(owner, f"Private {tag}")
    try:
        _set_demo(demo["id"], True)
        r = owner.post("/api/nodes", json={
            "pool": demo["id"], "block": demo["blocks"][0]["id"], "topic": "t",
            "difficulty": demo["levels"][0]["id"], "question": "q?",
        })
        assert r.status_code == 200, r.text
        anon = TestClient(app)
        pools = anon.get("/api/pools")
        assert pools.status_code == 200
        ids = {p["id"] for p in pools.json()}
        assert demo["id"] in ids and private["id"] not in ids
        assert all(p["demo"] for p in pools.json())
        assert all("progress" not in p for p in pools.json())
        g = anon.get(f"/api/graph?pool={demo['id']}")
        assert g.status_code == 200 and len(g.json()["nodes"]) == 1
        assert anon.get(f"/api/graph?pool={private['id']}").status_code == 401
        assert anon.get("/api/graph").status_code == 401
        assert anon.get("/api/graph?pool=no-such-pool").status_code == 401
        full = {p["id"]: p for p in owner.get("/api/pools").json()}
        assert private["id"] in full and "progress" in full[demo["id"]]
    finally:
        owner.delete(f"/api/pools/{demo['id']}")
        owner.delete(f"/api/pools/{private['id']}")


def test_anonymous_cannot_write_or_read_private_data():
    anon = TestClient(app)
    assert anon.put("/api/progress/x", json={"status": "known"}).status_code == 401
    assert anon.get("/api/progress?pool=data-engineer").status_code == 401
    assert anon.post("/api/nodes", json={"block": "a", "topic": "t", "difficulty": "x", "question": "q"}).status_code == 401
    assert anon.post("/api/pools/sync").status_code == 401
    assert anon.get("/api/users").status_code == 401
```

- [ ] **Step 2: Run — FAIL** (`/api/pools` без сессии → 401).
- [ ] **Step 3: Implement.** `backend/app/auth.py` (импорт `Optional` из typing):

```python
def optional_user(request: Request) -> Optional[dict]:
    """Как current_user, но без сессии — None вместо 401. Только для ручек демо-чтения
    (GET /api/pools, GET /api/graph; spec 2026-09-11)."""
    try:
        return current_user(request)
    except HTTPException:
        return None
```

`backend/app/main.py` — импорт `optional_user` из `.auth`; замены:

```python
def _pool_out(request: Request, p: PoolCfg, user: Optional[dict]) -> dict:
    """Форма направления для API: конфиг + счётчик вопросов + сводка чек-листа (только у вошедшего)."""
    tenant = resolve_tenant(request)
    out = {**p.to_dict(), "counts": {"nodes": db.count_nodes(tenant, pool=p.id)}}
    if user is not None:
        out["progress"] = db.progress_summary(tenant, user["id"], p.id)
    return out


@app.get("/api/pools")
def get_pools(request: Request, user: Optional[dict] = Depends(optional_user)) -> list:
    pools = _pools(request).values()
    if user is None:  # демо: тенант default, только направления с demo=true
        return [_pool_out(request, p, None) for p in pools if p.demo]
    return [_pool_out(request, p, user) for p in pools]


@app.get("/api/graph", response_model=GraphResponse)
def get_graph(
    request: Request,
    pool: Optional[str] = None,
    include_hidden: bool = False,
    user: Optional[dict] = Depends(optional_user),
) -> GraphResponse:
    # Вопросы читаются из БД (а не с диска) — рантайм-правки переживают деплой.
    if user is None:
        demo_pool = _pools(request).get(pool or "")
        if demo_pool is None or not demo_pool.demo:
            raise HTTPException(status_code=401, detail="not authenticated")
        return GraphResponse(nodes=_db_nodes(request, demo_pool), errors=[])
    return GraphResponse(
        nodes=_db_nodes(request, _pool_or_404(request, pool), include_hidden=include_hidden), errors=[]
    )
```

`backend/app/tenancy.py` — в docstring `resolve_tenant` после абзаца «ВНИМАНИЕ (fail-open)»:
«Исключение — демо-чтение (`auth.optional_user` в GET /api/pools и GET /api/graph): без сессии там осознанно читается тенант default и только направления с demo=true.»

- [ ] **Step 4: Run — PASS**, весь `pytest -q` зелёный (`test_unauthenticated_request_401` остаётся верным: `/api/graph` без pool → 401).
- [ ] **Step 5: Commit** `feat(api): демо-направления читаются без входа`.

---

### Task 3: Чек-лист для любой роли и несколько сессий

**Files:**
- Modify: `backend/app/main.py` (ручки progress), `backend/app/db.py` (`create_auth_session`, + `delete_user_sessions`), `backend/app/auth.py` (docstring ролей)
- Test: `backend/tests/test_auth.py` (замена `test_relogin_invalidates_prior_session`, новый тест viewer)

**Interfaces:**
- Produces: `Database.delete_user_sessions(tenant_id: str, user_id: str, except_token: Optional[str] = None) -> int`.

- [ ] **Step 1: Tests.** В `backend/tests/test_auth.py` заменить `test_relogin_invalidates_prior_session` на:

```python
def test_relogin_keeps_prior_session():
    """Несколько устройств: повторный вход не выбивает прежнюю сессию (spec 2026-09-11)."""
    c1 = _anon()
    assert _login(c1, OWNER_EMAIL, OWNER_PASSWORD).status_code == 200
    c2 = _anon()
    assert _login(c2, OWNER_EMAIL, OWNER_PASSWORD).status_code == 200
    assert c1.get("/api/auth/me").status_code == 200
    assert c2.get("/api/auth/me").status_code == 200


def test_viewer_keeps_checklist_but_cannot_edit():
    viewer = _user("viewer-progress@interview.local", "viewer-progress-pw", "viewer")
    owner = _owner()
    nid = owner.post("/api/nodes", json=_VALID_NODE).json()["id"]
    try:
        assert viewer.put(f"/api/progress/{nid}", json={"status": "known"}).status_code == 200
        assert viewer.delete(f"/api/progress/{nid}").status_code == 200
        assert viewer.post("/api/nodes", json=_VALID_NODE).status_code == 403
    finally:
        owner.delete(f"/api/nodes/{nid}")
```

- [ ] **Step 2: Run — FAIL** (c1 → 401; viewer PUT → 403).
- [ ] **Step 3: Implement.** `db.create_auth_session` — убрать `DELETE FROM auth_sessions WHERE tenant_id = ? AND user_id = ?` и комментарий про «один активный токен»; комментарий: «несколько сессий на пользователя (устройства); отзыв — delete_user_sessions». Новый метод рядом с `delete_auth_session`:

```python
    def delete_user_sessions(self, tenant_id: str, user_id: str, except_token: Optional[str] = None) -> int:
        """Отозвать сессии пользователя (кроме except_token — текущей). Возвращает число удалённых."""
        with self._conn() as conn:
            if except_token:
                cur = conn.execute(
                    "DELETE FROM auth_sessions WHERE tenant_id = ? AND user_id = ? AND token != ?",
                    (tenant_id, user_id, except_token),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM auth_sessions WHERE tenant_id = ? AND user_id = ?", (tenant_id, user_id)
                )
        return cur.rowcount
```

`main.py`: `set_progress` и `clear_progress` — `Depends(current_user)` вместо `require_member`; docstring `set_progress`: «Статус карточки для текущего пользователя — любая роль (чек-лист личный)». `auth.py` docstring ролей: «viewer — чтение и свой чек-лист».

- [ ] **Step 4: Run — PASS**, весь `pytest -q` зелёный.
- [ ] **Step 5: Commit** `feat(auth): чек-лист у любой роли, несколько сессий на пользователя`.

---

### Task 4: Пароли и аккаунты + гейт деплоя

**Files:**
- Modify: `backend/app/main.py` (`UserCreate`, `create_user`, + `PasswordChange`, `change_password`, `reset_user_password`, `delete_user`, `_one_time_password`), `backend/app/db.py` (+ `update_password`, `delete_user`)
- Modify: `.github/workflows/deploy.yml` (шаг «Проверить боевой адрес»)
- Test: Create `backend/tests/test_accounts.py`

**Interfaces:**
- Consumes: `delete_user_sessions` (Task 3).
- Produces (фронт Task 8): `POST /api/auth/password {current_password, new_password}` → `{"ok": true}` | 403 | 422; `POST /api/users {email, password?, role?="viewer"}` → `{id, email, role, tenant_id, password?}` (password только если сгенерирован); `POST /api/users/{id}/password` → `{id, password}` (400 для себя, 404 нет); `DELETE /api/users/{id}` → `{deleted}` (400 для себя, 404 нет); `GET /api/users` → `[{tenant_id, id, email, role, created_at}]` (как сейчас).

- [ ] **Step 1: Failing tests** `backend/tests/test_accounts.py`:

```python
"""Пароли и аккаунты полного режима (spec 2026-09-11)."""

import uuid

from fastapi.testclient import TestClient

from app.main import OWNER_EMAIL, OWNER_PASSWORD, app


def _login(c: TestClient, email: str, password: str):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def _owner() -> TestClient:
    c = TestClient(app)
    assert _login(c, OWNER_EMAIL, OWNER_PASSWORD).status_code == 200
    return c


def _email() -> str:
    return f"acc-{uuid.uuid4().hex[:8]}@x.test"


def test_create_user_generates_one_time_password_and_viewer_role():
    owner, email = _owner(), _email()
    r = owner.post("/api/users", json={"email": email})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "viewer" and len(body["password"]) >= 12
    assert _login(TestClient(app), email, body["password"]).status_code == 200
    explicit = owner.post("/api/users", json={"email": _email(), "password": "explicit-1"}).json()
    assert "password" not in explicit


def test_change_password_flow():
    owner, email = _owner(), _email()
    pw = owner.post("/api/users", json={"email": email}).json()["password"]
    me, other = TestClient(app), TestClient(app)
    assert _login(me, email, pw).status_code == 200
    assert _login(other, email, pw).status_code == 200
    bad = me.post("/api/auth/password", json={"current_password": "wrong", "new_password": "new-password-1"})
    assert bad.status_code == 403
    short = me.post("/api/auth/password", json={"current_password": pw, "new_password": "short"})
    assert short.status_code == 422
    ok = me.post("/api/auth/password", json={"current_password": pw, "new_password": "new-password-1"})
    assert ok.status_code == 200
    assert me.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert _login(TestClient(app), email, pw).status_code == 401
    assert _login(TestClient(app), email, "new-password-1").status_code == 200


def test_change_password_requires_login():
    r = TestClient(app).post("/api/auth/password", json={"current_password": "a", "new_password": "bbbbbbbb"})
    assert r.status_code == 401


def test_owner_resets_password():
    owner, email = _owner(), _email()
    created = owner.post("/api/users", json={"email": email}).json()
    user = TestClient(app)
    assert _login(user, email, created["password"]).status_code == 200
    r = owner.post(f"/api/users/{created['id']}/password")
    assert r.status_code == 200 and r.json()["password"] != created["password"]
    assert user.get("/api/auth/me").status_code == 401
    assert _login(TestClient(app), email, r.json()["password"]).status_code == 200
    me_id = owner.get("/api/auth/me").json()["id"]
    assert owner.post(f"/api/users/{me_id}/password").status_code == 400
    assert owner.post("/api/users/nope/password").status_code == 404


def test_owner_deletes_user():
    owner, email = _owner(), _email()
    created = owner.post("/api/users", json={"email": email}).json()
    user = TestClient(app)
    assert _login(user, email, created["password"]).status_code == 200
    assert owner.delete(f"/api/users/{created['id']}").status_code == 200
    assert user.get("/api/auth/me").status_code == 401
    assert _login(TestClient(app), email, created["password"]).status_code == 401
    me_id = owner.get("/api/auth/me").json()["id"]
    assert owner.delete(f"/api/users/{me_id}").status_code == 400
    assert owner.delete("/api/users/nope").status_code == 404


def test_non_owner_cannot_manage_accounts():
    owner, email = _owner(), _email()
    created = owner.post("/api/users", json={"email": email}).json()
    viewer = TestClient(app)
    assert _login(viewer, email, created["password"]).status_code == 200
    assert viewer.post("/api/users", json={"email": _email()}).status_code == 403
    assert viewer.post(f"/api/users/{created['id']}/password").status_code == 403
    assert viewer.delete(f"/api/users/{created['id']}").status_code == 403
```

- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement.** `db.py` рядом с `create_user`:

```python
    def update_password(self, tenant_id: str, user_id: str, password_hash: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE users SET password_hash = ? WHERE tenant_id = ? AND id = ?",
                (password_hash, tenant_id, user_id),
            )
        return cur.rowcount == 1

    def delete_user(self, tenant_id: str, user_id: str) -> bool:
        """Удалить аккаунт вместе с его сессиями и чек-листом (одна транзакция). False — не найден."""
        with self._conn() as conn:
            conn.execute("DELETE FROM progress WHERE tenant_id = ? AND user_id = ?", (tenant_id, user_id))
            conn.execute("DELETE FROM auth_sessions WHERE tenant_id = ? AND user_id = ?", (tenant_id, user_id))
            cur = conn.execute("DELETE FROM users WHERE tenant_id = ? AND id = ?", (tenant_id, user_id))
        return cur.rowcount == 1
```

`main.py` — модели:

```python
class UserCreate(BaseModel):
    """Аккаунт от owner'а: без password сервер генерирует одноразовый и отдаёт его один раз."""

    email: str = Field(min_length=3)
    password: Optional[str] = Field(default=None, min_length=6)
    role: str = Field(default="viewer", pattern="^(owner|member|viewer)$")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
```

Хелпер и ручки (после `auth_me` и в блоке users):

```python
def _one_time_password() -> str:
    return secrets.token_urlsafe(9)  # 12 символов; показывается владельцу один раз


@app.post("/api/auth/password")
def change_password(body: PasswordChange, request: Request, user: dict = Depends(current_user)) -> dict:
    """Сменить свой пароль. Неверный текущий — 403 (не 401: фронт на 401 перезагружает страницу)."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=403, detail="wrong current password")
    db.update_password(user["tenant_id"], user["id"], hash_password(body.new_password))
    db.delete_user_sessions(user["tenant_id"], user["id"], except_token=request.cookies.get(COOKIE_NAME))
    return {"ok": True}
```

`create_user` — тело:

```python
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
```

```python
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
    if user_id == owner["id"]:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    if not db.delete_user(resolve_tenant(request), user_id):
        raise HTTPException(status_code=404, detail="user not found")
    return {"deleted": user_id}
```

`.github/workflows/deploy.yml`, шаг «Проверить боевой адрес» — вместо проверки `graph 401`:

```bash
          code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$base/api/graph?pool=data-engineer")
          [ "$code" = 200 ] || { echo "✗ демо-граф без cookie → $code (ожидалось 200)"; exit 1; }
          code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$base/api/graph?pool=data-engineer-x5")
          [ "$code" = 401 ] || { echo "✗ не-демо граф без cookie → $code (ожидалось 401)"; exit 1; }
          echo "✓ health 200, демо 200, остальное за логином"
```

- [ ] **Step 4: Run — PASS**, весь `pytest -q` зелёный.
- [ ] **Step 5: Commit** `feat(auth): смена пароля, одноразовые пароли, сброс и удаление аккаунтов; гейт деплоя под демо`.

**Ревью ветки бэкенда (после Task 4):** одно ревью диффа `dev..feature/demo-access` против спеки — анонимный доступ не шире двух ручек, 401/403 как в спеке, миграция идемпотентна. Затем PR → `dev`.

---

### Task 5: EN-переводы «Дата-инженера» и «Системного аналитика» (параллельно)

**Files:**
- Create: `content/data-engineer-en/**`, `content/system-analyst-en/**`
- Modify: `content/data-engineer/pool.yaml`, `content/system-analyst/pool.yaml` — одна строка `demo: true` в конце
- Scratch (не коммитить): `$CLAUDE_JOB_DIR/tmp/en/dump_ru.py`, `build_en.py`, `tr_<pool>.json`

**Interfaces:**
- Produces: направления `data-engineer-en` и `system-analyst-en` с `lang: en`, `translation_of: <оригинал>`, `demo: true`; id карточки = id оригинала + `-en`; колонки, под-колонки, id уровней, теги, `kind`, `weight`, `topic` — как у оригинала.

- [ ] **Step 1: Выгрузить RU-карточки** (worktree `../interview-graph-en`, из его корня, venv основного чекаута):

```python
import json, sys
sys.path.insert(0, "backend")
from pathlib import Path
from app.importer import load_pool_content
from app.pools import load_pools

pool_id, out = sys.argv[1], Path(sys.argv[2])
pool = load_pools(Path("content"))[pool_id]
nodes, errors = load_pool_content(pool)
assert not errors, errors
out.write_text(json.dumps({n.id: {"title": n.title, "question": n.question, "answer": n.answer,
    "rubric": n.rubric, "starterCode": n.starter_code, "kind": n.kind} for n in nodes},
    ensure_ascii=False, indent=1), encoding="utf-8")
print(pool_id, len(nodes))
```

- [ ] **Step 2: Перевести** (по субагенту на направление). Выход `tr_<pool>.json`:
`{"pool": {"label", "description", "blocks": {id: label}, "subblocks": {id: label}, "levels": {id: label}}, "cards": {id: {"title", "question", "answer", "rubric"?: [...], "starterCode"?: str}}}`.
Правила: естественный технический английский, смысл и структура ответа 1:1, код не меняется (переводятся только комментарии в `starterCode`), термины (shuffle, DAG, SCD2 …) как в индустрии; ни одна строка не начинается с `#`; title 2–8 слов. Без сверки фактов — это перевод.

- [ ] **Step 3: Собрать направление** `build_en.py <pool> tr_<pool>.json`:

```python
import json, sys
from pathlib import Path
import frontmatter, yaml

src_id, tr = sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
root = Path("content")
src, dst = root / src_id, root / f"{src_id}-en"
pool = yaml.safe_load((src / "pool.yaml").read_text(encoding="utf-8"))
labels = tr["pool"]
pool.pop("demo", None)
pool.update({"id": f"{src_id}-en", "label": labels["label"], "description": labels["description"]})
for b in pool["blocks"]:
    b["label"] = labels["blocks"][b["id"]]
    for s in b.get("subblocks") or []:
        s["label"] = labels["subblocks"][s["id"]]
for lv in pool.get("levels") or []:
    lv["label"] = labels["levels"][lv["id"]]
pool.update({"lang": "en", "translation_of": src_id, "demo": True})
dst.mkdir(exist_ok=True)
(dst / "pool.yaml").write_text(
    f"# English translation of {src_id} (demo). Card id = original id + '-en'.\n"
    + yaml.safe_dump(pool, allow_unicode=True, sort_keys=False), encoding="utf-8")
for f in sorted(src.glob("*/*.md")):
    post = frontmatter.load(f)
    oid, t = post["id"], tr["cards"][post["id"]]
    post["id"], post["title"] = f"{oid}-en", t["title"]
    for k in ("rubric", "starterCode"):
        if t.get(k):
            post[k] = t[k]
    q, a = ("Task", "Solution") if post.get("kind") == "task" else ("Question", "Answer")
    post.content = f"## {q}\n{t['question'].strip()}\n\n## {a}\n{t['answer'].strip()}\n"
    (dst / f.parent.name).mkdir(exist_ok=True)
    (dst / f.parent.name / f"{oid}-en.md").write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
print(dst, len(list(dst.glob("*/*.md"))))
```

- [ ] **Step 4: Флаги оригиналов:** `printf 'demo: true\n' >> content/data-engineer/pool.yaml` и то же для `content/system-analyst/pool.yaml` (проверь, что файл кончался переводом строки).
- [ ] **Step 5: Гейты:** `cd backend && pytest -q tests/test_app.py -k imports` (EN-пулы импортируются: ≥10 нод, title, 1–3 тега); число карточек EN = RU (61 и 44); скрипт-проверка: в title/question/answer EN-карточек нет кириллицы вне блоков кода — список нарушений пуст.
- [ ] **Step 6: Commit** (только `content/`) `content: EN-переводы data-engineer и system-analyst для демо; флаг demo у оригиналов`. PR → `dev` после слияния бэкенда.

---

### Task 6: Сессия, маршруты, стартовый экран и вход

**Files:**
- Create: `frontend/src/session.tsx`, `frontend/src/pages/Landing.tsx`
- Modify: `frontend/src/api.ts` (`json`, + `setSessionActive`), `frontend/src/AuthGate.tsx`, `frontend/src/router.ts`, `frontend/src/Router.tsx`, `frontend/src/pages/PageShell.tsx`, `frontend/src/styles.css`, `frontend/src/i18n/en.ts`

**Interfaces:**
- Produces: `useSession(): {user: AuthUser | null; ready: boolean; refresh(): Promise<void>; logout(): Promise<void>}`; `useCan(): {demo: boolean; editContent: boolean; syncFiles: boolean; manageUsers: boolean}`; `useHomeHref(): string` (`#/` у вошедшего, `#/demo` в демо); маршруты `demo | login | people`; `href.demo`, `href.login`, `href.people`; `setSessionActive(on: boolean)`.

- [ ] **Step 1: `api.ts`** — 401 перезагружает страницу только при живой сессии (в демо 401 — «нельзя», а не «протухло»):

```ts
let sessionActive = false;
/** Сессия подтверждена /api/auth/me: только тогда 401 означает «протухла» → перезагрузка. */
export function setSessionActive(on: boolean): void {
  sessionActive = on;
}

async function json<T>(res: Response, opts?: { skipAuthReload?: boolean }): Promise<T> {
  if (res.status === 401 && sessionActive && !opts?.skipAuthReload) {
    window.location.reload();
    throw new Error("session expired");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

- [ ] **Step 2: `session.tsx`:**

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setSessionActive, type AuthUser } from "./api";
import { href } from "./router";

// Режим приложения следует из сессии: нет её — демо (чтение демо-направлений, чек-лист в браузере),
// есть — полный режим по роли (spec 2026-09-11).
type Session = { user: AuthUser | null; ready: boolean; refresh: () => Promise<void>; logout: () => Promise<void> };
const Ctx = createContext<Session>({ user: null, ready: false, refresh: async () => {}, logout: async () => {} });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const me = await api.me();
      setSessionActive(true);
      setUser(me);
    } catch {
      setSessionActive(false);
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);
  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setSessionActive(false);
      setUser(null);
      window.location.hash = href.home;
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const value = useMemo(() => ({ user, ready, refresh, logout }), [user, ready, refresh, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  return useContext(Ctx);
}

/** Что можно текущему режиму/роли. Демо — только чек-лист в браузере. */
export function useCan() {
  const role = useSession().user?.role ?? null;
  return {
    demo: role === null,
    editContent: role === "owner" || role === "member",
    syncFiles: role === "owner",
    manageUsers: role === "owner",
  };
}

/** Куда ведёт «← Меню»: главная полного режима или демо-главная. */
export function useHomeHref(): string {
  return useSession().user ? href.home : href.demo;
}
```

- [ ] **Step 3: `AuthGate.tsx`:**

```tsx
import Router from "./Router.tsx";
import { SessionProvider, useSession } from "./session";

// Гейт больше не требует входа: без сессии — демо-режим, вход — по #/login (spec 2026-09-11).
function Gate() {
  const { ready } = useSession();
  if (!ready) return null;
  return <Router />;
}

export function AuthGate() {
  return (
    <SessionProvider>
      <Gate />
    </SessionProvider>
  );
}
```

- [ ] **Step 4: `router.ts`** — маршруты и ссылки:

```ts
export type Route =
  | { name: "home" }
  | { name: "demo" }
  | { name: "login" }
  | { name: "people" }
  | { name: "board"; pool: string }
  | { name: "bank"; pool: string };
```

В `parseHash` перед `board`: `if (segs[0] === "demo") return { name: "demo" }; if (segs[0] === "login") return { name: "login" }; if (segs[0] === "people") return { name: "people" };`. В `href`: `demo: "#/demo", login: "#/login", people: "#/people",`.

- [ ] **Step 5: `pages/Landing.tsx`:**

```tsx
import { ArrowRight } from "lucide-react";
import { LangSwitch } from "../components/LangSwitch";
import { useT } from "../i18n";
import { href } from "../router";

// Стартовый экран без входа: демо в приоритете, вход — приглушённая ссылка в углу (spec 2026-09-11).
export function Landing() {
  const t = useT();
  return (
    <div className="landing">
      <header className="landing__top">
        <LangSwitch />
      </header>
      <main className="landing__main">
        <h1 className="landing__title">Ladder</h1>
        <p className="landing__pitch">
          {t("Тема разложена на колонки и ступени. Проходите карточки и отмечайте: знаю, повторить, не знаю.")}
        </p>
        <a className="landing__demo btn--primary" href={href.demo}>
          {t("Открыть демо")}
          <ArrowRight size={18} strokeWidth={1.75} aria-hidden="true" />
        </a>
        <p className="landing__note">{t("Дата-инженер и системный аналитик — на русском и английском.")}</p>
      </main>
      <a className="landing__login" href={href.login}>{t("Вход")}</a>
    </div>
  );
}
```

`styles.css` (в конец):

```css
/* Стартовый экран (демо в приоритете). Ссылка «Вход» нарочно не акцентирована. */
.landing { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg); color: var(--text); }
.landing__top { display: flex; justify-content: flex-end; padding: 16px 24px; }
.landing__main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; padding: 0 24px 12vh; text-align: center; }
.landing__title { margin: 0; font-size: 44px; font-weight: 800; letter-spacing: -0.02em; color: var(--heading); }
.landing__pitch { margin: 0; max-width: 520px; font-size: 17px; line-height: 1.5; color: var(--text-muted); }
.landing__demo { display: inline-flex; align-items: center; gap: 8px; padding: 12px 22px; border-radius: 10px; font-size: 16px; text-decoration: none; }
.landing__note { margin: 0; font-size: 13px; color: var(--text-muted); }
.landing__login { position: fixed; right: 16px; bottom: 12px; font-size: 12px; color: var(--text-muted); opacity: .55; text-decoration: none; }
.landing__login:hover { opacity: .9; }
```


- [ ] **Step 6: `Router.tsx`** — режим из сессии, редиректы, вход:

```tsx
import { useCallback, useEffect, useState } from "react";
import { api, type AuthUser } from "./api";
import { Login } from "./components/Login";
import BoardPage from "./pages/BoardPage";
import { BankPage } from "./pages/BankPage";
import { HomePage } from "./pages/HomePage";
import { Landing } from "./pages/Landing";
import { href, useRoute, type Route } from "./router";
import { useSession } from "./session";
import { useT } from "./i18n";
import type { PoolConfig } from "./types";

// Куда увести с маршрута, недоступного режиму (null — остаться).
function redirectFor(route: Route, user: AuthUser | null): string | null {
  if (user) {
    if (route.name === "login" || route.name === "demo") return href.home;
    if (route.name === "people" && user.role !== "owner") return href.home;
    return null;
  }
  return route.name === "people" ? href.home : null;
}

export default function Router() {
  const t = useT();
  const route = useRoute();
  const { user, refresh } = useSession();
  const [pools, setPools] = useState<PoolConfig[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reloadPools = useCallback(() => api.pools().then(setPools).catch((e) => setError(String(e))), []);
  useEffect(() => {
    setPools(null);
    setError(null);
    void reloadPools();
  }, [reloadPools, user?.id]);

  const redirect = redirectFor(route, user);
  useEffect(() => {
    if (redirect) window.location.replace(redirect);
  }, [redirect]);
  if (redirect) return null;

  if (route.name === "login") {
    return <Login onLogin={async () => { await refresh(); window.location.replace(href.home); }} />;
  }
  if (!user && route.name === "home") return <Landing />;
  if (error) return <div className="loading">{t("Не удалось загрузить направления: {error}", { error })}</div>;
  if (!pools) return <div className="loading">{t("Загрузка…")}</div>;

  const demo = !user;
  const poolOf = (id: string) => pools.find((p) => p.id === id) ?? null;
  switch (route.name) {
    case "board": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={pools} demo={demo} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      return <BoardPage key={pool.id} pool={pool} />;
    }
    case "bank": {
      const pool = poolOf(route.pool);
      if (!pool) return <HomePage pools={pools} demo={demo} notice={t("Направления «{pool}» нет", { pool: route.pool })} onChanged={reloadPools} />;
      return <BankPage key={pool.id} pool={pool} onChanged={reloadPools} />;
    }
    default:
      return <HomePage pools={pools} demo={demo} onChanged={reloadPools} />;
  }
}
```

(`people` добавится в Task 8; до него `people` у owner падает в `default`.) `HomePage` получает проп `demo?: boolean` (пока не используется — Task 7).

- [ ] **Step 7: `PageShell.tsx`** — `href={useHomeHref()}` вместо `href.home` у «← Меню»; в `BoardPage.tsx` все ссылки «назад в меню» (`href.home`) — так же через `useHomeHref()`.
- [ ] **Step 8: i18n** — ключи «Тема разложена на колонки…», «Открыть демо», «Дата-инженер и системный аналитик — на русском и английском.» в `en.ts` («Each topic is laid out in columns and rungs. Work through the cards and mark each one: know it, revisit, don't know.», «Open demo», «Data engineer and system analyst — in Russian and English.»).
- [ ] **Step 9: Gate:** `cd frontend && npm run build && npm run i18n:check`; руками: `#/` без cookie — стартовый экран; `#/login` — форма, после входа — главная.
- [ ] **Step 10: Commit** `feat(ui): стартовый экран, демо-режим по умолчанию, вход по #/login`.

---

### Task 7: Демо и роли на главной, доске и в банке; язык направлений

**Files:**
- Create: `frontend/src/progressStore.ts`, `frontend/src/poolLang.ts`
- Modify: `frontend/src/types.ts` (PoolConfig), `frontend/src/Router.tsx`, `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/BoardPage.tsx`, `frontend/src/components/DetailDrawer.tsx`, `frontend/src/pages/BankPage.tsx`, `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: `useSession`, `useCan` (Task 6); поля `demo/lang/translation_of` в `/api/pools` (Task 1).
- Produces: `useProgressStore(): ProgressStore`; `localSummary(pool: string, total: number)`; `poolsForLang(pools, lang)`, `pairOf(pools, pool, lang)`.

- [ ] **Step 1: `types.ts`** — в `PoolConfig`: `demo?: boolean; lang?: "ru" | "en"; translation_of?: string | null;`.
- [ ] **Step 2: `progressStore.ts`:**

```ts
import { api } from "./api";
import { useSession } from "./session";
import type { Progress } from "./types";

// Отметки чек-листа: у вошедшего — на сервере, в демо — только в localStorage этого браузера.
export interface ProgressStore {
  load(pool: string): Promise<Record<string, Progress>>;
  set(pool: string, nodeId: string, status: Progress): Promise<void>;
  clear(pool: string, nodeId: string): Promise<void>;
}

const key = (pool: string) => `ladder.progress.${pool}`;

function readLocal(pool: string): Record<string, Progress> {
  try {
    return JSON.parse(localStorage.getItem(key(pool)) || "{}") as Record<string, Progress>;
  } catch {
    return {};
  }
}

function writeLocal(pool: string, value: Record<string, Progress>): void {
  try {
    localStorage.setItem(key(pool), JSON.stringify(value));
  } catch {
    /* приватный режим — отметки живут до перезагрузки */
  }
}

export const localProgress: ProgressStore = {
  load: async (pool) => readLocal(pool),
  set: async (pool, nodeId, status) => {
    const v = readLocal(pool);
    v[nodeId] = status;
    writeLocal(pool, v);
  },
  clear: async (pool, nodeId) => {
    const v = readLocal(pool);
    delete v[nodeId];
    writeLocal(pool, v);
  },
};

export const serverProgress: ProgressStore = {
  load: (pool) => api.progress(pool),
  set: async (_pool, nodeId, status) => {
    await api.setProgress(nodeId, status);
  },
  clear: async (_pool, nodeId) => {
    await api.clearProgress(nodeId);
  },
};

export function useProgressStore(): ProgressStore {
  return useSession().user ? serverProgress : localProgress;
}

/** Сводка для карточки направления в демо — та же форма, что поле progress у /api/pools. */
export function localSummary(pool: string, total: number) {
  const values = Object.values(readLocal(pool));
  const n = (s: Progress) => values.filter((v) => v === s).length;
  return { known: n("known"), review: n("review"), unknown: n("unknown"), total };
}
```

- [ ] **Step 3: `poolLang.ts`:**

```ts
import type { Lang } from "./i18n";
import type { PoolConfig } from "./types";

// Язык контента: перевод заменяет оригинал на своём языке, если есть; иначе — оригинал (spec 2026-09-11).
export function poolsForLang(pools: PoolConfig[], lang: Lang): PoolConfig[] {
  const translations = new Map<string, PoolConfig>();
  for (const p of pools) if (p.translation_of && (p.lang ?? "ru") === lang) translations.set(p.translation_of, p);
  return pools
    .filter((p) => !p.translation_of)
    .map((p) => ((p.lang ?? "ru") === lang ? p : translations.get(p.id) ?? p));
}

/** Пара направления на языке lang (для переключателя на доске); null — пары нет. */
export function pairOf(pools: PoolConfig[], pool: PoolConfig, lang: Lang): PoolConfig | null {
  if ((pool.lang ?? "ru") === lang) return pool;
  if (pool.translation_of) {
    const original = pools.find((p) => p.id === pool.translation_of);
    if (original && (original.lang ?? "ru") === lang) return original;
  }
  return pools.find((p) => p.translation_of === pool.id && (p.lang ?? "ru") === lang) ?? null;
}
```

- [ ] **Step 4: `Router.tsx`** — язык: `const [lang] = useLang();` (импорт из `./i18n`), эффект до ранних `return` (после эффекта `redirect`):

```tsx
  useEffect(() => {
    if (!pools || (route.name !== "board" && route.name !== "bank")) return;
    const current = pools.find((p) => p.id === route.pool);
    const pair = current ? pairOf(pools, current, lang) : null;
    if (pair && current && pair.id !== current.id) {
      window.location.replace(route.name === "board" ? href.board(pair.id) : href.bank(pair.id));
    }
  }, [lang, pools, route]);
```

Главная получает `poolsForLang(pools, lang)` вместо `pools` во всех трёх вызовах `HomePage`.

- [ ] **Step 5: `HomePage.tsx`:**
  - убрать состояние `role` и эффект `api.me()`; `const can = useCan();` (`../session`);
  - кнопку `home__add` и пустое состояние с подсказкой про `pool.yaml` показывать только при `can.editContent`;
  - кнопку `.poolcard__menu` и `.poolcard__dropdown` — только при `can.editContent`; пункт «Обновить из файлов» — при `can.syncFiles`;
  - прогресс: `const progress = demo ? localSummary(p.id, p.counts?.nodes ?? 0) : p.progress;` и в разметке `progress` вместо `p.progress` (условие `progress && progress.total > 0`);
  - в шапке `pageshell__actions` перед `<LangSwitch />` — место под `AccountMenu` (Task 8).
- [ ] **Step 6: `BoardPage.tsx`:** `const store = useProgressStore(); const can = useCan();`; загрузка — `store.load(pool.id).then(setStatuses).catch(() => setStatuses({}))` с зависимостями `[pool.id, store]`; в `setStatus` — `const request = clearing ? store.clear(pool.id, nodeId) : store.set(pool.id, nodeId, status);` и зависимости `[statuses, store, pool.id]`; `DetailDrawer` получает `canEdit={can.editContent}`.
- [ ] **Step 7: `DetailDrawer.tsx`:** проп `canEdit: boolean` в `Props`; кнопки `.drawer__delete` и `.drawer__edit` рендерить только при `canEdit` («Скрыть» — локальная, остаётся у всех).
- [ ] **Step 8: `BankPage.tsx`:** `const can = useCan();`; `.addbtn` и `.uploadbtn` — только при `can.editContent`; «Скачать HTML» остаётся.
- [ ] **Step 9: Gate:** `npm run build && npm run i18n:check`; руками без cookie: `#/demo` — только демо-направления, без «+» и •••; доска — `1` ставит точку, F5 — точка на месте, в drawer нет «Удалить/Редактировать»; EN — главная и доска показывают `-en` пары (если контент Task 5 уже в ветке; иначе проверить на двух направлениях из `demo/content-en` не нужно — отложить до ребейза).
- [ ] **Step 10: Commit** `feat(ui): демо и роли — чек-лист в браузере, скрытые правки, язык направлений`.

---

### Task 8: Аккаунт: смена пароля, выход, страница «Люди»

**Files:**
- Create: `frontend/src/components/ChangePasswordModal.tsx`, `frontend/src/components/AccountMenu.tsx`, `frontend/src/pages/PeoplePage.tsx`
- Modify: `frontend/src/api.ts`, `frontend/src/Router.tsx`, `frontend/src/pages/HomePage.tsx`, `frontend/src/components/SettingsMenu.tsx`, `frontend/src/styles.css`, `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: ручки Task 4; `useSession` (Task 6).
- Produces: `api.changePassword(current, next): Promise<"ok" | "wrong-current" | "too-short">`, `api.users()`, `api.createUser(email)`, `api.resetUserPassword(id)`, `api.deleteUser(id)`; тип `AccountUser`.

- [ ] **Step 1: `api.ts`:**

```ts
export interface AccountUser {
  id: string;
  email: string;
  role: AuthUser["role"];
  tenant_id: string;
  created_at?: string;
}
```

в объект `api`:

```ts
  changePassword: async (current: string, next: string): Promise<"ok" | "wrong-current" | "too-short"> => {
    const res = await fetch(`${BASE}/auth/password`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: next }),
    });
    if (res.status === 403) return "wrong-current";
    if (res.status === 422) return "too-short";
    await json<{ ok: boolean }>(res);
    return "ok";
  },
  users: () => fetch(`${BASE}/users`).then(json<AccountUser[]>),
  createUser: (email: string) =>
    fetch(`${BASE}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).then(json<AccountUser & { password: string }>),
  resetUserPassword: (id: string) =>
    fetch(`${BASE}/users/${encodeURIComponent(id)}/password`, { method: "POST" }).then(json<{ id: string; password: string }>),
  deleteUser: (id: string) =>
    fetch(`${BASE}/users/${encodeURIComponent(id)}`, { method: "DELETE" }).then(json<{ deleted: string }>),
```

- [ ] **Step 2: `ChangePasswordModal.tsx`** (оверлей и Esc — как в `UploadModal`, классы `upload-modal*` переиспользуются):

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { useT } from "../i18n";

export function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [onClose]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (next.length < 8) return setError(t("Новый пароль — не короче 8 символов"));
    if (next !== repeat) return setError(t("Пароли не совпадают"));
    setBusy(true);
    try {
      const r = await api.changePassword(current, next);
      if (r === "wrong-current") setError(t("Текущий пароль неверный"));
      else if (r === "too-short") setError(t("Новый пароль — не короче 8 символов"));
      else setDone(true);
    } catch {
      setError(t("Не удалось сменить пароль"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="upload-modal" onClick={onClose}>
      <form className="upload-modal__card pwmodal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="upload-modal__head">
          <strong>{t("Сменить пароль")}</strong>
          <button type="button" className="upload-modal__close" onClick={onClose} title={t("Закрыть (Esc)")}>✕</button>
        </div>
        {done ? (
          <p className="pwmodal__ok">{t("Пароль изменён. Остальные устройства вышли из аккаунта.")}</p>
        ) : (
          <>
            <input className="pwmodal__current" type="password" autoComplete="current-password" placeholder={t("Текущий пароль")} value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
            <input className="pwmodal__new" type="password" autoComplete="new-password" placeholder={t("Новый пароль")} value={next} onChange={(e) => setNext(e.target.value)} />
            <input className="pwmodal__repeat" type="password" autoComplete="new-password" placeholder={t("Повторите новый пароль")} value={repeat} onChange={(e) => setRepeat(e.target.value)} />
            {error && <div className="pwmodal__error">{error}</div>}
            <button className="btn--primary pwmodal__submit" type="submit" disabled={busy || !current || !next}>{t("Сменить")}</button>
          </>
        )}
      </form>
    </div>
  );
}
```

- [ ] **Step 3: `AccountMenu.tsx`** (главная полного режима; закрытие кликом мимо и Esc — как меню ••• на главной):

```tsx
import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { href } from "../router";
import { useSession } from "../session";
import { ChangePasswordModal } from "./ChangePasswordModal";

export function AccountMenu() {
  const t = useT();
  const { user, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  if (!user) return null;
  return (
    <div className="account">
      <button className="account__btn iconbtn btn--quiet" aria-haspopup="menu" aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
        {user.email}
      </button>
      {open && (
        <div className="account__menu" role="menu" onClick={(e) => e.stopPropagation()}>
          <button className="account__password" role="menuitem" onClick={() => { setOpen(false); setPwOpen(true); }}>{t("Сменить пароль")}</button>
          {user.role === "owner" && (
            <a className="account__people" role="menuitem" href={href.people} onClick={() => setOpen(false)}>{t("Люди")}</a>
          )}
          <button className="account__logout" role="menuitem" onClick={() => { setOpen(false); void logout(); }}>{t("Выйти")}</button>
        </div>
      )}
      {pwOpen && <ChangePasswordModal onClose={() => setPwOpen(false)} />}
    </div>
  );
}
```

`HomePage.tsx`: `{!demo && <AccountMenu />}` перед `<LangSwitch />` в `pageshell__actions`.

- [ ] **Step 4: `SettingsMenu.tsx`** — последняя группа (после «Справка»), только у вошедшего:

```tsx
      {user && (
        <div className="settings__group">
          <div className="settings__title">{t("Аккаунт")}</div>
          <div className="settings__account-email">{user.email}</div>
          <button className="setdrawer__act settings__password" onClick={() => setPwOpen(true)}>{t("Сменить пароль")}</button>
          {user.role === "owner" && <a className="setdrawer__act settings__people" href={href.people}>{t("Люди")}</a>}
          <button className="setdrawer__act settings__logout" onClick={() => void logout()}>{t("Выйти")}</button>
        </div>
      )}
      {pwOpen && <ChangePasswordModal onClose={() => setPwOpen(false)} />}
```

с `const { user, logout } = useSession(); const [pwOpen, setPwOpen] = useState(false);` (импорты `useState`, `useSession`, `href`, `ChangePasswordModal`). Модалка внутри `.setdrawer` — клик в ней не закрывает панель (проверка `closest(".settings")` — модалку рендерить внутри обёртки `.settings`, как саму панель).

- [ ] **Step 5: `PeoplePage.tsx`:**

```tsx
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type AccountUser } from "../api";
import { useT } from "../i18n";
import { useSession } from "../session";
import { PageShell } from "./PageShell";

// «Люди» (owner): аккаунты полного режима. Пароль показывается один раз — после заведения или сброса.
export function PeoplePage() {
  const t = useT();
  const { user } = useSession();
  const [users, setUsers] = useState<AccountUser[]>([]);
  const [email, setEmail] = useState("");
  const [issued, setIssued] = useState<{ email: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api.users().then(setUsers).catch(() => setError(t("Не удалось загрузить список"))), [t]);
  useEffect(() => { void load(); }, [load]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const value = email.trim();
    if (!value) return;
    try {
      const created = await api.createUser(value);
      setIssued({ email: created.email, password: created.password });
      setEmail("");
      void load();
    } catch (err) {
      setError(String(err).includes("409") ? t("Такой аккаунт уже есть") : t("Не удалось добавить"));
    }
  };
  const reset = async (u: AccountUser) => {
    try {
      const r = await api.resetUserPassword(u.id);
      setIssued({ email: u.email, password: r.password });
    } catch {
      setError(t("Не удалось сбросить пароль"));
    }
  };
  const remove = async (u: AccountUser) => {
    if (!window.confirm(t("Удалить аккаунт {email} вместе с его чек-листом?", { email: u.email }))) return;
    try {
      await api.deleteUser(u.id);
      void load();
    } catch {
      setError(t("Не удалось удалить аккаунт"));
    }
  };
  const roleLabel = (r: AccountUser["role"]) => (r === "owner" ? t("владелец") : r === "member" ? t("редактор") : t("разбор"));

  return (
    <PageShell title={t("Люди")}>
      <form className="people__add" onSubmit={add}>
        <input className="people__email" type="email" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <button className="btn--primary people__submit" type="submit" disabled={!email.trim()}>{t("Добавить")}</button>
      </form>
      {issued && (
        <div className="people__issued" role="status">
          <span>{t("Пароль для {email} — показывается один раз:", { email: issued.email })}</span>
          <code className="people__password">{issued.password}</code>
          <button className="iconbtn" onClick={() => void navigator.clipboard?.writeText(issued.password)}>{t("Скопировать")}</button>
          <button className="iconbtn btn--quiet" onClick={() => setIssued(null)}>{t("Скрыть")}</button>
        </div>
      )}
      {error && <div className="errbar">{error}</div>}
      <table className="people__table">
        <thead>
          <tr><th>{t("Почта")}</th><th>{t("Доступ")}</th><th>{t("Заведён")}</th><th /></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} data-email={u.email}>
              <td>{u.email}</td>
              <td>{roleLabel(u.role)}</td>
              <td>{u.created_at?.slice(0, 10) ?? ""}</td>
              <td className="people__actions">
                {u.id !== user?.id && (
                  <>
                    <button className="iconbtn people__reset" onClick={() => void reset(u)}>{t("Сбросить пароль")}</button>
                    <button className="iconbtn people__delete" onClick={() => void remove(u)}>{t("Удалить")}</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </PageShell>
  );
}
```

`Router.tsx`: `case "people": return <PeoplePage />;` (редирект не-owner уже в `redirectFor`).

- [ ] **Step 6: Стили** — в конец `styles.css`:

```css
/* Аккаунт полного режима и «Люди». */
.account { position: relative; }
.account__btn { font-size: 12px; color: var(--text-muted); max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account__menu { position: absolute; right: 0; top: calc(100% + 6px); z-index: 30; min-width: 180px; display: flex; flex-direction: column; padding: 6px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.15); }
.account__menu button, .account__menu a { text-align: left; border: 0; background: transparent; padding: 8px 10px; border-radius: 6px; font-size: 13px; color: var(--text); text-decoration: none; cursor: pointer; }
.account__menu button:hover, .account__menu a:hover { background: var(--hover); }
.pwmodal { display: flex; flex-direction: column; gap: 10px; width: 340px; max-width: 100%; }
.pwmodal input { padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); }
.pwmodal__error { color: #dc2626; font-size: 13px; }
.pwmodal__ok { margin: 8px 0; }
.settings__account-email { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; overflow-wrap: anywhere; }
.people__add { display: flex; gap: 8px; margin-bottom: 16px; max-width: 480px; }
.people__email { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); }
.people__issued { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 10px 14px; margin-bottom: 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.people__password { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; padding: 2px 8px; border-radius: 6px; background: var(--hover); }
.people__table { width: 100%; border-collapse: collapse; }
.people__table th, .people__table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); font-size: 14px; }
.people__table th { font-size: 12px; font-weight: 600; color: var(--text-muted); }
.people__actions { display: flex; gap: 8px; justify-content: flex-end; }
```

- [ ] **Step 7: i18n** — все новые строки в `en.ts`: «Сменить пароль»→«Change password», «Люди»→«People», «Выйти»→«Sign out», «Аккаунт»→«Account», «Текущий пароль»→«Current password», «Новый пароль»→«New password», «Повторите новый пароль»→«Repeat new password», «Сменить»→«Change», «Новый пароль — не короче 8 символов»→«The new password must be at least 8 characters», «Пароли не совпадают»→«Passwords do not match», «Текущий пароль неверный»→«The current password is wrong», «Не удалось сменить пароль»→«Could not change the password», «Пароль изменён. Остальные устройства вышли из аккаунта.»→«Password changed. Other devices have been signed out.», «Добавить»→«Add», «Пароль для {email} — показывается один раз:»→«Password for {email} — shown only once:», «Скопировать»→«Copy», «Почта»→«Email», «Доступ»→«Access», «Заведён»→«Added», «Сбросить пароль»→«Reset password», «Удалить аккаунт {email} вместе с его чек-листом?»→«Delete the account {email} together with its checklist?», «Такой аккаунт уже есть»→«This account already exists», «Не удалось добавить»→«Could not add», «Не удалось сбросить пароль»→«Could not reset the password», «Не удалось удалить аккаунт»→«Could not delete the account», «Не удалось загрузить список»→«Could not load the list», «владелец»→«owner», «редактор»→«editor», «разбор»→«study». Ключи, уже существующие в словаре («Удалить», «Скрыть», «Вход»), не дублировать.
- [ ] **Step 8: Gate:** `npm run build && npm run i18n:check`.
- [ ] **Step 9: Commit** `feat(ui): смена пароля, выход и страница «Люди»`.

---

### Task 9: Smoke, скриншоты, документация

**Files:**
- Modify: `frontend/smoke.mjs`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `DEPLOY.md`

- [ ] **Step 1: smoke.mjs — начало до входа** (вместо ожидания `.login__card` сразу после `goto`; стиль проверок — как во всём smoke: `fail(...)` и `console.log("OK: ...")`):

```js
await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForSelector(".landing__demo", { timeout: 10000 });
const loginFont = await page.$eval(".landing__login", (el) => parseFloat(getComputedStyle(el).fontSize));
if (loginFont > 13) fail(`landing: «Вход» слишком заметен (font-size ${loginFont}px)`);
await page.click(".landing__demo");
await page.waitForSelector('.poolcard[data-pool="data-engineer"]', { timeout: 10000 });
if ((await page.locator('.poolcard[data-pool="system-analyst"]').count()) !== 1) fail("demo: нет системного аналитика");
if ((await page.locator('.poolcard[data-pool="data-engineer-x5"]').count()) !== 0) fail("demo: виден не-демо пул X5");
if ((await page.locator(".home__add, .poolcard__menu").count()) !== 0) fail("demo: видна правка направлений");
console.log("OK: landing → demo home");
await page.click('.poolcard[data-pool="data-engineer"] .poolcard__open');
await page.waitForSelector(".react-flow__node-question", { timeout: 15000 });
await page.locator(".react-flow__node-question").first().click();
await page.keyboard.press("1");
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 3000 });
if ((await page.locator(".drawer__delete, .drawer__edit").count()) !== 0) fail("demo: в drawer есть удаление/правка");
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector('.qnode__status[data-status="known"]', { timeout: 15000 })
  .catch(() => fail("demo: отметка не пережила перезагрузку (localStorage)"));
console.log("OK: demo checklist persists in the browser");
await page.click(".langswitch");
await page.waitForURL(/#\/board\/data-engineer-en/, { timeout: 10000 })
  .catch(() => fail("demo: EN не переключил на перевод направления"));
await page.click(".langswitch");
console.log("OK: demo language switch uses the translation");
await page.goto(URL + "#/login", { waitUntil: "networkidle" });
await page.waitForSelector(".login__card", { timeout: 10000 });
```

Далее — существующий вход owner'ом (заполнение `.login__input` и submit) и прежние шаги полного режима без изменений, кроме тех, что ждали форму входа сразу после первого `goto`.

- [ ] **Step 2: smoke.mjs — аккаунты** (в конце, перед итоговым сообщением):

```js
await page.goto(URL + "#/people", { waitUntil: "networkidle" });
const viewerEmail = `viewer-${Date.now()}@smoke.test`;
await page.fill(".people__email", viewerEmail);
await page.click(".people__submit");
await page.waitForSelector(".people__password", { timeout: 5000 });
const viewerPw = (await page.locator(".people__password").innerText()).trim();
if (viewerPw.length < 12) fail("people: одноразовый пароль не показан");
console.log("OK: people — account created with a one-time password");
await page.goto(URL, { waitUntil: "networkidle" });
await page.click(".account__btn");
await page.click(".account__logout");
await page.waitForSelector(".landing__demo", { timeout: 10000 });
await page.goto(URL + "#/login", { waitUntil: "networkidle" });
await page.fill('.login__input[type="email"]', viewerEmail);
await page.fill('.login__input[type="password"]', viewerPw);
await page.click(".login__card button[type=submit]");
await page.waitForSelector('.poolcard[data-pool="apache-kafka"]', { timeout: 10000 });
if ((await page.locator(".home__add, .poolcard__menu").count()) !== 0) fail("viewer: видна правка направлений");
await page.click(".account__btn");
await page.click(".account__password");
await page.fill(".pwmodal__current", viewerPw);
await page.fill(".pwmodal__new", "viewer-new-pass-1");
await page.fill(".pwmodal__repeat", "viewer-new-pass-1");
await page.click(".pwmodal__submit");
await page.waitForSelector(".pwmodal__ok", { timeout: 5000 }).catch(() => fail("viewer: пароль не сменился"));
console.log("OK: viewer signs in, sees all pools read-only, changes the password");
```

- [ ] **Step 3: Прогон:** свежая БД, собранный фронт, контент с EN-парами (ветка ребейзнута на `dev` после слияния Task 5):
`cd backend && INTERVIEW_DB_PATH=$(mktemp -d)/s.db INTERVIEW_OWNER_PASSWORD=interview-dev uvicorn app.main:app --port 8003` и `cd frontend && SMOKE_URL=http://localhost:8003/ npm run smoke` → `ALL SMOKE CHECKS PASSED`.
- [ ] **Step 4: Скриншоты** (playwright, 1600×1000): стартовый экран RU и EN, демо-доска EN, «Люди» — открыть через Read и проверить глазами: «Вход» незаметен, лишних кнопок в демо нет.
- [ ] **Step 5: Документация:** README — раздел «Режимы: демо и полный доступ» (что видит гость, как войти `#/login`, как владелец заводит людей, одноразовый пароль, смена своего); CLAUDE.md/AGENTS.md — маршруты `#/demo`, `#/login`, `#/people`, флаги `demo/lang/translation_of` в pool.yaml, роли (viewer — разбор), `optional_user` только в двух ручках; DEPLOY.md — новый гейт (демо 200, не-демо 401).
- [ ] **Step 6: Commit** `test(smoke): демо, вход, аккаунты; docs: режимы доступа`.

**Ревью ветки фронта:** одно ревью `feature/demo-access..feature/demo-access-ui` против спеки + просмотр скриншотов. Затем ребейз на `dev`, PR → `dev`.

---

### Task 10: Выпуск

- [ ] PR бэкенда → `dev` (CI) → merge; PR контента → `dev` → merge; ребейз фронта на `dev`, smoke, PR → `dev` → merge.
- [ ] PR `dev → main` → merge → `gh workflow run Deploy --ref main` → run success (гейт: health 200, демо 200, не-демо 401).
- [ ] Живой сайт без cookie: `/` — стартовый экран; `#/demo` — DE и SA; EN — переводы; `#/login` — вход владельцем; «Люди» открывается.
- [ ] `docker compose up -d --build` локально; память и леджер обновлены.
