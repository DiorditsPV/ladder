#!/usr/bin/env bash
# Forced command деплой-ключа (ladder): принимает tar.gz со stdin, раскладывает код, обновляет venv,
# рестартует юнит, ждёт health. Ставится deploy/install.sh в /usr/local/bin (root:root 755);
# в authorized_keys пользователя deploy ключ раннера прибит к
#   command="sudo -n /usr/local/bin/deploy-ladder.sh" — другого доступа у ключа нет.
# Состав архива (собирает .github/workflows/deploy.yml): backend/ content/ frontend/dist/
# Юнит НЕ трогает — он ставится только install.sh, чтобы архив не мог подменить User=.
#
# Локальный тест (deploy/test-deploy-ladder.sh): APP_DIR, DATA_DIR, DEPLOY_DRY_RUN=1 —
# только приём, проверка и раскладка архива, без chown/venv/systemd/health.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ladder}"
DATA_DIR="${DATA_DIR:-/var/lib/ladder}"
SVC="${SVC:-ladder}"
SVC_USER="${SVC_USER:-ladder}"
PORT="${PORT:-8770}"
DRY="${DEPLOY_DRY_RUN:-0}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/ladder.tar.gz"

# 1) архив со stdin — сначала проверка, потом любые изменения на диске -----------
cat > "$ARCHIVE"
if ! gzip -t "$ARCHIVE" 2>/dev/null; then
  echo "✗ stdin — не gzip-архив, выкладка отменена" >&2
  exit 1
fi
mkdir -p "$TMP/src"
tar -xzf "$ARCHIVE" -C "$TMP/src"
for must in backend/app/main.py backend/requirements.txt frontend/dist/index.html content; do
  if [ ! -e "$TMP/src/$must" ]; then
    echo "✗ в архиве нет $must — выкладка отменена, $APP_DIR не тронут" >&2
    exit 1
  fi
done
echo "→ архив принят: $(du -sh "$ARCHIVE" | cut -f1)"

# 2) раскладка кода: venv и штамп остаются, всё остальное — как в архиве ----------
mkdir -p "$APP_DIR" "$DATA_DIR"
rsync -a --delete --exclude 'backend/.venv' --exclude '.req.sha256' "$TMP/src"/ "$APP_DIR"/
[ "$DRY" = 1 ] || chown -R "$SVC_USER":"$SVC_USER" "$APP_DIR" "$DATA_DIR"
echo "→ код разложен в $APP_DIR"

# 3) venv — pip только при смене requirements.txt (1 vCPU, экономим минуты) ------
REQ="$APP_DIR/backend/requirements.txt"
STAMP="$APP_DIR/.req.sha256"
NEW_HASH=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$REQ")
OLD_HASH=$(cat "$STAMP" 2>/dev/null || true)
if [ "$DRY" != 1 ] && [ ! -x "$APP_DIR/backend/.venv/bin/python" ]; then
  sudo -u "$SVC_USER" python3 -m venv "$APP_DIR/backend/.venv"
  OLD_HASH=""
fi
if [ "$NEW_HASH" != "$OLD_HASH" ]; then
  echo "→ requirements изменились — pip install"
  [ "$DRY" = 1 ] || sudo -u "$SVC_USER" "$APP_DIR/backend/.venv/bin/pip" install -q -r "$REQ"
else
  echo "→ requirements не менялись — pip пропущен"
fi
printf '%s\n' "$NEW_HASH" > "$STAMP"

if [ "$DRY" = 1 ]; then
  echo "✓ dry-run завершён"
  exit 0
fi

# 4) страховка накопленного: снимок базы и счётчики карточек до рестарта --------
#    (ladder-backup ставит deploy/install-backup.sh; нет его — деплой идёт без страховки, с предупреждением)
BACKUP=/usr/local/bin/ladder-backup
SNAP=""; BEFORE=""
if [ -x "$BACKUP" ] && [ -f "$DATA_DIR/ladder.db" ]; then
  SNAP=$(LADDER_DB="$DATA_DIR/ladder.db" "$BACKUP" pre-deploy)
  BEFORE=$(LADDER_DB="$DATA_DIR/ladder.db" "$BACKUP" --counts)
  echo "→ снимок до деплоя: $SNAP"
else
  echo "! ladder-backup не установлен — деплой без снимка (deploy/install-backup.sh)" >&2
fi

# 5) рестарт юнита (ставит install.sh) и health --------------------------------
systemctl enable "$SVC" >/dev/null 2>&1 || true
systemctl restart "$SVC"
healthy=0
for _ in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
if [ "$healthy" != 1 ]; then
  echo "✗ healthcheck не прошёл за 15 с — лог сервиса:" >&2
  journalctl -u "$SVC" -n 40 --no-pager >&2 || true
  [ -n "$SNAP" ] && echo "  снимок базы до деплоя: $SNAP" >&2
  exit 1
fi
echo "✓ $SVC активен, /api/health отвечает на :$PORT"

# 6) после старта (засев из content/ уже прошёл) карточек не может стать меньше -----
if [ -n "$BEFORE" ]; then
  AFTER=$(LADDER_DB="$DATA_DIR/ladder.db" "$BACKUP" --counts)
  if ! "$BACKUP" --compare "$BEFORE" "$AFTER"; then
    echo "✗ после деплоя пропали карточки — разбирайся до следующей выкладки; снимок до деплоя: $SNAP" >&2
    exit 1
  fi
  echo "✓ карточки на месте: $AFTER"
fi
exit 0
