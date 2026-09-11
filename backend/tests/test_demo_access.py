"""Демо без входа: анонимно читаются только направления с demo=true (spec 2026-09-11)."""

import re
import uuid

from fastapi.routing import APIRoute
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


def test_anonymous_graph_ignores_include_hidden():
    """Скрытые карточки аноним не видит и с ?include_hidden=true — флаг только для вошедших."""
    owner = _owner()
    demo = _pool(owner, f"Hidden {uuid.uuid4().hex[:6]}")
    try:
        _set_demo(demo["id"], True)
        ids = []
        for q in ("visible?", "hidden?"):
            r = owner.post("/api/nodes", json={
                "pool": demo["id"], "block": demo["blocks"][0]["id"], "topic": "t",
                "difficulty": demo["levels"][0]["id"], "question": q,
            })
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        main_module.db.set_node_hidden("default", ids[1], True)
        anon = TestClient(app)
        for url in (f"/api/graph?pool={demo['id']}", f"/api/graph?pool={demo['id']}&include_hidden=true"):
            r = anon.get(url)
            assert r.status_code == 200 and [n["id"] for n in r.json()["nodes"]] == [ids[0]]
        assert len(owner.get(f"/api/graph?pool={demo['id']}&include_hidden=true").json()["nodes"]) == 2
    finally:
        owner.delete(f"/api/pools/{demo['id']}")


# Без сессии открыто ровно это: служебные health/login/logout и две ручки демо-чтения.
_ANON_ALLOWED = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/pools"),
    ("GET", "/api/graph"),
}


def test_anonymous_surface_is_only_demo_reads():
    """Любая другая /api-ручка без сессии — 401. Ловит новую ручку без auth-зависимости:
    resolve_tenant без неё молча отдаёт тенант default (fail-open, см. tenancy.py)."""
    anon = TestClient(app)
    checked = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        path = re.sub(r"\{[^}]+\}", "x", route.path)  # path-параметры — заглушкой; тело не шлём
        for method in sorted(route.methods):
            if (method, route.path) in _ANON_ALLOWED:
                continue
            r = anon.request(method, path)
            assert r.status_code == 401, f"{method} {route.path} без сессии → {r.status_code}"
            checked.append((method, route.path))
    assert len(checked) >= 10, checked  # защита от пустого обхода (сменился тип роутов и т.п.)
