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


def test_seed_never_overwrites_or_hides_existing(tmp_path):
    """Засев (по умолчанию, в том числе на старте сервера): только новое. Правки в БД, конфиг направления и
    карточки без файлов переживают любой деплой (spec 2026-09-11-content-in-db)."""
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    db.upsert_node("t", {**db.get_node("t", "demo-01"), "title": "ПРАВКА В БД"}, source="seed")
    _card(root, "demo-01", title="Из файла")
    (root / "demo" / "a" / "demo-02.md").unlink()
    _card(root, "demo-03")
    (root / "demo" / "pool.yaml").write_text(POOL.replace("description: d1", "description: d2"), encoding="utf-8")
    rep = sync_pools(db, "t", root)
    assert rep["mode"] == "seed" and rep["created"] == [] and rep["updated"] == ["demo"]
    assert rep["nodes_upserted"] == 1 and rep["skipped"] == 1 and rep["hidden"] == [] and rep["conflicts"] == []
    assert db.get_pool("t", "demo")["description"] == "d1"
    assert db.get_node("t", "demo-01")["title"] == "ПРАВКА В БД"
    assert db.get_node("t", "demo-02")["hidden"] is False
    assert db.get_node("t", "demo-03")["source"] == "seed"


def test_seed_skips_ids_taken_in_other_pools(tmp_path):
    """id карточки уникален в тенанте: засев не переносит чужую карточку в своё направление."""
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    db.upsert_node("t", {"id": "demo-01", "pool": "other", "block": "x", "topic": "t", "difficulty": "d",
                         "question": "q"}, source="user")
    rep = sync_pools(db, "t", _content(tmp_path))
    assert rep["skipped"] == 1 and rep["nodes_upserted"] == 1
    assert db.get_node("t", "demo-01")["pool"] == "other"


