# Подпроект A: уровни как данные направления + синхронизация контента — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** уровни сложности — упорядоченный список направления (`pool.yaml` → `pools.levels`), а не enum; `POST /api/pools/sync` и старт сервера подхватывают изменения `content/` без рестарта и без условия «пул пуст».

**Architecture:** `LevelCfg` рядом с `BlockCfg` в `pools.py` (парсинг, JSON, нормализация из UI); столбец `pools.levels` с мягкой миграцией; `Node.difficulty: str`, проверка по пулу в импортёре и в API; sampler получает порядок уровней параметром. Новый модуль `backend/app/sync.py` — upsert seed-нод из файлов, скрытие исчезнувших, конфликт с `user`-нодами. Фронт выводит ряды/подписи/цвета из `pool.levels` через хелперы в `types.ts`, как уже делает для колонок.

**Tech Stack:** FastAPI, pydantic v2, SQLite, PyYAML, python-frontmatter, pytest; React + TypeScript + Vite, lucide-react.

**Spec:** `docs/superpowers/specs/2026-09-10-topic-study-pivot-design.md` (раздел «Подпроект A»).

## Global Constraints

- `content/data-engineer/` и `content/data-engineer-x5/` **не меняются** (`git diff --stat content/data-engineer*` пуст в конце каждой задачи). `system-analyst` в этом подпроекте тоже не трогаем — его пересобирает B.
- `DEFAULT_LEVELS = (base «Base», junior «Junior», middle «Middle», senior «Senior»)` — пул без `levels` получает их; DE-пулы визуально не меняются (первые четыре цвета палитры уровней — прежние `DIFF_COLOR`).
- Уровней в пуле 2–8, `id` по `^[a-z0-9-]+$`, уникален в пуле; `label` непустой.
- Правка ноды из UI (`PUT /api/nodes/{id}`) переводит её в `source='user'` — файлы её больше не перетирают.
- `sync` **не** удаляет ноды и не каскадит удаление колонок/уровней: конфиг направления обновляется без побочных удалений; исчезнувшие из файлов seed-ноды прячутся (`hidden=1`), скрытые вручную не разворачиваются.
- Комментарии в коде — по-русски, в стиле файлов; `set -euo pipefail` не применимо — это Python/TS.
- Ветка `feature/levels-and-sync` (уже создана, на ней спека). Не пушить в `main`.
- Режимы (CLAUDE.md): Task 1, 2, 3 — **субагент + ревью** (миграция, слои, переписывание 38 мест); Task 4 — **инлайн**; Task 5 — гейты и PR. Последовательно, одна ветка.

---

### Task 1: Бэкенд — уровни как данные (модель, pools, db, importer, sampler, API)

**Files:**
- Modify: `backend/app/models.py:16,32`
- Modify: `backend/app/pools.py` (dataclasses, parse, json, normalize, `_parse_pool`, `pool_from_row`)
- Modify: `backend/app/db.py` (`_SCHEMA` pools, `_migrate_pools`, `_row_to_pool`, `upsert_pool_seed`, `create_pool`, `update_pool`)
- Modify: `backend/app/importer.py:validate_against_pool`
- Modify: `backend/app/sampler.py` (`LEVELS` → параметр)
- Modify: `backend/app/seed.py:seed_pool_if_empty` (передать `levels`)
- Modify: `backend/app/main.py` (`NodeCreate`, `NodeUpdate`, `PoolCreate`, `PoolUpdate`, `create_pool`, `update_pool`, `create_node`, `update_node`, `_plan_from`/matrix_order, `_levels_or_422`)
- Test: `backend/tests/test_levels.py`

**Interfaces:**
- Produces: `pools.LevelCfg(id, label)`, `pools.DEFAULT_LEVELS`, `pools.parse_levels(raw) -> Tuple[LevelCfg,...]`, `pools.levels_to_json(levels) -> str`, `pools.normalize_levels(raw, existing) -> List[dict]`, `PoolCfg.levels`, `PoolCfg.level_ids`, `PoolCfg.to_dict()["levels"]`; `db.update_pool(..., fields={"levels": [...]})`; `sampler.matrix_order(nodes, block_order, sub_order, level_order)`; API: `levels` в `GET/POST/PUT /api/pools`, 422 на чужой `difficulty`.
- Consumes: ничего нового.

- [ ] **Step 1: Тесты уровней (падают)**

