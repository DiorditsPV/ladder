"""Тесты чек-листа разбора (progress): DAL напрямую + API /api/progress.

Статус карточки — per-user (у каждого свой чек-лист по направлению). DAL-тесты дёргают
app.main.db напрямую (как test_nodes.py::test_hidden_node_excluded_when_requested),
API-тесты — через TestClient, залогинившись owner'ом (паттерн _client() из test_nodes.py).
Каждый тест чистит за собой созданные ноды/статусы, поэтому не зависит от порядка
и не портит общую тестовую БД.
"""

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    return c


def _db():
    import app.main as main_module

    return main_module.db


def _make_node(c: TestClient, **overrides) -> str:
    payload = {"block": "python", "topic": "Progress topic", "difficulty": "middle", "question": "q?"}
    payload.update(overrides)
    r = c.post("/api/nodes", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# --- DAL ---


def test_set_progress_upserts():
    db = _db()
    tenant = "default"
    c = _client()
    node_id = _make_node(c)
    try:
        out = db.set_progress(tenant, "u1", node_id, "review")
        assert out == {"node_id": node_id, "status": "review"}
        out2 = db.set_progress(tenant, "u1", node_id, "known")
        assert out2 == {"node_id": node_id, "status": "known"}
        assert db.get_progress(tenant, "u1", "data-engineer")[node_id] == "known"
    finally:
        db.clear_progress(tenant, "u1", node_id)
        c.delete(f"/api/nodes/{node_id}")


def test_clear_progress_returns_bool():
    db = _db()
    tenant = "default"
    c = _client()
    node_id = _make_node(c)
    try:
        assert db.clear_progress(tenant, "u1", node_id) is False
        db.set_progress(tenant, "u1", node_id, "known")
        assert db.clear_progress(tenant, "u1", node_id) is True
        assert db.clear_progress(tenant, "u1", node_id) is False
    finally:
        c.delete(f"/api/nodes/{node_id}")


def test_progress_isolated_per_user():
    db = _db()
    tenant = "default"
    c = _client()
    node_id = _make_node(c)
    try:
        db.set_progress(tenant, "u1", node_id, "known")
        db.set_progress(tenant, "u2", node_id, "unknown")
        assert db.get_progress(tenant, "u1", "data-engineer")[node_id] == "known"
        assert db.get_progress(tenant, "u2", "data-engineer")[node_id] == "unknown"
    finally:
        db.clear_progress(tenant, "u1", node_id)
        db.clear_progress(tenant, "u2", node_id)
        c.delete(f"/api/nodes/{node_id}")


def test_get_progress_hides_status_of_hidden_node():
    db = _db()
    tenant = "default"
    c = _client()
    node_id = _make_node(c)
    try:
        db.set_progress(tenant, "u1", node_id, "known")
        db.set_node_hidden(tenant, node_id, True)
        # статус скрытой ноды не отдаём, но и не стираем
        assert node_id not in db.get_progress(tenant, "u1", "data-engineer")
        db.set_node_hidden(tenant, node_id, False)
        assert db.get_progress(tenant, "u1", "data-engineer")[node_id] == "known"
    finally:
        db.clear_progress(tenant, "u1", node_id)
        c.delete(f"/api/nodes/{node_id}")


def test_progress_summary_counts_visible_nodes():
    """total = все видимые ноды пула (не зависит от того, есть ли по ним статус);
    known/review/unknown растут по мере простановки статусов."""
    db = _db()
    tenant = "default"
    c = _client()
    node_id = _make_node(c)
    try:
        before = db.progress_summary(tenant, "u1", "data-engineer")
        # count_nodes считает и скрытые ноды — progress_summary.total их не видит, поэтому сверяем
        # с тем же источником, что и он (видимые ноды пула).
        expected_total = len(db.list_nodes(tenant, pool="data-engineer", include_hidden=False))
        assert before["total"] == expected_total  # свежесозданная нода уже видима, но без статуса
        db.set_progress(tenant, "u1", node_id, "known")
        after = db.progress_summary(tenant, "u1", "data-engineer")
        assert after["total"] == expected_total  # total не меняется от простановки статуса
        assert after["known"] == before["known"] + 1
    finally:
        db.clear_progress(tenant, "u1", node_id)
        c.delete(f"/api/nodes/{node_id}")


# --- API ---


def test_put_progress_unknown_node_404():
    c = _client()
    assert c.put("/api/progress/does-not-exist", json={"status": "known"}).status_code == 404


def test_put_progress_invalid_status_422():
    c = _client()
    node_id = _make_node(c)
    try:
        r = c.put(f"/api/progress/{node_id}", json={"status": "meh"})
        assert r.status_code == 422
    finally:
        c.delete(f"/api/nodes/{node_id}")


def test_put_and_get_progress_roundtrip():
    c = _client()
    node_id = _make_node(c, pool="data-engineer")
    try:
        r = c.put(f"/api/progress/{node_id}", json={"status": "review"})
        assert r.status_code == 200, r.text
        assert r.json() == {"node_id": node_id, "status": "review"}
        got = c.get("/api/progress?pool=data-engineer")
        assert got.status_code == 200, got.text
        assert got.json()[node_id] == "review"
    finally:
        c.delete(f"/api/progress/{node_id}")
        c.delete(f"/api/nodes/{node_id}")


def test_get_pools_includes_progress_summary():
    c = _client()
    node_id = _make_node(c, pool="data-engineer")
    try:
        c.put(f"/api/progress/{node_id}", json={"status": "known"})
        pools = {p["id"]: p for p in c.get("/api/pools").json()}
        de = pools["data-engineer"]
        assert "progress" in de
        # counts.nodes считает и скрытые ноды — сверяем total с видимыми нодами графа,
        # как их видит progress_summary.
        visible = len(c.get("/api/graph?pool=data-engineer").json()["nodes"])
        assert de["progress"]["total"] == visible
        assert de["progress"]["known"] >= 1
    finally:
        c.delete(f"/api/progress/{node_id}")
        c.delete(f"/api/nodes/{node_id}")


def test_delete_progress_removes_status():
    c = _client()
    node_id = _make_node(c, pool="data-engineer")
    try:
        c.put(f"/api/progress/{node_id}", json={"status": "known"})
        r = c.delete(f"/api/progress/{node_id}")
        assert r.status_code == 200
        assert r.json() == {"cleared": True}
        assert node_id not in c.get("/api/progress?pool=data-engineer").json()
    finally:
        c.delete(f"/api/nodes/{node_id}")