def test_update_dry_run_reports_without_writing(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    same = sync_pools(db, "t", root, update=True, dry_run=True)
    assert same["nodes_changed"] == 0 and same["config_changed"] == [] and same["hidden"] == []
    (root / "demo" / "a" / "demo-02.md").unlink()
    _card(root, "demo-01", title="Из файла")
    (root / "demo" / "pool.yaml").write_text(POOL.replace("description: d1", "description: d2"), encoding="utf-8")
    rep = sync_pools(db, "t", root, update=True, dry_run=True)
    assert rep["dry_run"] is True and rep["hidden"] == ["demo-02"] and rep["config_changed"] == ["demo"]
    assert rep["nodes_upserted"] == 1 and rep["nodes_changed"] == 1
    assert db.get_node("t", "demo-02")["hidden"] is False
    assert db.get_node("t", "demo-01")["title"] == "T"
    assert db.get_pool("t", "demo")["description"] == "d1"


def test_update_only_one_pool(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    (root / "other").mkdir()
    (root / "other" / "pool.yaml").write_text(POOL.replace("id: demo", "id: other").replace("label: Demo", "label: Other"),
                                             encoding="utf-8")
    rep = sync_pools(db, "t", root, update=True, only="demo")
    assert rep["created"] == ["demo"] and db.get_pool("t", "other") is None
    import pytest

    from app.sync import UnknownPoolError

    with pytest.raises(UnknownPoolError):
        sync_pools(db, "t", root, only="nope")


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
    rep = sync_pools(db, "t", root, update=True)
    assert rep["updated"] == ["demo"] and rep["hidden"] == ["demo-02"] and rep["conflicts"] == ["demo-04"]
    assert rep["config_changed"] == ["demo"]
    assert db.get_pool("t", "demo")["description"] == "d2"
    assert db.get_node("t", "demo-01")["title"] == "T2"
    assert db.get_node("t", "demo-02")["hidden"] is True
    assert db.get_node("t", "demo-03")["source"] == "seed"
    assert db.get_node("t", "demo-04")["title"] is None  # user-нода не перетёрта
    # повтор — идемпотентен: ничего нового не прячется
    assert sync_pools(db, "t", root, update=True)["hidden"] == []


def test_sync_skips_tombstone(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    db.delete_pool("t", "demo")
    rep = sync_pools(db, "t", root)
    assert rep["created"] == [] and rep["updated"] == [] and rep["nodes_upserted"] == 0
    assert db.list_pools("t") == []


def test_sync_parse_errors_skip_hiding(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    # demo-02 исчезает, но рядом падает bad.md — file_ids неполон, прятать нельзя
    (root / "demo" / "a" / "demo-02.md").unlink()
    (root / "demo" / "a" / "bad.md").write_text(
        "---\nid: bad\nblock: zzz\ndifficulty: intro\ntopic: t\n---\nQ", encoding="utf-8"
    )
    rep = sync_pools(db, "t", root, update=True)
    assert len(rep["errors"]) == 1 and "bad.md" in rep["errors"][0]["file"]
    assert rep["hidden"] == []
    assert db.get_node("t", "demo-02")["hidden"] is False


def test_sync_unhides_returning_seed_node(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    (root / "demo" / "a" / "demo-02.md").unlink()
    rep = sync_pools(db, "t", root, update=True)
    assert rep["hidden"] == ["demo-02"]
    assert db.get_node("t", "demo-02")["hidden"] is True
    _card(root, "demo-02", difficulty="deep")  # вопрос вернулся в файлы
    sync_pools(db, "t", root, update=True)
    assert db.get_node("t", "demo-02")["hidden"] is False


def test_api_graph_excludes_hidden_nodes():
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app
    from app.main import db as main_db

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    r = c.post(
        "/api/nodes",
        json={
            "block": "python",
            "topic": "Hidden smoke",
            "difficulty": "middle",
            "question": "Q?",
            "answer": "A",
        },
    )
    assert r.status_code == 200
    node_id = r.json()["id"]
    try:
        ids = {n["id"] for n in c.get("/api/graph").json()["nodes"]}
        assert node_id in ids
        main_db.set_node_hidden("default", node_id, True)
        ids = {n["id"] for n in c.get("/api/graph").json()["nodes"]}
        assert node_id not in ids
    finally:
        c.delete(f"/api/nodes/{node_id}")


def test_api_sync_requires_owner_and_returns_report():
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app

    c = TestClient(app)
    assert c.post("/api/pools/sync").status_code == 401
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    r = c.post("/api/pools/sync")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"mode", "created", "updated", "nodes_upserted", "skipped", "hidden", "conflicts", "errors"}
    assert body["errors"] == [] and body["mode"] == "seed" and body["hidden"] == []
    dry = c.post("/api/pools/sync?pool=data-engineer&update=true&dry_run=true")
    assert dry.status_code == 200 and dry.json()["mode"] == "update" and dry.json()["dry_run"] is True
    # только что засеянный пресет совпадает с файлами — предпросмотр не находит правок (задачи со starterCode и rubric тоже)
    assert dry.json()["nodes_changed"] == 0 and dry.json()["config_changed"] == [] and dry.json()["hidden"] == []
    assert c.post("/api/pools/sync?pool=no-such-pool").status_code == 404


def test_api_graph_include_hidden_shows_hidden_nodes():
    """Ruling 8: доска в режиме сессии/отчёт грузят граф с include_hidden=1, обычная доска — без."""
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app
    from app.main import db as main_db

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    r = c.post(
        "/api/nodes",
        json={
            "block": "python",
            "topic": "Hidden include_hidden",
            "difficulty": "middle",
            "question": "Q?",
            "answer": "A",
        },
    )
    assert r.status_code == 200
    node_id = r.json()["id"]
    try:
        main_db.set_node_hidden("default", node_id, True)
        ids = {n["id"] for n in c.get("/api/graph?pool=data-engineer").json()["nodes"]}
        assert node_id not in ids
        ids_hidden = {n["id"] for n in c.get("/api/graph?pool=data-engineer&include_hidden=1").json()["nodes"]}
        assert node_id in ids_hidden
    finally:
        c.delete(f"/api/nodes/{node_id}")


def test_edit_node_marks_source_user_and_sync_respects_it():
    """Регрессия блокера: upsert_node не писал source → UI-правка seed-ноды оставалась 'seed'
    и следующий sync откатывал бы её файлом. Теперь source=excluded.source в ON CONFLICT."""
    from fastapi.testclient import TestClient

    from app.main import CONTENT_DIR, OWNER_EMAIL, OWNER_PASSWORD, app
    from app.main import db as main_db
    from app.models import Node
    from app.sync import sync_pools

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    node_id = "acid-01"
    original = main_db.get_node("default", node_id)
    assert original is not None and original["source"] == "seed"
    try:
        r = c.put(f"/api/nodes/{node_id}", json={"title": "ПРАВКА ИЗ UI"})
        assert r.status_code == 200
        assert main_db.get_node("default", node_id)["source"] == "user"
        rep = sync_pools(main_db, "default", CONTENT_DIR, update=True, only="data-engineer")
        assert main_db.get_node("default", node_id)["title"] == "ПРАВКА ИЗ UI"
        assert node_id in rep["conflicts"]
    finally:
        restore = {k: v for k, v in original.items() if k in Node.model_fields}
        main_db.upsert_node("default", restore, source="seed")


def test_delete_seed_node_tombstones_and_sync_keeps_it_hidden():
    """Ruling 7: DELETE seed-ноды из UI — tombstone (hidden=1, source='user'), не воскресает
    следующим sync и не считается конфликтом id."""
    from fastapi.testclient import TestClient

    from app.main import CONTENT_DIR, OWNER_EMAIL, OWNER_PASSWORD, app
    from app.main import db as main_db
    from app.models import Node
    from app.sync import sync_pools

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    node_id = "acid-01"
    original = main_db.get_node("default", node_id)
    assert original is not None and original["source"] == "seed"
    try:
        r = c.delete(f"/api/nodes/{node_id}")
        assert r.status_code == 200
        assert r.json() == {"deleted": node_id, "tombstoned": True}
        after = main_db.get_node("default", node_id)
        assert after["hidden"] is True and after["source"] == "user"
        ids = {n["id"] for n in c.get("/api/graph?pool=data-engineer").json()["nodes"]}
        assert node_id not in ids

        rep = sync_pools(main_db, "default", CONTENT_DIR, update=True, only="data-engineer")
        again = main_db.get_node("default", node_id)
        assert again["hidden"] is True
        assert again["title"] == original["title"]  # sync не перезаписала tombstone файлом
        assert node_id not in rep["conflicts"]  # не глобальное равенство: БД общая на прогон, порядок тестов случайный
    finally:
        restore = {k: v for k, v in original.items() if k in Node.model_fields}
        main_db.upsert_node("default", restore, source="seed")
        main_db.set_node_hidden("default", node_id, False)


def test_sync_carries_and_clears_flags(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    (root / "demo" / "pool.yaml").write_text(POOL + "demo: true\nlang: en\ntranslation_of: demo-ru\n", encoding="utf-8")
    sync_pools(db, "t", root)
    row = db.get_pool("t", "demo")
    assert (row["demo"], row["lang"], row["translation_of"]) == (True, "en", "demo-ru")
    (root / "demo" / "pool.yaml").write_text(POOL, encoding="utf-8")
    sync_pools(db, "t", root)  # засев не трогает флаги существующего направления
    row = db.get_pool("t", "demo")
    assert (row["demo"], row["lang"], row["translation_of"]) == (True, "en", "demo-ru")
    sync_pools(db, "t", root, update=True)
    row = db.get_pool("t", "demo")
    assert (row["demo"], row["lang"], row["translation_of"]) == (False, "ru", None)


def test_db_migration_adds_pool_flags(tmp_path):
    """Старая БД без столбцов demo/lang/translation_of: миграция добавляет их с дефолтами, повтор — no-op."""
    path = tmp_path / "t.db"
    db = Database(path)
    db.ensure_tenant("t")
    with db._conn() as conn:  # строка pools как в БД до миграции
        for col in ("demo", "lang", "translation_of"):
            conn.execute(f"ALTER TABLE pools DROP COLUMN {col}")
        conn.execute(
            "INSERT INTO pools (tenant_id, id, label, description, blocks, levels, source, created_at, updated_at) "
            "VALUES ('t', 'old', 'Old', '', '[]', '[]', 'seed', 'x', 'x')"
        )
    row = Database(path).get_pool("t", "old")
    assert (row["demo"], row["lang"], row["translation_of"]) == (False, "ru", None)
    row = Database(path).get_pool("t", "old")  # повторное открытие не падает и ничего не меняет
    assert (row["demo"], row["lang"], row["translation_of"]) == (False, "ru", None)