`backend/tests/test_levels.py`:
```python
"""Уровни сложности как данные направления: pool.yaml → pools.levels → валидация нод и API."""

from pathlib import Path

import pytest

from app.db import Database
from app.importer import load_pool_content
from app.pools import DEFAULT_LEVELS, PoolConfigError, load_pools, normalize_levels, parse_levels

VALID = """\
id: demo
label: Demo
blocks:
  - { id: a, label: A, color: "#111111", weight: 1 }
levels:
  - { id: intro, label: Введение }
  - { id: deep,  label: Глубина }
"""

NO_LEVELS = """\
id: plain
label: Plain
blocks:
  - { id: a, label: A, color: "#111111", weight: 1 }
"""


def _mk(tmp_path: Path, name: str, yaml_text: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "pool.yaml").write_text(yaml_text, encoding="utf-8")
    return d


def _card(d: Path, block: str, nid: str, difficulty: str) -> None:
    (d / block).mkdir(exist_ok=True)
    (d / block / f"{nid}.md").write_text(
        f"---\nid: {nid}\nblock: {block}\ndifficulty: {difficulty}\ntopic: t\ntitle: T\ntags: [sql]\n---\n"
        "## Вопрос\nQ?\n## Ответ\nA\n",
        encoding="utf-8",
    )


def test_levels_parsed_and_default(tmp_path):
    _mk(tmp_path, "demo", VALID)
    _mk(tmp_path, "plain", NO_LEVELS)
    pools = load_pools(tmp_path)
    assert [l.id for l in pools["demo"].levels] == ["intro", "deep"]
    assert pools["demo"].to_dict()["levels"] == [{"id": "intro", "label": "Введение"}, {"id": "deep", "label": "Глубина"}]
    assert pools["plain"].levels == DEFAULT_LEVELS
    assert [l.id for l in DEFAULT_LEVELS] == ["base", "junior", "middle", "senior"]


@pytest.mark.parametrize(
    "raw",
    [
        [{"id": "one", "label": "1"}],                                   # меньше двух
        [{"id": f"l{i}", "label": str(i)} for i in range(9)],            # больше восьми
        [{"id": "x", "label": "X"}, {"id": "x", "label": "Y"}],          # дубль id
        [{"id": "Bad Id", "label": "B"}, {"id": "ok", "label": "O"}],    # не slug
        [{"id": "a", "label": ""}, {"id": "b", "label": "B"}],           # пустая подпись
    ],
)
def test_parse_levels_rejects(raw):
    with pytest.raises(PoolConfigError):
        parse_levels(raw)


def test_importer_validates_difficulty_against_pool(tmp_path):
    d = _mk(tmp_path, "demo", VALID)
    _card(d, "a", "demo-01", "intro")
    _card(d, "a", "demo-02", "senior")  # уровня senior в demo нет
    nodes, errors = load_pool_content(load_pools(tmp_path)["demo"])
    assert [n.id for n in nodes] == ["demo-01"]
    assert len(errors) == 1 and "difficulty 'senior'" in errors[0].error and "intro, deep" in errors[0].error


def test_normalize_levels_generates_ids_and_keeps_existing():
    existing = parse_levels([{"id": "intro", "label": "Введение"}, {"id": "deep", "label": "Глубина"}])
    out = normalize_levels([{"id": "deep", "label": "Глубже"}, {"label": "Внутренности"}, {"label": "Внутренности"}], existing)
    assert out == [
        {"id": "deep", "label": "Глубже"},
        {"id": "vnutrennosti", "label": "Внутренности"},
        {"id": "vnutrennosti-2", "label": "Внутренности"},
    ]


def test_db_migration_adds_default_levels(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    with db._conn() as conn:  # старая строка без levels — как в БД до миграции
        conn.execute("ALTER TABLE pools DROP COLUMN levels")
        conn.execute(
            "INSERT INTO pools (tenant_id, id, label, description, blocks, source, created_at, updated_at) "
            "VALUES ('t', 'old', 'Old', '', '[]', 'seed', 'x', 'x')"
        )
    db2 = Database(tmp_path / "t.db")
    assert db2.get_pool("t", "old")["levels"] == [{"id": l.id, "label": l.label} for l in DEFAULT_LEVELS]


def test_update_pool_levels_prunes_nodes(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    blocks = [{"id": "a", "label": "A", "color": "#111111", "weight": 1, "subblocks": []}]
    levels = [{"id": "intro", "label": "I"}, {"id": "deep", "label": "D"}]
    db.create_pool("t", "p", "P", "", blocks, levels=levels)
    assert db.get_pool("t", "p")["levels"] == levels
    for nid, lvl in (("n1", "intro"), ("n2", "deep")):
        db.upsert_node("t", {"id": nid, "pool": "p", "block": "a", "topic": "t", "difficulty": lvl, "question": "q"})
    db.update_pool("t", "p", {"levels": [{"id": "intro", "label": "I2"}, {"id": "top", "label": "T"}]})
    assert db.get_pool("t", "p")["levels"][0]["label"] == "I2"
    assert db.get_node("t", "n1") is not None and db.get_node("t", "n2") is None


def _client():
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    return c


def test_api_pools_expose_levels_and_reject_foreign_difficulty():
    c = _client()
    de = next(p for p in c.get("/api/pools").json() if p["id"] == "data-engineer")
    assert [l["id"] for l in de["levels"]] == ["base", "junior", "middle", "senior"]
    r = c.post("/api/nodes", json={"pool": "data-engineer", "block": "python", "topic": "t", "difficulty": "guru",
                                   "kind": "question", "question": "q?", "answer": "a", "tags": ["sql"]})
    assert r.status_code == 422 and "base, junior, middle, senior" in r.json()["detail"]


def test_api_create_pool_with_levels_and_update():
    c = _client()
    p = c.post("/api/pools", json={"label": "Levels Test", "blocks": [{"label": "A", "color": "#111111"}],
                                   "levels": [{"label": "Один"}, {"label": "Два"}, {"label": "Три"}]}).json()
    try:
        assert [l["id"] for l in p["levels"]] == ["odin", "dva", "tri"]
        r = c.put(f"/api/pools/{p['id']}", json={"levels": [{"id": "odin", "label": "1"}]})
        assert r.status_code == 422  # меньше двух
        r = c.put(f"/api/pools/{p['id']}", json={"levels": [{"id": "odin", "label": "1"}, {"id": "tri", "label": "3"}]})
        assert r.status_code == 200 and [l["id"] for l in r.json()["levels"]] == ["odin", "tri"]
        # пресет копирует уровни
        p2 = c.post("/api/pools", json={"label": "Levels Copy", "preset": p["id"]}).json()
        assert [l["id"] for l in p2["levels"]] == ["odin", "tri"]
        c.delete(f"/api/pools/{p2['id']}")
    finally:
        c.delete(f"/api/pools/{p['id']}")
```

