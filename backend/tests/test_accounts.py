"""Пароли и аккаунты полного режима (spec 2026-09-11)."""

import uuid

from fastapi.testclient import TestClient

import app.main as main_module
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


def test_delete_user_removes_checklist():
    """Удаление аккаунта стирает и его чек-лист (spec: удаляются сессии и прогресс пользователя)."""
    owner, email = _owner(), _email()
    created = owner.post("/api/users", json={"email": email}).json()
    user = TestClient(app)
    assert _login(user, email, created["password"]).status_code == 200
    nid = owner.post("/api/nodes", json={"block": "python", "topic": "acc-test", "difficulty": "middle", "question": "q?"}).json()["id"]
    try:
        assert user.put(f"/api/progress/{nid}", json={"status": "known"}).status_code == 200
        assert main_module.db.get_progress("default", created["id"], "data-engineer") == {nid: "known"}
        assert owner.delete(f"/api/users/{created['id']}").status_code == 200
        with main_module.db._conn() as conn:
            left = conn.execute("SELECT COUNT(*) FROM progress WHERE user_id = ?", (created["id"],)).fetchone()[0]
        assert left == 0
    finally:
        owner.delete(f"/api/nodes/{nid}")


def test_non_owner_cannot_manage_accounts():
    owner, email = _owner(), _email()
    created = owner.post("/api/users", json={"email": email}).json()
    viewer = TestClient(app)
    assert _login(viewer, email, created["password"]).status_code == 200
    assert viewer.post("/api/users", json={"email": _email()}).status_code == 403
    assert viewer.post(f"/api/users/{created['id']}/password").status_code == 403
    assert viewer.delete(f"/api/users/{created['id']}").status_code == 403
