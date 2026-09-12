"""Выгрузка всех направлений Ladder в JSON через API: читаемая копия контента рядом со снимком базы.

    LADDER_URL=https://ladder.paveldiordits.site LADDER_EMAIL=… LADDER_PASSWORD=… \
        python deploy/export_json.py ~/dev/backups/ladder/export-$(date +%Y%m%d-%H%M%S)

Пишет <dir>/<pool>.json (конфиг направления + все карточки, включая скрытые) и <dir>/manifest.json (сводка).
Нужен только httpx (есть в backend/.venv). Ничего не меняет на сервере, кроме одной сессии входа (выход в конце).
"""

import json
import os
import sys
from pathlib import Path

import httpx


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_json.py <output-dir>")
    out = Path(sys.argv[1]).expanduser()
    url = os.environ.get("LADDER_URL", "http://localhost:8000").rstrip("/")
    email, password = os.environ.get("LADDER_EMAIL"), os.environ.get("LADDER_PASSWORD")
    if not email or not password:
        raise SystemExit("set LADDER_EMAIL and LADDER_PASSWORD")
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=url, timeout=60) as http:
        r = http.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise SystemExit(f"login failed: {r.status_code}")
        # manifest пишется всегда, в том числе при обрыве: каталог выгрузки без него неотличим от полного
        manifest = {"url": url, "complete": False, "expected": None, "pools": []}
        try:
            pools = http.get("/api/pools").raise_for_status().json()
            manifest["expected"] = len(pools)
            for pool in pools:
                nodes = http.get("/api/nodes", params={"pool": pool["id"], "include_hidden": "true"}).raise_for_status().json()
                (out / f"{pool['id']}.json").write_text(
                    json.dumps({"pool": pool, "nodes": nodes}, ensure_ascii=False, indent=1), encoding="utf-8"
                )
                hidden = sum(1 for n in nodes if n.get("hidden"))
                manifest["pools"].append({"id": pool["id"], "nodes": len(nodes), "hidden": hidden})
                print(f"{pool['id']}: {len(nodes)} cards ({hidden} hidden)")
            manifest["complete"] = len(manifest["pools"]) == manifest["expected"]
        except Exception as exc:
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
            http.post("/api/auth/logout")
    print(f"exported to {out}")


if __name__ == "__main__":
    main()