- [ ] **Step 2: Запустить — падают**

Run: `cd backend && . .venv/bin/activate && pytest tests/test_levels.py -q`
Expected: ImportError `DEFAULT_LEVELS` / `parse_levels`.

- [ ] **Step 3: `models.py`** — `Difficulty = str` с комментарием:

```python
# Уровень — строка: допустимые значения задаёт список levels в pool.yaml пула (как block),
# проверяет импортёр (validate_against_pool) и API, а не схема.
Difficulty = str
```
В `Node`: `difficulty: Difficulty` — **без дефолта** (поле обязательно в frontmatter; все 107 карточек его содержат).

- [ ] **Step 4: `pools.py` — LevelCfg, DEFAULT_LEVELS, parse/json/normalize**

После `SubblockCfg` добавить:
```python
@dataclass(frozen=True)
class LevelCfg:
    id: str
    label: str


# Уровни пула без `levels:` в pool.yaml — прежняя четвёрка, чтобы существующие пулы и их файлы
# остались валидными без правок. Порядок = сложность по возрастанию.
DEFAULT_LEVELS: Tuple[LevelCfg, ...] = (
    LevelCfg("base", "Base"),
    LevelCfg("junior", "Junior"),
    LevelCfg("middle", "Middle"),
    LevelCfg("senior", "Senior"),
)
```
В `PoolCfg` — поле `levels: Tuple[LevelCfg, ...] = DEFAULT_LEVELS` (после `blocks`, до `dir`), свойство и вывод:
```python
    @property
    def level_ids(self) -> frozenset:
        return frozenset(l.id for l in self.levels)
```
и в `to_dict()` после `"blocks"`: `"levels": [{"id": l.id, "label": l.label} for l in self.levels],`.

Функции (после `parse_blocks`):
```python
def parse_levels(raw_levels: object) -> Tuple[LevelCfg, ...]:
    """Уровни из YAML (`levels:`) или JSON таблицы pools: 2–8 штук, id — slug, уникален, label непустой."""
    if not isinstance(raw_levels, list):
        raise PoolConfigError("'levels' must be a list")
    if not 2 <= len(raw_levels) <= 8:
        raise PoolConfigError("pool must declare between 2 and 8 levels")
    out, seen = [], set()
    for rl in raw_levels:
        if not isinstance(rl, dict):
            raise PoolConfigError("each level must be a mapping")
        lid = _req_str(rl, "id", "level")
        if not _ID_RE.match(lid):
            raise PoolConfigError(f"level id '{lid}' must match [a-z0-9-]+")
        if lid in seen:
            raise PoolConfigError(f"duplicate level id '{lid}'")
        seen.add(lid)
        out.append(LevelCfg(id=lid, label=_req_str(rl, "label", f"level {lid}")))
    return tuple(out)


def levels_to_json(levels: Tuple[LevelCfg, ...]) -> str:
    """Уровни в JSON для столбца pools.levels (та же форма, что в /api/pools)."""
    return json.dumps([{"id": l.id, "label": l.label} for l in levels], ensure_ascii=False)


def normalize_levels(raw: object, existing: Tuple[LevelCfg, ...] = ()) -> List[dict]:
    """Уровни из UI → форма для parse_levels: новым (без id) id даётся транслитерацией подписи,
    уникально среди переданных и текущих (`-2`, `-3`…). Валидацию делает parse_levels."""
    if not isinstance(raw, list):
        raise PoolConfigError("levels must be a list")
    taken = {l.id for l in existing} | {rl.get("id") for rl in raw if isinstance(rl, dict) and isinstance(rl.get("id"), str)}
    out: List[dict] = []
    for rl in raw:
        if not isinstance(rl, dict):
            raise PoolConfigError("each level must be a mapping")
        lid = rl.get("id") if isinstance(rl.get("id"), str) else _unique_slug(rl.get("label"), taken, "level")
        out.append({"id": lid, "label": rl.get("label")})
    return out
```
`_parse_pool`: `levels=parse_levels(data["levels"]) if data.get("levels") is not None else DEFAULT_LEVELS,`.
`pool_from_row`: `levels=parse_levels(row["levels"]) if row.get("levels") else DEFAULT_LEVELS,`.
`_unique_slug` уже есть выше по файлу — переместить `normalize_levels` ниже него.

- [ ] **Step 5: `db.py` — столбец, миграция, CRUD**

