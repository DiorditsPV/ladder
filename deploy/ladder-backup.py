#!/usr/bin/env python3
"""Снимки базы Ladder и счётчики карточек — страховка накопленного контента (spec 2026-09-11-content-in-db).

    ladder-backup <label> [--keep N]   снимок: nightly | pre-deploy | pull | manual → печатает путь
    ladder-backup --counts             видимые карточки по направлениям (JSON) — для проверки деплоя
    ladder-backup --compare BEFORE AFTER   выход 1, если в каком-то направлении карточек стало меньше

Снимок — через sqlite3 backup API: согласованная копия даже на работающем сервисе; копия проверяется
integrity_check, старые снимки той же метки удаляются (оставляются последние N). Ставится deploy/install-backup.sh
в /usr/local/bin/ladder-backup; пути — LADDER_DB и LADDER_BACKUP_DIR (по умолчанию серверные).
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

DB = Path(os.environ.get("LADDER_DB", "/var/lib/ladder/ladder.db"))
BACKUP_DIR = Path(os.environ.get("LADDER_BACKUP_DIR", "/var/backups/ladder"))
KEEP = {"nightly": 14, "pre-deploy": 10, "pull": 5, "manual": 20}


def counts() -> dict:
    """Видимые (не скрытые) карточки по живым направлениям."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT p.id, COUNT(n.id) FROM pools p LEFT JOIN nodes n "
            "ON n.tenant_id = p.tenant_id AND n.pool = p.id AND n.hidden = 0 "
            "WHERE p.deleted_at IS NULL GROUP BY p.id ORDER BY p.id"
        ).fetchall()
    finally:
        con.close()
    return {pool: n for pool, n in rows}


def drops(before: dict, after: dict) -> dict:
    """Направления, где видимых карточек стало меньше (или направление пропало): {id: (было, стало)}."""
    return {pool: (n, after.get(pool, 0)) for pool, n in before.items() if after.get(pool, 0) < n}


def snapshot(label: str, keep: int) -> Path:
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    dst = BACKUP_DIR / f"ladder-{time.strftime('%Y%m%d-%H%M%S')}-{label}.db"
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    check = sqlite3.connect(dst)
    try:
        status = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if status != "ok":
        dst.unlink()
        raise SystemExit(f"✗ снимок не прошёл integrity_check: {status}")
    os.chmod(dst, 0o600)
    for old in sorted(BACKUP_DIR.glob(f"ladder-*-{label}.db"))[:-keep]:
        old.unlink()
    return dst


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("label", nargs="?", help="nightly | pre-deploy | pull | manual")
    ap.add_argument("--keep", type=int, help="сколько снимков этой метки хранить")
    ap.add_argument("--counts", action="store_true", help="напечатать JSON {направление: видимых карточек}")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="сравнить два JSON из --counts")
    a = ap.parse_args()
    if a.compare:
        lost = drops(json.loads(a.compare[0]), json.loads(a.compare[1]))
        for pool, (was, now) in sorted(lost.items()):
            print(f"✗ {pool}: было {was} карточек, стало {now}", file=sys.stderr)
        return 1 if lost else 0
    if not DB.exists():
        raise SystemExit(f"✗ нет базы {DB}")
    if a.counts:
        print(json.dumps(counts(), ensure_ascii=False, sort_keys=True))
        return
    if not a.label or not re.match(r"^[a-z][a-z-]*$", a.label):
        ap.error("нужна метка снимка: nightly | pre-deploy | pull | manual")
    print(snapshot(a.label, a.keep or KEEP.get(a.label, 10)))


if __name__ == "__main__":
    sys.exit(main())
