"""deploy/ladder-backup.py: согласованный снимок с ротацией и счётчики карточек для проверки деплоя."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.db import Database

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "ladder-backup.py"


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "ladder.db"
    db = Database(path)
    db.ensure_tenant("default")
    blocks = [{"id": "a", "label": "A", "color": "#2563eb", "weight": 1, "subblocks": []}]
    for pid in ("one", "two"):
        db.upsert_pool_seed("default", {"id": pid, "label": pid, "blocks": blocks})
    for i in range(3):
        db.upsert_node("default", {"id": f"one-{i}", "pool": "one", "block": "a", "topic": "t", "difficulty": "base",
                                   "question": "q"}, source="user")
    db.upsert_node("default", {"id": "two-0", "pool": "two", "block": "a", "topic": "t", "difficulty": "base",
                               "question": "q"}, source="user")
    db.set_node_hidden("default", "one-2", True)
    return path


def _run(tmp_path: Path, db: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "LADDER_DB": str(db), "LADDER_BACKUP_DIR": str(tmp_path / "backups")}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_counts_visible_cards_per_pool(tmp_path):
    db = _db(tmp_path)
    r = _run(tmp_path, db, "--counts")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"one": 2, "two": 1}


def test_snapshot_is_consistent_and_rotated(tmp_path):
    db = _db(tmp_path)
    paths = []
    for _ in range(3):
        r = _run(tmp_path, db, "manual", "--keep", "2")
        assert r.returncode == 0, r.stderr
        paths.append(Path(r.stdout.strip()))
        # имена снимков — с точностью до секунды: разводим вызовы, чтобы ротация видела три разных файла
        os.utime(paths[-1])
        import time

        time.sleep(1.1)
    kept = sorted((tmp_path / "backups").glob("ladder-*-manual.db"))
    assert kept == sorted(paths[-2:])
    con = sqlite3.connect(kept[-1])
    assert con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 4
    con.close()


def test_compare_fails_only_when_cards_disappear(tmp_path):
    db = _db(tmp_path)
    ok = _run(tmp_path, db, "--compare", '{"one": 2, "two": 1}', '{"one": 3, "two": 1, "new": 5}')
    assert ok.returncode == 0
    lost = _run(tmp_path, db, "--compare", '{"one": 2, "two": 1}', '{"one": 1}')
    assert lost.returncode == 1
    assert "one: было 2 карточек, стало 1" in lost.stderr and "two: было 1 карточек, стало 0" in lost.stderr


def test_label_is_required(tmp_path):
    r = _run(tmp_path, _db(tmp_path))
    assert r.returncode != 0 and "метка" in r.stderr