В `_SCHEMA` таблица `pools` — после `blocks`: `levels      TEXT NOT NULL DEFAULT '[]',        -- JSON: [{id,label}]; '[]' → DEFAULT_LEVELS при чтении`.
Новый метод (вызвать в `__init__` после `_migrate_nodes`):
```python
    @staticmethod
    def _migrate_pools(conn: sqlite3.Connection) -> None:
        """Уровни как данные направления: столбец pools.levels. Старые строки получают прежнюю
        четвёрку явно (не '[]'), чтобы ответ API не зависел от того, когда пул создан."""
        from .pools import DEFAULT_LEVELS, levels_to_json

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(pools)").fetchall()}
        if "levels" not in cols:
            conn.execute("ALTER TABLE pools ADD COLUMN levels TEXT NOT NULL DEFAULT '[]'")
        conn.execute("UPDATE pools SET levels = ? WHERE levels = '[]'", (levels_to_json(DEFAULT_LEVELS),))
```
`_row_to_pool`: `d["levels"] = json.loads(d.get("levels") or "[]")`.
`upsert_pool_seed`: в INSERT добавить `levels` (значение `json.dumps(pool.get("levels") or [], ensure_ascii=False)`); `create_pool(..., blocks, copy_from=None, levels: Optional[List[Dict]] = None)` — при `copy_from` и `levels is None` брать `levels` пресета (`self.get_pool(tenant_id, copy_from)["levels"]`), иначе `levels or []`; в INSERT — столбец `levels`.
`update_pool`: рядом с `blocks` — `levels = fields.get("levels")`; условие «нечего менять» учитывает `levels is None`; в транзакции:
```python
            if levels is not None:
                kept_l = [l["id"] for l in levels]
                if not kept_l:
                    raise ValueError("levels must not be empty")
                conn.execute(
                    "UPDATE pools SET levels = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                    (json.dumps(levels, ensure_ascii=False), now, tenant_id, pool_id),
                )
                marks = ",".join("?" * len(kept_l))
                conn.execute(
                    f"DELETE FROM nodes WHERE tenant_id = ? AND pool = ? AND difficulty NOT IN ({marks})",
                    (tenant_id, pool_id, *kept_l),
                )
```
Докстринг `update_pool` дополнить: «вопросы исчезнувших уровней удаляются».
В `upsert_node`/`seed_nodes`/`_copy_nodes` ничего не меняется (`difficulty` — строка).

- [ ] **Step 6: `importer.py`** — в `validate_against_pool` после проверки subblock:
```python
    if node.difficulty not in pool.level_ids:
        raise ValueError(
            f"difficulty '{node.difficulty}' is not declared in pool '{pool.id}' "
            f"(allowed: {', '.join(l.id for l in pool.levels)})"
        )
```

- [ ] **Step 7: `sampler.py`** — удалить `LEVELS`; `matrix_order(nodes, block_order, sub_order, level_order: List[str])`:
```python
        d = level_order.index(n.difficulty) if n.difficulty in level_order else len(level_order)
```
Докстринг: «раздел → под-колонка → уровень (порядок из pool.levels) → id».

- [ ] **Step 8: `seed.py`** — в `seed_pool_if_empty` в dict конфига добавить `"levels": json.loads(levels_to_json(pool.levels))` (импорт `levels_to_json`).

- [ ] **Step 9: `main.py`**
- `NodeCreate.difficulty: str = Field(min_length=1)` (без дефолта); `NodeUpdate.difficulty: Optional[str] = None`.
- `PoolCreate.levels: Optional[List[dict]] = None`; `PoolUpdate.levels: Optional[List[dict]] = None`.
- Хелперы рядом с `_blocks_or_422`:
```python
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
```
- `create_pool`: при `preset` — `levels = json.loads(levels_to_json(preset.levels))`, иначе `levels = _levels_or_422(body.levels, ()) if body.levels is not None else json.loads(levels_to_json(DEFAULT_LEVELS))`; передать `levels=levels` в `db.create_pool`.
- `update_pool`: `if body.levels is not None: fields["levels"] = _levels_or_422(body.levels, _pool_or_404(request, pool_id).levels)`.
- `create_node` (строка ~527): перед сборкой `Node` — `_difficulty_or_422(pool, body.difficulty)`. `update_node` (~551): если `difficulty` передан — `_difficulty_or_422(pool_of_node, ...)` (пул ноды — `_pool_or_404(request, existing["pool"])`); и **`source="user"`** вместо `existing.get("source", "user")` с комментарием «правка из UI делает ноду пользовательской: файлы content/ её больше не перетирают (см. sync.py)».
- Вызов `matrix_order(...)` (~666): добавить `level_order=[l.id for l in pool.levels]`.
- Импорты: `DEFAULT_LEVELS, levels_to_json, normalize_levels, parse_levels` из `.pools`.

- [ ] **Step 10: Тесты зелёные**

Run: `pytest -q`
Expected: все старые + `test_levels.py` зелёные. Если `test_nodes.py`/`test_people.py` создают ноды без `difficulty` — добавить `"difficulty": "middle"` в их фикстуры (DE-пул на дефолтных уровнях).

- [ ] **Step 11: Ground truth** — `pytest tests/test_app.py::test_every_pool_imports_without_errors -q` (все три пула импортируются на дефолтных уровнях), `git diff --stat content/` пуст.

- [ ] **Step 12: Commit**
```bash
git add backend/ && git commit -m "feat(levels): уровни сложности — данные направления (pool.yaml levels → pools.levels), валидация по пулу, миграция с прежней четвёркой"
```

---

### Task 2: Бэкенд — `sync.py`, `POST /api/pools/sync`, старт через sync

**Files:**
- Create: `backend/app/sync.py`
- Modify: `backend/app/db.py` (`set_pool_config`, `list_node_ids`)
- Modify: `backend/app/main.py` (старт, ручка)
- Modify: `backend/app/seed.py` (докстринг: используется тестами, старт — sync)
- Test: `backend/tests/test_sync.py`

