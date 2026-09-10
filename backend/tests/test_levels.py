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
