#!/usr/bin/env bash
# Локальный тест deploy-ladder.sh: приём архива со stdin, проверка состава, раскладка, кэш
# requirements. Без сервера: DEPLOY_DRY_RUN=1 отключает chown/venv/systemd/health.
#   bash deploy/test-deploy-ladder.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/deploy-ladder.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export APP_DIR="$T/opt" DATA_DIR="$T/data" DEPLOY_DRY_RUN=1
fail() { echo "✗ $*" >&2; exit 1; }

# эталонный архив
mkdir -p "$T/src/backend/app" "$T/src/frontend/dist" "$T/src/content/pool"
echo 'app = None' > "$T/src/backend/app/main.py"
printf 'fastapi>=0.110\n' > "$T/src/backend/requirements.txt"
echo '<!doctype html>' > "$T/src/frontend/dist/index.html"
echo 'id: x' > "$T/src/content/pool/pool.yaml"
tar czf "$T/good.tar.gz" -C "$T/src" backend content frontend/dist

# 1) не gzip → отказ, /opt не создан
if echo "мусор" | bash "$SCRIPT" >/dev/null 2>&1; then fail "мусор на stdin принят"; fi
[ ! -e "$APP_DIR/backend" ] || fail "после отказа /opt тронут"

# 2) архив без фронта → отказ
tar czf "$T/nofront.tar.gz" -C "$T/src" backend content
if bash "$SCRIPT" < "$T/nofront.tar.gz" >/dev/null 2>&1; then fail "архив без frontend/dist принят"; fi
[ ! -e "$APP_DIR/backend" ] || fail "после отказа /opt тронут"

# 3) первый деплой: разложено, requirements «изменились», штамп записан
mkdir -p "$APP_DIR/backend/.venv"; echo keep > "$APP_DIR/backend/.venv/keep"   # venv переживает --delete
echo stale > "$APP_DIR/stale.txt"                                               # лишний файл удаляется
out=$(bash "$SCRIPT" < "$T/good.tar.gz")
grep -q 'requirements изменились' <<<"$out" || fail "первый деплой не запросил pip: $out"
[ -f "$APP_DIR/backend/app/main.py" ]      || fail "main.py не разложен"
[ -f "$APP_DIR/frontend/dist/index.html" ] || fail "dist не разложен"
[ -f "$APP_DIR/content/pool/pool.yaml" ]   || fail "content не разложен"
[ -f "$APP_DIR/backend/.venv/keep" ]       || fail "venv затёрт --delete"
[ ! -e "$APP_DIR/stale.txt" ]              || fail "лишний файл не удалён"
[ -s "$APP_DIR/.req.sha256" ]              || fail "штамп requirements не записан"
[ -d "$DATA_DIR" ]                         || fail "DATA_DIR не создан"

# 4) повтор без изменений → pip пропущен, штамп цел
out=$(bash "$SCRIPT" < "$T/good.tar.gz")
grep -q 'requirements не менялись' <<<"$out" || fail "повтор запросил pip: $out"

# 5) смена requirements → pip снова
printf 'fastapi>=0.110\nhttpx>=0.27\n' > "$T/src/backend/requirements.txt"
tar czf "$T/good2.tar.gz" -C "$T/src" backend content frontend/dist
out=$(bash "$SCRIPT" < "$T/good2.tar.gz")
grep -q 'requirements изменились' <<<"$out" || fail "смена requirements не замечена: $out"

echo "✓ deploy-ladder.sh: 5/5"