**Interfaces:**
- Produces: `sync.sync_pools(db, tenant_id, content_dir) -> dict` с ключами `created: [pool_id]`, `updated: [pool_id]`, `nodes_upserted: int`, `hidden: [node_id]`, `conflicts: [node_id]`, `errors: [{file, error}]`; `POST /api/pools/sync` (owner) → тот же dict; `db.set_pool_config(tenant, pool_id, cfg)`; `db.list_node_ids(tenant, pool, source=None, hidden=None) -> List[str]`.
- Consumes: Task 1 (`levels_to_json`, `PoolCfg.levels`).

- [ ] **Step 1: Тесты (падают)** — `backend/tests/test_sync.py`:
```python
"""Синхронизация content/ → БД: создать/обновить направление, upsert seed-нод, спрятать исчезнувшие,
не трогать user-ноды."""

from pathlib import Path

from app.db import Database
from app.sync import sync_pools

POOL = """\
id: demo
label: Demo
description: d1
blocks:
  - { id: a, label: A, color: "#111111", weight: 1 }
levels:
  - { id: intro, label: I }
  - { id: deep,  label: D }
"""


def _card(root: Path, nid: str, title: str = "T", difficulty: str = "intro") -> None:
    (root / "demo" / "a").mkdir(parents=True, exist_ok=True)
    (root / "demo" / "a" / f"{nid}.md").write_text(
        f"---\nid: {nid}\nblock: a\ndifficulty: {difficulty}\ntopic: t\ntitle: {title}\ntags: [sql]\n---\n## Вопрос\nQ?\n## Ответ\nA\n",
        encoding="utf-8",
    )


def _content(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "pool.yaml").write_text(POOL, encoding="utf-8")
    _card(root, "demo-01")
    _card(root, "demo-02", difficulty="deep")
    return root


def test_sync_creates_pool_and_nodes(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    rep = sync_pools(db, "t", _content(tmp_path))
    assert rep["created"] == ["demo"] and rep["nodes_upserted"] == 2 and rep["errors"] == []
    assert db.get_pool("t", "demo")["levels"] == [{"id": "intro", "label": "I"}, {"id": "deep", "label": "D"}]
    assert db.get_node("t", "demo-01")["source"] == "seed"


def test_sync_updates_config_and_nodes_hides_missing_keeps_user(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    # правка файла, удаление файла, новая карточка, user-нода с чужим id
    _card(root, "demo-01", title="T2")
    (root / "demo" / "a" / "demo-02.md").unlink()
    _card(root, "demo-03")
    db.upsert_node("t", {"id": "demo-04", "pool": "demo", "block": "a", "topic": "t", "difficulty": "intro", "question": "q"}, source="user")
    _card(root, "demo-04", title="из файла")
    (root / "demo" / "pool.yaml").write_text(POOL.replace("description: d1", "description: d2"), encoding="utf-8")
    rep = sync_pools(db, "t", root)
    assert rep["updated"] == ["demo"] and rep["hidden"] == ["demo-02"] and rep["conflicts"] == ["demo-04"]
    assert db.get_pool("t", "demo")["description"] == "d2"
    assert db.get_node("t", "demo-01")["title"] == "T2"
    assert db.get_node("t", "demo-02")["hidden"] is True
    assert db.get_node("t", "demo-03")["source"] == "seed"
    assert db.get_node("t", "demo-04")["title"] is None  # user-нода не перетёрта
    # повтор — идемпотентен: ничего нового не прячется
    assert sync_pools(db, "t", root)["hidden"] == []


def test_sync_skips_tombstone_and_reports_bad_files(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    db.delete_pool("t", "demo")
    (root / "demo" / "a" / "bad.md").write_text("---\nid: bad\nblock: zzz\ndifficulty: intro\ntopic: t\n---\nQ", encoding="utf-8")
    rep = sync_pools(db, "t", root)
    assert rep["created"] == [] and rep["updated"] == [] and rep["nodes_upserted"] == 0
    assert db.list_pools("t") == []


def test_api_sync_requires_owner_and_returns_report():
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app

    c = TestClient(app)
    assert c.post("/api/pools/sync").status_code == 401
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    r = c.post("/api/pools/sync")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"created", "updated", "nodes_upserted", "hidden", "conflicts", "errors"}
    assert body["errors"] == []
```

- [ ] **Step 2: Запустить — падают** (`ModuleNotFoundError: app.sync`).

- [ ] **Step 3: `db.py` — два метода** (рядом с `update_pool` и `list_nodes`):
```python
    def set_pool_config(self, tenant_id: str, pool_id: str, cfg: Dict) -> None:
        """Конфиг направления из файлов (sync): label/description/blocks/levels без побочных удалений
        вопросов — в отличие от update_pool, где смена колонок/уровней из UI режет вопросы."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE pools SET label = ?, description = ?, blocks = ?, levels = ?, updated_at = ? "
                "WHERE tenant_id = ? AND id = ?",
                (cfg["label"], cfg.get("description") or "", json.dumps(cfg["blocks"], ensure_ascii=False),
                 json.dumps(cfg["levels"], ensure_ascii=False), _now(), tenant_id, pool_id),
            )

    def list_node_ids(self, tenant_id: str, pool: str, source: Optional[str] = None, hidden: Optional[bool] = None) -> List[str]:
        sql, args = "SELECT id FROM nodes WHERE tenant_id = ? AND pool = ?", [tenant_id, pool]
        if source is not None:
            sql += " AND source = ?"
            args.append(source)
        if hidden is not None:
            sql += " AND hidden = ?"
            args.append(int(hidden))
        with self._conn() as conn:
            return [r["id"] for r in conn.execute(sql + " ORDER BY id", args).fetchall()]
```

