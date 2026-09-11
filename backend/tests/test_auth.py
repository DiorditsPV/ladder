"""Тесты auth-identity (#36): аутентификация, сессии, RBAC.

Используют общий module-level app/db (паттерн _client из test_app/test_nodes).
Cookie сессии живёт внутри инстанса TestClient, поэтому разные клиенты = разные сессии.
"""

from fastapi.testclient import TestClient

from app.db import Database
from app.main import OWNER_EMAIL, OWNER_PASSWORD, _resolve_owner_password, app

_VALID_NODE = {"block": "python", "topic": "auth-test", "difficulty": "middle", "question": "q?"}


def _anon() -> TestClient:
    return TestClient(app)


def _login(c: TestClient, email: str, password: str):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def _owner() -> TestClient:
    c = _anon()
    assert _login(c, OWNER_EMAIL, OWNER_PASSWORD).status_code == 200
    return c


def _user(email: str, password: str, role: str) -> TestClient:
    """Создать (owner'ом) пользователя с ролью и вернуть залогиненного под ним клиента.

    Идемпотентно: при повторном прогоне создание вернёт 409, но логин всё равно работает.
    """
    owner = _owner()
    owner.post("/api/users", json={"email": email, "password": password, "role": role})
    c = _anon()
    assert _login(c, email, password).status_code == 200
    return c


def test_unauthenticated_request_401():
    assert _anon().get("/api/graph").status_code == 401


def test_login_success_me_and_tenant_resolution():
    c = _owner()
    me = c.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == OWNER_EMAIL
    assert body["role"] == "owner"
    assert body["tenant_id"] == "default"  # resolve_tenant из сессии, не хардкод


def test_login_wrong_password_401():
    assert _login(_anon(), OWNER_EMAIL, "definitely-wrong").status_code == 401


def test_logout_clears_session():
    c = _owner()
    assert c.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_viewer_can_read_but_not_mutate():
    viewer = _user("viewer@interview.local", "viewer-pw", "viewer")
    assert viewer.get("/api/graph").status_code == 200  # чтение — ок
    assert viewer.post("/api/nodes", json=_VALID_NODE).status_code == 403  # мутация — 403


def test_member_can_mutate():
    member = _user("member@interview.local", "member-pw", "member")
    r = member.post("/api/nodes", json=_VALID_NODE)
    assert r.status_code == 200, r.text
    member.delete(f"/api/nodes/{r.json()['id']}")  # cleanup


def test_owner_can_manage_users():
    owner = _owner()
    assert owner.get("/api/users").status_code == 200


def test_non_owner_cannot_list_users():
    member = _user("member2@interview.local", "member2-pw", "member")
    assert member.get("/api/users").status_code == 403


# --- auth-hardening (#40) ---


def test_owner_password_random_when_env_unset(monkeypatch):
    """Без INTERVIEW_OWNER_PASSWORD пароль случайный и НЕ известный дефолт."""
    monkeypatch.delenv("INTERVIEW_OWNER_PASSWORD", raising=False)
    pw1, gen1 = _resolve_owner_password()
    pw2, gen2 = _resolve_owner_password()
    assert gen1 and gen2  # помечен как сгенерированный (логируется при сиде)
    assert pw1 != "interview-dev" and pw2 != "interview-dev"
    assert pw1 != pw2 and len(pw1) >= 16  # случайный, не пустой
    # с env — берётся как есть и не считается сгенерированным
    monkeypatch.setenv("INTERVIEW_OWNER_PASSWORD", "from-env")
    pw3, gen3 = _resolve_owner_password()
    assert pw3 == "from-env" and gen3 is False


def test_login_cookie_has_max_age():
    """Cookie сессии несёт max_age (TTL) — браузер сам выкинет протухшую."""
    r = _login(_anon(), OWNER_EMAIL, OWNER_PASSWORD)
    assert r.status_code == 200
    assert "max-age=" in r.headers.get("set-cookie", "").lower()


def test_session_ttl_expires_to_401():
    """Сессия старше TTL → 401 (get_auth_session удаляет протухшую)."""
    c = _owner()
    assert c.get("/api/auth/me").status_code == 200
    with app.state.db._conn() as conn:  # «состарим» все auth-сессии за пределы TTL
        conn.execute("UPDATE auth_sessions SET created_at = ?", ("2000-01-01T00:00:00+00:00",))
    assert c.get("/api/auth/me").status_code == 401


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


def test_delete_user_sessions_keeps_current(tmp_path):
    """Отзыв сессий пользователя: except_token (текущая) остаётся, чужие сессии не трогаются."""
    db = Database(tmp_path / "s.db")
    db.ensure_tenant("t")
    cur, other_device, foreign = (db.create_auth_session("t", u) for u in ("u1", "u1", "u2"))
    assert db.delete_user_sessions("t", "u1", except_token=cur) == 1
    assert db.get_auth_session(cur) is not None and db.get_auth_session(other_device) is None
    assert db.delete_user_sessions("t", "u1") == 1
    assert db.get_auth_session(cur) is None and db.get_auth_session(foreign) is not None


def test_login_purges_expired_sessions(tmp_path):
    """Повторный вход больше не вытесняет прежние сессии — протухшие чистит сам вход, таблица не растёт."""
    db = Database(tmp_path / "s.db")
    db.ensure_tenant("t")
    old, fresh = db.create_auth_session("t", "u1"), db.create_auth_session("t", "u2")
    with db._conn() as conn:
        conn.execute("UPDATE auth_sessions SET created_at = ? WHERE token = ?", ("2000-01-01T00:00:00+00:00", old))
    new = db.create_auth_session("t", "u3")  # вход другого пользователя тоже чистит протухшие
    with db._conn() as conn:
        tokens = {r["token"] for r in conn.execute("SELECT token FROM auth_sessions").fetchall()}
    assert tokens == {fresh, new}


def test_nodes_tenant_isolation(tmp_path):
    """DAL: ноды чужого тенанта не видны (изоляция осталась после удаления режима интервью)."""
    db = Database(tmp_path / "iso.db")
    db.ensure_tenant("t1")
    db.ensure_tenant("t2")
    node = {"id": "iso-01", "pool": "p", "block": "b", "topic": "t", "question": "q", "difficulty": "base"}
    db.upsert_node("t1", node)
    assert db.get_node("t1", "iso-01") is not None
    assert db.get_node("t2", "iso-01") is None
    assert db.list_nodes("t2") == []
