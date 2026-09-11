"""CRUD API для MCP (spec 2026-09-11-api-mcp): направление по id, карточки со всеми полями и переносом,
фильтры списка, топики, словарь тегов, права."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import OWNER_EMAIL, OWNER_PASSWORD, app


def _login(c: TestClient, email: str, password: str):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def _owner() -> TestClient:
    c = TestClient(app)
    assert _login(c, OWNER_EMAIL, OWNER_PASSWORD).status_code == 200
    return c


def _viewer(owner: TestClient) -> TestClient:
    email = f"crud-viewer-{uuid.uuid4().hex[:8]}@x.test"
    pw = owner.post("/api/users", json={"email": email}).json()["password"]
    c = TestClient(app)
    assert _login(c, email, pw).status_code == 200
    return c


BLOCKS = [
    {"label": "Alpha", "color": "#2563eb", "subblocks": [{"label": "One"}, {"label": "Two"}]},
    {"label": "Beta", "color": "#16a34a"},
]


@pytest.fixture()
def pool():
    """Направление с колонками alpha (one, two) и beta и уровнями по умолчанию; удаляется после теста."""
    owner = _owner()
    pid = f"crud-{uuid.uuid4().hex[:8]}"
    r = owner.post("/api/pools", json={"id": pid, "label": f"CRUD {pid}", "blocks": BLOCKS})
    assert r.status_code == 200, r.text
    yield owner, r.json()
    owner.delete(f"/api/pools/{pid}")


def _node(owner: TestClient, pid: str, **kw) -> dict:
    payload = {"pool": pid, "block": "alpha", "topic": "t1", "difficulty": "base", "question": "Что такое X?"}
    payload.update(kw)
    r = owner.post("/api/nodes", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# --- направления ---


def test_get_pool_by_id(pool):
    owner, p = pool
    r = owner.get(f"/api/pools/{p['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == p["id"] and [b["id"] for b in body["blocks"]] == ["alpha", "beta"]
    assert [s["id"] for s in body["blocks"][0]["subblocks"]] == ["one", "two"]
    assert "progress" in body and "counts" in body
    assert owner.get("/api/pools/no-such-pool").status_code == 404
    assert TestClient(app).get(f"/api/pools/{p['id']}").status_code == 401


def test_create_pool_with_explicit_id(pool):
    owner, p = pool
    dup = owner.post("/api/pools", json={"id": p["id"], "label": "Again", "blocks": BLOCKS})
    assert dup.status_code == 409
    bad = owner.post("/api/pools", json={"id": "Bad Id", "label": "X", "blocks": BLOCKS})
    assert bad.status_code == 422


# --- карточки ---


def test_create_node_with_all_fields(pool):
    owner, p = pool
    nid = f"{p['id']}-alpha-01"
    body = _node(
        owner, p["id"], id=nid, subblock="two", kind="task", weight=3, title="Заголовок карточки",
        answer="Ответ", starterCode="SELECT 1", rubric=["критерий"], tags=["SQL", "sql", "storage"],
    )
    assert body["id"] == nid
    got = owner.get(f"/api/nodes/{nid}")
    assert got.status_code == 200
    node = got.json()
    assert (node["subblock"], node["kind"], node["weight"]) == ("two", "task", 3)
    assert node["starterCode"] == "SELECT 1" and node["rubric"] == ["критерий"]
    assert node["tags"] == ["sql", "storage"]  # нижний регистр, дубли схлопнуты
    assert node["hidden"] is False and node["source"] == "user"
    assert owner.post("/api/nodes", json={"pool": p["id"], "id": nid, "block": "alpha", "topic": "t",
                                          "difficulty": "base", "question": "q"}).status_code == 409


def test_create_node_normalizes_tags(pool):
    owner, p = pool
    node = _node(owner, p["id"], tags=["Data Modeling", "data_modeling", " SQL "])
    assert node["tags"] == ["data-modeling", "sql"]


@pytest.mark.parametrize("tags", [["не тег"], ["tag!"], ["a", "b", "c", "d", "e", "f"]])
def test_create_node_rejects_bad_tags(pool, tags):
    owner, p = pool
    r = owner.post("/api/nodes", json={"pool": p["id"], "block": "alpha", "topic": "t", "difficulty": "base",
                                       "question": "q", "tags": tags})
    assert r.status_code == 422


def test_create_node_subblock_must_belong_to_block(pool):
    owner, p = pool
    r = owner.post("/api/nodes", json={"pool": p["id"], "block": "beta", "subblock": "one", "topic": "t",
                                       "difficulty": "base", "question": "q"})
    assert r.status_code == 400


def test_get_missing_node_404(pool):
    owner, _ = pool
    assert owner.get("/api/nodes/does-not-exist").status_code == 404


def test_list_nodes_filters(pool):
    owner, p = pool
    a = _node(owner, p["id"], subblock="one", topic="joins", tags=["sql"], title="Джойны")["id"]
    b = _node(owner, p["id"], block="beta", difficulty="senior", topic="plans", tags=["optimization"],
              question="Как читать план запроса?")["id"]
    c = _node(owner, p["id"], kind="task", topic="joins", question="Напишите запрос")["id"]
    pid = p["id"]

    def ids(query: str = "") -> set:
        r = owner.get(f"/api/nodes?pool={pid}{query}")
        assert r.status_code == 200, r.text
        return {n["id"] for n in r.json()}

    assert ids() == {a, b, c}
    assert ids("&block=beta") == {b}
    assert ids("&subblock=one") == {a}
    assert ids("&difficulty=senior") == {b}
    assert ids("&topic=joins") == {a, c}
    assert ids("&tag=sql") == {a}
    assert ids("&kind=task") == {c}
    assert ids("&q=%D0%BF%D0%BB%D0%B0%D0%BD") == {b}  # «план» — поиск по тексту без учёта регистра
    main_module.db.tombstone_node("default", a)
    assert ids() == {b, c}
    assert ids("&include_hidden=true") == {a, b, c}
    assert owner.get("/api/nodes?pool=no-such-pool").status_code == 404
    assert owner.get("/api/nodes").status_code == 422


def test_update_node_moves_and_edits_every_field(pool):
    owner, p = pool
    nid = _node(owner, p["id"], subblock="one", title="Старый заголовок")["id"]
    r = owner.put(f"/api/nodes/{nid}", json={
        "block": "beta", "difficulty": "senior", "topic": "moved", "tags": ["storage"], "kind": "task",
        "weight": 5, "rubric": ["r1"], "starterCode": "print(1)", "answer": "Новый ответ",
    })
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == nid
    node = r.json()["node"]
    assert (node["block"], node["subblock"], node["difficulty"], node["topic"]) == ("beta", None, "senior", "moved")
    assert (node["kind"], node["weight"], node["rubric"], node["starterCode"]) == ("task", 5, ["r1"], "print(1)")
    assert node["tags"] == ["storage"] and node["answer"] == "Новый ответ"
    cleared = owner.put(f"/api/nodes/{nid}", json={"title": "", "starterCode": ""}).json()["node"]
    assert cleared["title"] is None and cleared["starterCode"] is None
    back = owner.put(f"/api/nodes/{nid}", json={"block": "alpha", "subblock": "two"}).json()["node"]
    assert (back["block"], back["subblock"]) == ("alpha", "two")
    assert owner.put(f"/api/nodes/{nid}", json={"subblock": ""}).json()["node"]["subblock"] is None
    assert owner.put(f"/api/nodes/{nid}", json={"block": "gamma"}).status_code == 422
    assert owner.put(f"/api/nodes/{nid}", json={"subblock": "nope"}).status_code == 422
    assert owner.put(f"/api/nodes/{nid}", json={"tags": ["плохой тег"]}).status_code == 422


def test_update_node_moves_between_pools(pool):
    owner, p = pool
    other = owner.post("/api/pools", json={"label": f"Other {uuid.uuid4().hex[:6]}", "blocks": [
        {"label": "Alpha", "color": "#2563eb"}]}).json()
    try:
        nid = _node(owner, p["id"], subblock="one")["id"]
        moved = owner.put(f"/api/nodes/{nid}", json={"pool": other["id"]})
        assert moved.status_code == 200, moved.text
        assert (moved.json()["node"]["pool"], moved.json()["node"]["subblock"]) == (other["id"], None)
        assert owner.put(f"/api/nodes/{nid}", json={"pool": "no-such-pool"}).status_code == 404
    finally:
        owner.delete(f"/api/pools/{other['id']}")


# --- топики ---


def test_topics_list_rename_delete(pool):
    owner, p = pool
    pid = p["id"]
    _node(owner, pid, topic="joins")
    _node(owner, pid, topic="joins")
    _node(owner, pid, block="beta", topic="joins")
    _node(owner, pid, topic="plans")
    topics = owner.get(f"/api/pools/{pid}/topics").json()
    assert {(t["block"], t["topic"]): t["count"] for t in topics} == {
        ("alpha", "joins"): 2, ("alpha", "plans"): 1, ("beta", "joins"): 1}
    assert [t["topic"] for t in owner.get(f"/api/pools/{pid}/topics?block=beta").json()] == ["joins"]

    r = owner.put(f"/api/pools/{pid}/topics/joins", json={"topic": "join-strategies", "block": "alpha"})
    assert r.status_code == 200 and r.json()["renamed"] == 2
    topics = {(t["block"], t["topic"]): t["count"] for t in owner.get(f"/api/pools/{pid}/topics").json()}
    assert topics[("alpha", "join-strategies")] == 2 and topics[("beta", "joins")] == 1
    assert owner.put(f"/api/pools/{pid}/topics/nope", json={"topic": "x"}).status_code == 404
    assert owner.put(f"/api/pools/{pid}/topics/plans", json={"topic": "  "}).status_code == 422

    d = owner.delete(f"/api/pools/{pid}/topics/join-strategies")
    assert d.status_code == 200 and d.json()["count"] == 2
    assert owner.get(f"/api/nodes?pool={pid}&topic=join-strategies").json() == []
    assert owner.delete(f"/api/pools/{pid}/topics/join-strategies").status_code == 404


# --- теги ---


def test_tags_vocabulary_and_usage(pool):
    owner, p = pool
    _node(owner, p["id"], tags=["sql", "storage"])
    _node(owner, p["id"], tags=["sql"])
    body = owner.get(f"/api/tags?pool={p['id']}").json()
    assert "orchestration" in body["concepts"] and len(body["concepts"]) == 17
    assert body["used"][0] == {"tag": "sql", "count": 2}
    assert owner.get("/api/tags").json()["used"] == []


# --- права ---


def test_viewer_reads_but_cannot_write(pool):
    owner, p = pool
    pid = p["id"]
    nid = _node(owner, pid)["id"]
    viewer = _viewer(owner)
    for path in (f"/api/pools/{pid}", f"/api/nodes?pool={pid}", f"/api/nodes/{nid}", f"/api/pools/{pid}/topics",
                 f"/api/tags?pool={pid}"):
        assert viewer.get(path).status_code == 200, path
    assert viewer.post("/api/nodes", json={"pool": pid, "block": "alpha", "topic": "t", "difficulty": "base",
                                           "question": "q"}).status_code == 403
    assert viewer.put(f"/api/nodes/{nid}", json={"topic": "x"}).status_code == 403
    assert viewer.put(f"/api/pools/{pid}/topics/t1", json={"topic": "x"}).status_code == 403
    assert viewer.delete(f"/api/pools/{pid}/topics/t1").status_code == 403
    anon = TestClient(app)
    for path in (f"/api/nodes?pool={pid}", f"/api/nodes/{nid}", f"/api/pools/{pid}/topics", "/api/tags"):
        assert anon.get(path).status_code == 401, path