- [ ] **Step 4: `sync.py`**
```python
"""Синхронизация content/ → БД: направления и seed-ноды из файлов.

Источник правды для вопросов — БД (UI их правит), но файлы content/ — способ массово завозить
и перегенерировать темы (скилл interview-topic). Поэтому: seed-ноды upsert-ятся из файлов по id,
пользовательские (source='user') — не трогаются (конфликт id — в отчёт), исчезнувшие из файлов
seed-ноды прячутся (на них могут ссылаться оценки), скрытые вручную не разворачиваются.
Конфиг направления обновляется без каскадных удалений (см. db.set_pool_config).
Вызывается при старте сервера и по POST /api/pools/sync.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .db import Database
from .importer import load_pool_content
from .pools import PoolCfg, blocks_to_json, levels_to_json, load_pools


def _cfg(pool: PoolCfg) -> Dict:
    return {
        "id": pool.id,
        "label": pool.label,
        "description": pool.description,
        "blocks": json.loads(blocks_to_json(pool.blocks)),
        "levels": json.loads(levels_to_json(pool.levels)),
    }


def sync_pool(db: Database, tenant_id: str, pool: PoolCfg, report: Dict) -> None:
    """Одно направление: конфиг, ноды, скрытие исчезнувших. Tombstone — пропуск целиком."""
    existing = db.get_pool(tenant_id, pool.id)
    if existing is not None and existing["deleted_at"] is not None:
        return
    if existing is None:
        db.upsert_pool_seed(tenant_id, _cfg(pool))
        report["created"].append(pool.id)
    else:
        db.set_pool_config(tenant_id, pool.id, _cfg(pool))
        report["updated"].append(pool.id)

    nodes, errors = load_pool_content(pool)
    report["errors"].extend({"file": e.file, "error": e.error} for e in errors)
    user_ids = set(db.list_node_ids(tenant_id, pool.id, source="user"))
    file_ids: List[str] = []
    for node in nodes:
        if node.id in user_ids:
            report["conflicts"].append(node.id)
            continue
        db.upsert_node(tenant_id, node.model_dump(), source="seed")
        report["nodes_upserted"] += 1
        file_ids.append(node.id)
    # seed-ноды, которых больше нет в файлах, — спрятать (один раз: уже скрытые не считаем)
    for nid in db.list_node_ids(tenant_id, pool.id, source="seed", hidden=False):
        if nid not in file_ids and nid not in user_ids:
            db.set_node_hidden(tenant_id, nid, True)
            report["hidden"].append(nid)


def sync_pools(db: Database, tenant_id: str, content_dir: Path) -> Dict:
    """Все каталоги с pool.yaml в content_dir. Возвращает сводку для лога/ответа API."""
    report: Dict = {"created": [], "updated": [], "nodes_upserted": 0, "hidden": [], "conflicts": [], "errors": []}
    db.ensure_tenant(tenant_id)
    for pool in load_pools(content_dir).values():
        sync_pool(db, tenant_id, pool, report)
    return report
```
Примечание к тесту `test_sync_updates_…`: user-нода `demo-04` есть в файлах, но её нет в `file_ids` — она не спрячется, потому что `list_node_ids(source="seed")` её не вернёт.

- [ ] **Step 5: `main.py`** — старт: заменить цикл `for _pool in _CONTENT_POOLS.values(): seed_pool_if_empty(...)` на
```python
_sync = sync_pools(db, resolve_tenant(), CONTENT_DIR)
log.info("content sync: created=%s updated=%s nodes=%d hidden=%d conflicts=%d errors=%d",
         _sync["created"], _sync["updated"], _sync["nodes_upserted"], len(_sync["hidden"]), len(_sync["conflicts"]), len(_sync["errors"]))
if _sync["errors"]:
    log.warning("content import errors: %s", _sync["errors"])
```
(`_CONTENT_POOLS` и предупреждение «no pools found» оставить.) Ручка — перед `@app.get("/api/graph")`:
```python
@app.post("/api/pools/sync")
def sync_content(request: Request, _owner: dict = Depends(require_owner)) -> dict:
    """Перечитать content/: новые направления, обновлённые конфиги и seed-ноды; user-ноды не трогаются."""
    return sync_pools(db, resolve_tenant(request), CONTENT_DIR)
```
Порядок регистрации важен: `POST /api/pools/sync` должен стоять **до** `@app.post("/api/pools")`? Нет — разные пути; но `PUT /api/pools/{pool_id}` не конфликтует с POST. Оставить рядом с остальными pools-ручками.

- [ ] **Step 6: Тесты зелёные** — `pytest -q`. Тесты `test_seed_does_not_resurrect_deleted_pool` и `test_people` продолжают использовать `seed_pool_if_empty` — функция остаётся (докстринг: «сид одного пула, используется тестами; старт сервера — sync.sync_pools»).

- [ ] **Step 7: Commit**
```bash
git add backend/ && git commit -m "feat(sync): content/ → БД без рестарта — POST /api/pools/sync и старт через sync_pools; user-ноды не перетираются, исчезнувшие прячутся"
```

---

