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
    rep = sync_pools(db, "t", root)
    assert len(rep["errors"]) == 1 and "bad.md" in rep["errors"][0]["file"]
    assert rep["hidden"] == []
    assert db.get_node("t", "demo-02")["hidden"] is False


def test_sync_unhides_returning_seed_node(tmp_path):
    db = Database(tmp_path / "t.db")
    db.ensure_tenant("t")
    root = _content(tmp_path)
    sync_pools(db, "t", root)
    (root / "demo" / "a" / "demo-02.md").unlink()
    rep = sync_pools(db, "t", root)
    assert rep["hidden"] == ["demo-02"]
    assert db.get_node("t", "demo-02")["hidden"] is True
    _card(root, "demo-02", difficulty="deep")  # вопрос вернулся в файлы
    sync_pools(db, "t", root)
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
    assert set(body) >= {"created", "updated", "nodes_upserted", "hidden", "conflicts", "errors"}
    assert body["errors"] == []
