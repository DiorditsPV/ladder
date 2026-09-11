#!/usr/bin/env bash
# Забрать к себе свежий снимок живой базы Ladder, а при заданных LADDER_EMAIL/LADDER_PASSWORD — ещё и JSON-выгрузку
# всех направлений (читаемая копия контента). Нужен root-доступ по SSH (снимки лежат в /var/backups/ladder, 700).
#   deploy/backup-pull.sh                       → ~/dev/backups/ladder/ladder-<ts>-pull.db
#   LADDER_EMAIL=… LADDER_PASSWORD=… deploy/backup-pull.sh   → + export-<ts>/<направление>.json
# Из сети X5 SSH ходит через squid (~/.ssh/proxy-connect.py) — подключается сам; LADDER_NO_PROXY=1 — напрямую.
set -euo pipefail

HOST="${LADDER_HOST:-root@37.46.132.95}"
URL="${LADDER_URL:-https://ladder.paveldiordits.site}"
DEST="${LADDER_BACKUP_DEST:-$HOME/dev/backups/ladder}"
HERE=$(cd "$(dirname "$0")" && pwd)
PY="${LADDER_PY:-$HERE/../backend/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

SSH=(ssh -o ConnectTimeout=20)
if [ "${LADDER_NO_PROXY:-0}" != 1 ] && [ -x "$HOME/.ssh/proxy-connect.py" ]; then
  SSH+=(-o "ProxyCommand=$HOME/.ssh/proxy-connect.py %h %p")
fi

mkdir -p "$DEST"
chmod 700 "$DEST"
SNAP=$("${SSH[@]}" "$HOST" /usr/local/bin/ladder-backup pull)
NAME=$(basename "$SNAP")
"${SSH[@]}" "$HOST" cat "$SNAP" > "$DEST/$NAME"
chmod 600 "$DEST/$NAME"
python3 -c '
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
status = con.execute("PRAGMA integrity_check").fetchone()[0]
rows = con.execute("SELECT pool, COUNT(*) FROM nodes WHERE hidden = 0 GROUP BY pool ORDER BY pool").fetchall()
print("integrity:", status); print("карточки:", ", ".join(f"{p} {n}" for p, n in rows))
sys.exit(0 if status == "ok" else 1)
' "$DEST/$NAME"
echo "✓ снимок: $DEST/$NAME"

if [ -n "${LADDER_EMAIL:-}" ] && [ -n "${LADDER_PASSWORD:-}" ]; then
  LADDER_URL="$URL" "$PY" "$HERE/export_json.py" "$DEST/export-${NAME%.db}"
fi