### Task 3: Фронт — уровни из `pool.levels` вместо `DIFFS`/`DIFF_COLOR`

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/layout.ts`, `frontend/src/api.ts`
- Modify: `frontend/src/components/BandsNode.tsx`, `QuestionNode.tsx`, `DetailDrawer.tsx`, `AddQuestionModal.tsx`, `BankBrowser.tsx`
- Modify: `frontend/src/pages/BoardPage.tsx`, `SetupPage.tsx`, `frontend/src/report.ts`
- Modify: `frontend/src/styles.css:254-257` (удалить)

**Interfaces:**
- Produces: `LevelCfg {id,label}`, `PoolConfig.levels: LevelCfg[]`, `levelOrder(pool): string[]`, `levelLabel(pool,id): string`, `levelColor(pool,id): string`, `LEVEL_PALETTE`; `Band.color`.
- Consumes: `GET /api/pools` с `levels` (Task 1).

- [ ] **Step 1: `types.ts`**
- `export type Difficulty = string;` (комментарий: «уровень — строка, список задаёт pool.levels»).
- `export interface LevelCfg { id: string; label: string }`; в `PoolConfig` — `levels: LevelCfg[];`.
- Удалить `DIFF_LABEL` и `DIFF_COLOR`. Добавить:
```ts
// Палитра уровней по индексу (снизу — легче, сверху — сложнее); первые четыре — прежние цвета
// base/junior/middle/senior, поэтому пулы на дефолтной четвёрке выглядят как раньше.
export const LEVEL_PALETTE = ["#1e40af", "#166534", "#854d0e", "#991b1b", "#6d28d9", "#0e7490", "#be185d", "#374151"];

export function levelOrder(pool: PoolConfig): string[] {
  return pool.levels.map((l) => l.id);
}
export function levelLabel(pool: PoolConfig, level: string): string {
  return pool.levels.find((l) => l.id === level)?.label ?? level;
}
export function levelColor(pool: PoolConfig, level: string): string {
  const i = pool.levels.findIndex((l) => l.id === level);
  return i >= 0 ? LEVEL_PALETTE[i % LEVEL_PALETTE.length] : FALLBACK_COLOR;
}
```
- В `api.ts`: `BlockDraft` остаётся; добавить `export interface LevelDraft { uid?: string; id?: string; label: string }`; `createPool`/`updatePool` принимают `levels?: LevelDraft[]`; добавить `syncPools: () => fetch(\`${BASE}/pools/sync\`, { method: "POST" }).then(json<SyncReport>)` с `export interface SyncReport { created: string[]; updated: string[]; nodes_upserted: number; hidden: string[]; conflicts: string[]; errors: { file: string; error: string }[] }`.

- [ ] **Step 2: `layout.ts`** — удалить `DIFFS`, `DIFF_LABEL_FULL`, импорт `Difficulty`; `Band` получает `color: string`; в `swimlaneLayout` вместо `DIFFS` — `const levels = levelOrder(pool);` везде (`for (const d of levels)`); `bands`:
```ts
  const bands: Band[] = levels.map((d) => ({
    difficulty: d,
    y: bandTop[d],
    height: bandHeight[d],
    label: levelLabel(pool, d).toUpperCase(),
    color: levelColor(pool, d),
  }));
```
Ноды с уровнем вне списка (старый контент) — добавить в `levels` следом по алфавиту, как делается для блоков:
```ts
  const levels: string[] = [...levelOrder(pool)];
  for (const n of [...nodes].sort((a, c) => a.difficulty.localeCompare(c.difficulty)))
    if (!levels.includes(n.difficulty)) levels.push(n.difficulty);
```

- [ ] **Step 3: Компоненты**
- `BandsNode.tsx`: `const color = b.color;` — импорт `DIFF_COLOR`/`Difficulty` убрать.
- `QuestionNode.tsx:42`: плашка уровня — `<span className="qnode__diff" style={{ background: hexA(levelColor(pool, node.difficulty), 0.15), color: levelColor(pool, node.difficulty) }}>{levelLabel(pool, node.difficulty)}</span>`; `pool` приходит в `data` ноды (проверить, как QuestionNode получает `pool`; если нет — прокинуть через `data.pool` в `buildNodes` BoardPage). `styles.css:254-257` удалить (базовый стиль `.qnode__diff` остаётся).
- `DetailDrawer.tsx`: `DIFF_OPTS` → `levelOrder(pool)`; `<option>` показывает `levelLabel(pool, d)`; тип `Difficulty` → `string`; дефолт драфта — `pool.levels[0]?.id ?? ""`.
- `AddQuestionModal.tsx`: принять проп `pool: PoolConfig` (BoardPage передаёт), `levelOrder(pool).map(...)` с `levelLabel`; дефолт select — первый уровень.
- `BankBrowser.tsx`: `DIFFS` → `levelOrder(pool)`, `DIFF_COLOR[d]` → `levelColor(pool, d)`, подпись чипа — `levelLabel(pool, d)`, `drank` по `levelOrder(pool).indexOf`.
- `BoardPage.tsx`: `ALL_DIFFS` из константы → `useMemo(() => Object.fromEntries(levelOrder(pool).map((d) => [d, true])), [pool])`; `activeDiffs` инициализируется от него и **сбрасывается при смене пула** (`useEffect` по `pool.id`); строки 811, 927, 1204–1215 — `levelOrder(pool)`, `levelColor(pool, d)`, подпись `levelLabel(pool, d)`; `toggleDiff(d: string)`.
- `SetupPage.tsx`: `DIFFS` → `levelOrder(pool)` (стр. 34–35, 100, 105, 191), тип `Record<string, boolean>`, подписи чекбоксов — `levelLabel`.
- `report.ts`: `drank` по `levelOrder(pool).indexOf`, цвет — `levelColor(pool, n.difficulty)`, текст — `levelLabel(pool, n.difficulty)` (строки 67, 91, 226, 267); импорт `DIFFS`/`DIFF_COLOR` убрать.

- [ ] **Step 4: Гейт** — `cd frontend && npm run build` (tsc найдёт все оставшиеся `DIFFS`/`DIFF_COLOR`), `npm run i18n:check`, `grep -rn 'DIFFS\|DIFF_COLOR\|DIFF_LABEL' src` → пусто.

- [ ] **Step 5: Живой гейт** — сервер `./run.sh dev` (:8001), `npm run smoke` с `SMOKE_BASE=http://localhost:8001` (см. `smoke.mjs`, как задаётся адрес) — 4 полосы уровней на DE-доске, тест проходит без правок.

- [ ] **Step 6: Commit**
```bash
git add frontend/src && git commit -m "feat(levels): фронт читает уровни из pool.levels — ряды, подписи, цвета, фильтры, отчёт; DIFFS/DIFF_COLOR удалены"
```

---

### Task 4: Редактор уровней в форме направления + «Обновить из файлов» (инлайн)

**Files:**
- Create: `frontend/src/components/LevelsEditor.tsx`
- Modify: `frontend/src/components/PoolFormModal.tsx` (второй список под колонками; `levels` в `createPool`/`updatePool`; при создании без пресета — дефолтная четвёрка в драфте)
- Modify: `frontend/src/pages/HomePage.tsx` (пункт меню `•••` «Обновить из файлов» → `api.syncPools()` → тост со сводкой; показывать только owner'у)
- Modify: `frontend/src/i18n/en.ts` (новые ключи)

**Interfaces:**
- Consumes: `LevelDraft`, `api.syncPools`, `PoolConfig.levels` (Task 3), `PUT /api/pools` с `levels` (Task 1).

- [ ] **Step 1: `LevelsEditor.tsx`** — простой список (без DnD): ряд = название · ↑ · ↓ · ×; кнопка «+ Уровень»; валидность — 2–8 рядов с непустыми названиями (`levelsValid`); при удалении уровня с `id` и `nodeCounts[id] > 0` — `confirm(t("Удалить уровень «{label}» и его вопросы ({n})?"))`. Порядок = сложность по возрастанию, подпись сверху «легче → сложнее».
- [ ] **Step 2: `PoolFormModal.tsx`** — секция «Уровни» под «Разделы»; `nodeCounts` по уровням считать из графа пула (как для разделов); кнопка сохранения disabled, если `!blocksValid || !levelsValid`.
- [ ] **Step 3: `HomePage.tsx`** — пункт меню и тост: `t("Обновлено из файлов: направлений {p}, вопросов {n}, скрыто {h}, конфликтов {c}")`; при `errors.length` — второй тост с первым текстом ошибки и числом остальных.
- [ ] **Step 4: Гейт** — `npm run build`, `npm run i18n:check`; руками: создать направление с тремя уровнями → доска с тремя рядами; «Обновить из файлов» после правки `content/system-analyst/.../*.md` (title) → карточка обновилась без рестарта; вернуть файл `git checkout -- content/`.
- [ ] **Step 5: Commit**
```bash
git add frontend/src && git commit -m "feat(levels): редактор уровней в форме направления, «Обновить из файлов» в меню направления"
```

---

### Task 5: Гейты ветки, документация, PR

- [ ] **Step 1:** `pytest -q`, `npm run build`, `npm run i18n:check`, `npm run smoke` (сервер), `git diff --stat dev -- content/` пуст.
- [ ] **Step 2: Документация** — `CLAUDE.md` и `AGENTS.md`: «сложность → уровни задаются `levels` в `pool.yaml` (2–8), без `levels` — base/junior/middle/senior; `POST /api/pools/sync` подхватывает `content/` без рестарта; правка ноды из UI делает её `source=user`». `README.md` — абзац про `levels` там, где описан `pool.yaml`. Спека A: отметить решения «UI-правка → user», «sync без каскадов».
- [ ] **Step 3: Финальное ревью ветки** — `review-agent` по `git diff dev...HEAD`; дефекты — правятся.
- [ ] **Step 4: PR в `dev`** — `gh pr create --base dev --title "Уровни как данные направления + синхронизация content/ без рестарта (подпроект A)"`; тело — ссылка на спеку/план, что сделано, гейты. CI зелёный → merge squash.

---

## Self-review

- **Spec coverage:** A1 модель → T1 Steps 3–8; A2 API → T1 Step 9, T2 Step 5; A3 фронт → T3, T4; A4 sync → T2; A5 гейты → T1 Step 10–11, T2 Step 6, T3 Steps 4–5, T5. Уточнения (UI-правка → `user`; sync без каскадов; скрытые не разворачиваются) → Global Constraints + T5 Step 2.
- **Placeholders:** нет; фронтовые правки даны по файлу и строке с заменой; компоненты Task 4 описаны по поведению и валидности — код пишет исполнитель по образцу `BlocksEditor.tsx`.
- **Consistency:** `levels`, `level_ids`, `levelOrder/levelLabel/levelColor`, `LEVEL_PALETTE`, `DEFAULT_LEVELS`, `sync_pools` и ключи отчёта (`created, updated, nodes_upserted, hidden, conflicts, errors`) — одинаковы в T1–T5 и в тестах.
