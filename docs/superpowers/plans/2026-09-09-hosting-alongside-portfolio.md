# Размещение сервиса рядом с портфолио — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** interview-graph отвечает на `https://interview.paveldiordits.site` за логином, выкладывается из GitHub Actions по merge в `main` через forced-command-ключ; старый инстанс на NL `45.114.62.236:8800/8801` снесён.

**Architecture:** uvicorn на `127.0.0.1:8770` под hardened systemd-юнитом рядом с lexis, nginx-server-блок на поддомене с certbot-TLS, SSE-локейшн без буферизации. Раннер собирает фронт и шлёт один tar.gz в stdin скрипта `/usr/local/bin/deploy-interview.sh`; ключ раннера прибит к этой команде. Юнит, nginx-конфиг и forced command ставит разовый `deploy/install.sh` от root.

**Tech Stack:** bash, systemd, nginx 1.24, certbot, GitHub Actions, GNU tar, rsync, python3-venv.

**Spec:** `docs/superpowers/specs/2026-09-09-hosting-alongside-portfolio-design.md`

## Global Constraints

- Сервер `37.46.132.95`: 1 vCPU, 1799 МБ RAM, swap 899 МБ; занят `lexis.service` (`127.0.0.1:8765`, `MemoryMax=1200M`), nginx `:80/:443`. Порт сервиса — **8770**, `MemoryMax=400M`.
- На сервере **нет node/npm** — фронт собирается только на раннере.
- SSH к серверу из сети X5 невозможен (IP не в ACL squid): **серверные шаги выполняет владелец** через `!`-команды, текст команды даётся дословно.
- Host-key сервера (закреплён в workflow дословно): `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1sEThhqUNxeSWgjUtOOuulxk6EMVNAizFdjoCAPlXY`.
- Пользователь деплоя на сервере — существующий `deploy` (им же выкладывается сайт); ключ interview — отдельная строка в его `authorized_keys` со своим forced command.
- Юнит `/etc/systemd/system/interview.service` пишет **только** `install.sh`; `deploy-interview.sh` его не трогает.
- Все скрипты в `deploy/` — `set -euo pipefail`, комментарии по-русски, как в `deploy/bootstrap.sh`.
- В фиче-ветке не пушить в `main`; merge в `main` = выкладка, и делается он последним, после провижининга и DNS.
- Режимы задач (CLAUDE.md): все задачи **инлайн**, одна ветка `feature/hosting-portfolio-server`, последовательно; параллелить нечего (общие файлы и один сервер). Финальное ревью ветки — одно, перед PR (Task 8).

---

### Task 1: Юнит и nginx-конфиг

**Files:**
- Create: `deploy/interview.service`
- Create: `deploy/nginx-interview.conf`
- Delete: ничего (bootstrap.sh удаляется в Task 6 вместе с документацией)

**Interfaces:**
- Produces: юнит `interview.service` с `ExecStart` на `:8770`, `EnvironmentFile=/etc/interview.env` (создаёт Task 3), `ReadWritePaths=/var/lib/interview`; nginx-блок `interview.paveldiordits.site` → `127.0.0.1:8770`.
- Consumes: ничего.

- [ ] **Step 1: Написать юнит**

```ini
# /etc/systemd/system/interview.service — сервис «Интервью» (FastAPI + SQLite).
# Ставится deploy/install.sh (от root) и только им: deploy-interview.sh юнит не трогает,
# чтобы архив от раннера не мог подменить User=. Слепок с lexis.service на том же сервере.
[Unit]
Description=interview graph (FastAPI)
After=network.target

[Service]
User=interview
Group=interview
WorkingDirectory=/opt/interview/backend
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=INTERVIEW_DB_PATH=/var/lib/interview/interview.db
Environment=INTERVIEW_CONTENT_DIR=/opt/interview/content
Environment=INTERVIEW_FRONTEND_DIR=/opt/interview/frontend/dist
# owner-креды; файл обязателен — без него приложение сгенерирует случайный пароль в лог
EnvironmentFile=/etc/interview.env
# только localhost: наружу — через nginx; --proxy-headers, чтобы схема/IP брались из X-Forwarded-*
ExecStart=/opt/interview/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8770 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=on-failure
RestartSec=3
MemoryMax=400M
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/interview

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Написать nginx-конфиг**

```nginx
# /etc/nginx/sites-available/interview.paveldiordits.site — фронт-дверь сервиса «Интервью».
# Всё проксируется на uvicorn (фронт отдаёт само приложение через StaticFiles), /var/www не нужен.
# Блок 443 и редирект с 80 дописывает certbot:  certbot --nginx -d interview.paveldiordits.site --redirect
server {
    listen 80;
    listen [::]:80;
    server_name interview.paveldiordits.site;

    client_max_body_size 8m;

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # SSE — живое обновление оценок в сессии: без буферизации, с долгим таймаутом,
    # иначе nginx копит поток и обновления во второй вкладке залипают.
    location ~ ^/api/sessions/[0-9]+/events$ {
        proxy_pass         http://127.0.0.1:8770;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 1h;
    }

    location / {
        proxy_pass         http://127.0.0.1:8770;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

- [ ] **Step 3: Гейт — `nginx -t` в контейнере той же версии**

Run:
```bash
docker run --rm -v "$PWD/deploy/nginx-interview.conf:/etc/nginx/conf.d/interview.conf:ro" nginx:1.24 nginx -t
```
Expected: `syntax is ok` и `test is successful`.

- [ ] **Step 4: Commit**

```bash
git add deploy/interview.service deploy/nginx-interview.conf
git commit -m "deploy: systemd-юнит и nginx-блок interview.paveldiordits.site (:8770, SSE без буферизации)"
```

---

### Task 2: Forced-command-скрипт выкладки + локальный тест

**Files:**
- Create: `deploy/deploy-interview.sh`
- Create: `deploy/test-deploy-interview.sh`

**Interfaces:**
- Consumes: архив со stdin, состав — `backend/`, `content/`, `frontend/dist/` (собирает Task 4).
- Produces: `/usr/local/bin/deploy-interview.sh` (ставит Task 3). Переменные для теста: `APP_DIR`, `DATA_DIR`, `DEPLOY_DRY_RUN=1`. Коды выхода: 0 — выложено, 1 — архив отвергнут или health не прошёл (в `/opt` при отвергнутом архиве ничего не меняется).

- [ ] **Step 1: Написать тест (падает — скрипта нет)**

```bash
#!/usr/bin/env bash
# Локальный тест deploy-interview.sh: приём архива со stdin, проверка состава, раскладка, кэш
# requirements. Без сервера: DEPLOY_DRY_RUN=1 отключает chown/venv/systemd/health.
#   bash deploy/test-deploy-interview.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/deploy-interview.sh"
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

echo "✓ deploy-interview.sh: 5/5"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `bash deploy/test-deploy-interview.sh`
Expected: FAIL — `deploy-interview.sh: No such file` (или «мусор на stdin принят»).

- [ ] **Step 3: Написать скрипт**

```bash
#!/usr/bin/env bash
# Forced command деплой-ключа: принимает tar.gz со stdin, раскладывает код, обновляет venv,
# рестартует юнит, ждёт health. Ставится deploy/install.sh в /usr/local/bin (root:root 755);
# в authorized_keys пользователя deploy ключ раннера прибит к
#   command="sudo -n /usr/local/bin/deploy-interview.sh" — другого доступа у ключа нет.
# Состав архива (собирает .github/workflows/deploy.yml): backend/ content/ frontend/dist/
# Юнит НЕ трогает — он ставится только install.sh, чтобы архив не мог подменить User=.
#
# Локальный тест (deploy/test-deploy-interview.sh): APP_DIR, DATA_DIR, DEPLOY_DRY_RUN=1 —
# только приём, проверка и раскладка архива, без chown/venv/systemd/health.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/interview}"
DATA_DIR="${DATA_DIR:-/var/lib/interview}"
SVC="${SVC:-interview}"
SVC_USER="${SVC_USER:-interview}"
PORT="${PORT:-8770}"
DRY="${DEPLOY_DRY_RUN:-0}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/interview.tar.gz"

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

# 4) рестарт юнита (ставит install.sh) и health --------------------------------
systemctl enable "$SVC" >/dev/null 2>&1 || true
systemctl restart "$SVC"
for _ in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    echo "✓ $SVC активен, /api/health отвечает на :$PORT"
    exit 0
  fi
  sleep 1
done
echo "✗ healthcheck не прошёл за 15 с — лог сервиса:" >&2
journalctl -u "$SVC" -n 40 --no-pager >&2 || true
exit 1
```

- [ ] **Step 4: Запустить тест — проходит**

Run: `bash deploy/test-deploy-interview.sh`
Expected: `✓ deploy-interview.sh: 5/5`.

- [ ] **Step 5: `bash -n` обоих + shellcheck через docker**

Run:
```bash
bash -n deploy/deploy-interview.sh && bash -n deploy/test-deploy-interview.sh
docker run --rm -v "$PWD/deploy:/d:ro" koalaman/shellcheck:stable -S warning /d/deploy-interview.sh /d/test-deploy-interview.sh
```
Expected: пусто (0 замечаний уровня warning и выше).

- [ ] **Step 6: Commit**

```bash
git add deploy/deploy-interview.sh deploy/test-deploy-interview.sh
git commit -m "deploy: forced-command-скрипт выкладки (tar.gz со stdin, кэш requirements, health) + локальный тест"
```

---

### Task 3: Разовый провижининг `install.sh` + гейт в контейнере

**Files:**
- Create: `deploy/install.sh`

**Interfaces:**
- Consumes: `deploy/interview.service`, `deploy/nginx-interview.conf` (Task 1), `deploy/deploy-interview.sh` (Task 2) — читает из своего каталога `$(dirname "$0")`.
- Produces: на сервере — пользователь `interview`, каталоги, `/etc/interview.env`, `/usr/local/bin/deploy-interview.sh`, `/etc/sudoers.d/deploy-interview`, строка в `~deploy/.ssh/authorized_keys`, юнит (не запущен), nginx-блок (включён). Входные переменные окружения: `DEPLOY_PUBKEY` (обязательна), `OWNER_EMAIL`, `OWNER_PASSWORD` (необязательны).

- [ ] **Step 1: Написать скрипт**

```bash
#!/usr/bin/env bash
# Разовый провижининг сервера под сервис «Интервью» (Ubuntu 24.04, от root). Идемпотентен:
# повторный запуск обновляет юнит, nginx-блок и forced command, не трогая данные и /etc/interview.env.
# Файлы deploy/ должны лежать рядом со скриптом — запуск с ноутбука одной командой:
#   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/interview-deploy && mkdir -p /root/interview-deploy \
#     && tar xzf - -C /root/interview-deploy && DEPLOY_PUBKEY="ssh-ed25519 AAAA…" bash /root/interview-deploy/install.sh'
# Код НЕ выкладывает и юнит НЕ стартует: первая выкладка приедет из GitHub Actions.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DOMAIN=interview.paveldiordits.site
APP=/opt/interview
DATA=/var/lib/interview
SVC_USER=interview
DEPLOY_USER=deploy                       # тот же, что выкладывает сайт; ключ interview — своя строка
PUBKEY="${DEPLOY_PUBKEY:?DEPLOY_PUBKEY='ssh-ed25519 …' — публичный ключ раннера (deploy/.deploy/interview_deploy_key.pub)}"

[ "$(id -u)" = 0 ] || { echo "✗ запускать от root" >&2; exit 1; }
for f in interview.service nginx-interview.conf deploy-interview.sh; do
  [ -f "$HERE/$f" ] || { echo "✗ рядом нет $f" >&2; exit 1; }
done

# 1) пакеты --------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
need=()
for p in python3-venv rsync curl; do dpkg -s "$p" >/dev/null 2>&1 || need+=("$p"); done
if [ "${#need[@]}" -gt 0 ]; then
  echo "→ apt-get install: ${need[*]}"
  apt-get update -qq && apt-get install -y -qq "${need[@]}"
fi

# 2) пользователи и каталоги ---------------------------------------------------
id -u "$SVC_USER" >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin "$SVC_USER"
id -u "$DEPLOY_USER" >/dev/null 2>&1 || useradd --create-home --shell /bin/sh "$DEPLOY_USER"
mkdir -p "$APP" "$DATA"
chown "$SVC_USER":"$SVC_USER" "$APP" "$DATA"

# 3) owner-креды — один раз; смена потом только руками (owner сидится в БД при первом старте) ----
if [ ! -f /etc/interview.env ]; then
  EMAIL="${OWNER_EMAIL:-owner@interview.local}"
  PW="${OWNER_PASSWORD:-$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)}"
  printf 'INTERVIEW_OWNER_EMAIL=%s\nINTERVIEW_OWNER_PASSWORD=%s\n' "$EMAIL" "$PW" > /etc/interview.env
  chmod 600 /etc/interview.env
  echo "→ /etc/interview.env создан. Вход owner: $EMAIL / $PW  — сохрани, второй раз не покажется"
else
  echo "→ /etc/interview.env уже есть — не трогаю"
fi

# 4) forced command: скрипт root-only, sudo на одну команду, ключ прибит к ней ----
install -m 755 -o root -g root "$HERE/deploy-interview.sh" /usr/local/bin/deploy-interview.sh
printf '%s ALL=(root) NOPASSWD: /usr/local/bin/deploy-interview.sh\n' "$DEPLOY_USER" > /etc/sudoers.d/deploy-interview
chmod 440 /etc/sudoers.d/deploy-interview
visudo -cf /etc/sudoers.d/deploy-interview >/dev/null
DEPLOY_HOME=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)
AK="$DEPLOY_HOME/.ssh/authorized_keys"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$DEPLOY_HOME/.ssh"
touch "$AK"; chown "$DEPLOY_USER":"$DEPLOY_USER" "$AK"; chmod 600 "$AK"
KEY_BODY=$(printf '%s' "$PUBKEY" | awk '{print $1" "$2}')
LINE="command=\"sudo -n /usr/local/bin/deploy-interview.sh\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $PUBKEY"
if grep -qF "$KEY_BODY" "$AK"; then
  # ключ уже есть — обновить его строку (вдруг менялся forced command), чужие строки не трогать
  cp "$AK" "$AK.bak-interview"
  grep -vF "$KEY_BODY" "$AK" > "$AK.new" || true
  printf '%s\n' "$LINE" >> "$AK.new"
  mv "$AK.new" "$AK"; chown "$DEPLOY_USER":"$DEPLOY_USER" "$AK"; chmod 600 "$AK"
  echo "→ authorized_keys: строка interview обновлена (резерв: $AK.bak-interview)"
else
  printf '%s\n' "$LINE" >> "$AK"
  echo "→ authorized_keys: строка interview добавлена"
fi
if sshd -T 2>/dev/null | grep -qi '^allowusers' && ! sshd -T | grep -i '^allowusers' | grep -qw "$DEPLOY_USER"; then
  echo "! sshd AllowUsers не содержит $DEPLOY_USER — раннер не войдёт, добавь его в sshd_config" >&2
fi

# 5) systemd — юнит ставим, но не стартуем (кода ещё нет) --------------------
install -m 644 "$HERE/interview.service" /etc/systemd/system/interview.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/interview.service 2>&1 | grep -v '^$' || true

# 6) nginx ---------------------------------------------------------------------
install -m 644 "$HERE/nginx-interview.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t
systemctl reload nginx

cat <<EOF

✓ провижининг готов. Дальше по порядку:
  1) DNS на reg.ru:  A  interview  →  $(hostname -I 2>/dev/null | awk '{print $1}')
  2) когда запись разъедется:  certbot --nginx -d $DOMAIN --redirect
  3) merge в main → GitHub Actions выложит код и поднимет юнит
EOF
```

- [ ] **Step 2: `bash -n` + shellcheck**

Run:
```bash
bash -n deploy/install.sh
docker run --rm -v "$PWD/deploy:/d:ro" koalaman/shellcheck:stable -S warning /d/install.sh
```
Expected: пусто.

- [ ] **Step 3: Живой гейт — прогон в контейнере ubuntu:24.04 с nginx**

Проверяет, что скрипт идемпотентен, ставит forced command, юнит и nginx-блок, и второй запуск не дублирует строку ключа.

Run:
```bash
docker run --rm -v "$PWD/deploy:/deploy:ro" ubuntu:24.04 bash -c '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq nginx sudo openssh-server python3 rsync curl systemd >/dev/null
  cp -r /deploy /root/d
  K="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtestkeytestkeytestkeytestkeytestkeytestke test"
  DEPLOY_PUBKEY="$K" OWNER_EMAIL=me@x OWNER_PASSWORD=pw1 bash /root/d/install.sh
  DEPLOY_PUBKEY="$K" bash /root/d/install.sh
  echo "--- проверки:"
  test "$(grep -c AAAAC3NzaC1lZDI1NTE5AAAAIGtest /home/deploy/.ssh/authorized_keys)" = 1 && echo "ключ ровно один раз"
  grep -q "command=\"sudo -n /usr/local/bin/deploy-interview.sh\"" /home/deploy/.ssh/authorized_keys && echo "forced command на месте"
  test -x /usr/local/bin/deploy-interview.sh && echo "скрипт root-only: $(stat -c %U:%a /usr/local/bin/deploy-interview.sh)"
  grep -q "^deploy ALL=(root) NOPASSWD: /usr/local/bin/deploy-interview.sh" /etc/sudoers.d/deploy-interview && echo "sudoers ok"
  grep -q "INTERVIEW_OWNER_PASSWORD=pw1" /etc/interview.env && echo "env создан один раз ($(stat -c %a /etc/interview.env))"
  test -L /etc/nginx/sites-enabled/interview.paveldiordits.site && echo "nginx-блок включён"
  test -f /etc/systemd/system/interview.service && echo "юнит на месте"
'
```
Expected: шесть строк «ok»-проверок, `nginx: configuration file … test is successful` дважды, без `✗`. (`systemctl reload nginx` в контейнере без init упадёт — допустимо: скрипт должен это пережить? **Нет** — `set -e` уронит. Поэтому в контейнере команды `systemctl …` подменяются заглушкой: перед запуском `printf '#!/bin/sh\nexit 0\n' > /usr/local/sbin/systemctl && chmod +x /usr/local/sbin/systemctl` и то же для `systemd-analyze`, `sshd`. Добавить эти две строки в команду выше перед первым `bash /root/d/install.sh`.)

- [ ] **Step 4: Commit**

```bash
git add deploy/install.sh
git commit -m "deploy: разовый провижининг сервера — пользователи, /etc/interview.env, forced command, юнит, nginx"
```

---

### Task 4: Workflow выкладки

**Files:**
- Modify: `.github/workflows/deploy.yml` (полная замена)
- Delete: `.github/workflows/deploy-dev.yml`

**Interfaces:**
- Consumes: секрет `DEPLOY_INTERVIEW_SSH_KEY`, переменная `DEPLOY_HOST` (Task 5); forced command на сервере (Task 3).
- Produces: архив `backend content frontend/dist` в stdin `ssh deploy@$DEPLOY_HOST`; внешний гейт `health 200` + `graph 401`.

- [ ] **Step 1: Переписать `deploy.yml`**

```yaml
name: Deploy

# Выкладка на сервер портфолио (interview.paveldiordits.site) при любом попадании коммита в main.
# Фронт собирается на раннере — node на сервере нет. Всё нужное уезжает одним tar.gz в stdin
# forced-command-скрипта /usr/local/bin/deploy-interview.sh: ключ раннера на сервере умеет ровно
# эту команду (см. deploy/install.sh и DEPLOY.md). Host-key закреплён явно — подмену сервера
# раннер не примет.
on:
  push:
    branches: [main]
  workflow_dispatch: {}

concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Собрать фронт (tsc + vite)
        working-directory: frontend
        run: |
          npm ci
          npm run build

      - name: Упаковать выкладку
        run: |
          tar czf interview.tar.gz \
            --exclude='backend/.venv' --exclude='__pycache__' --exclude='*.db' --exclude='.pytest_cache' \
            backend content frontend/dist
          ls -la interview.tar.gz

      - name: Разложить ключ и закреплённый host-key
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "${{ secrets.DEPLOY_INTERVIEW_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          printf '%s\n' "${{ vars.DEPLOY_HOST }} ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1sEThhqUNxeSWgjUtOOuulxk6EMVNAizFdjoCAPlXY" > ~/.ssh/known_hosts
          chmod 600 ~/.ssh/known_hosts

      - name: Выложить на сервер
        run: |
          ssh -i ~/.ssh/deploy_key \
              -o StrictHostKeyChecking=yes \
              -o UserKnownHostsFile=~/.ssh/known_hosts \
              -o ConnectTimeout=20 \
              deploy@${{ vars.DEPLOY_HOST }} < interview.tar.gz

      - name: Проверить боевой адрес
        run: |
          sleep 2
          base=https://interview.paveldiordits.site
          code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$base/api/health")
          [ "$code" = 200 ] || { echo "✗ /api/health → $code"; exit 1; }
          code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$base/api/graph")
          [ "$code" = 401 ] || { echo "✗ /api/graph без cookie → $code (ожидалось 401: сервис за логином)"; exit 1; }
          echo "✓ health 200, graph 401 — сервис на месте и за логином"
```

- [ ] **Step 2: Удалить dev-workflow**

Run: `git rm .github/workflows/deploy-dev.yml`

- [ ] **Step 3: Гейт — actionlint в docker + локальная упаковка**

Run:
```bash
docker run --rm -v "$PWD:/repo:ro" -w /repo rhysd/actionlint:latest -color
tar czf /tmp/interview-test.tar.gz --exclude='backend/.venv' --exclude='__pycache__' --exclude='*.db' --exclude='.pytest_cache' backend content frontend/dist \
  && APP_DIR=/tmp/ig-opt DATA_DIR=/tmp/ig-data DEPLOY_DRY_RUN=1 bash deploy/deploy-interview.sh < /tmp/interview-test.tar.gz \
  && ls /tmp/ig-opt/frontend/dist/index.html /tmp/ig-opt/content && rm -rf /tmp/ig-opt /tmp/ig-data /tmp/interview-test.tar.gz
```
Expected: actionlint молчит; dry-run печатает `→ архив принят`, `✓ dry-run завершён`, `ls` находит оба пути. (Тар собирается ровно той командой, что в workflow, — это проверка, что реальный состав архива проходит валидатор скрипта.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): выкладка на сервер портфолио — сборка на раннере, tar.gz в forced command, внешний health-гейт; dev-контур снят"
```

---

### Task 5: Ключ раннера и GitHub-секреты

**Files:**
- Create: `.deploy/interview_deploy_key`, `.deploy/interview_deploy_key.pub` (gitignored — `/.deploy/` в `.gitignore:21`)

**Interfaces:**
- Produces: секрет `DEPLOY_INTERVIEW_SSH_KEY`, переменная `DEPLOY_HOST=37.46.132.95` в репозитории `DiorditsPV/interview-graph`; публичный ключ — вход `DEPLOY_PUBKEY` для `install.sh` (Task 7).

- [ ] **Step 1: Сгенерировать пару**

Run:
```bash
ssh-keygen -t ed25519 -N '' -C 'interview-graph deploy → 37.46.132.95' -f .deploy/interview_deploy_key
cat .deploy/interview_deploy_key.pub
```
Expected: файл и строка `ssh-ed25519 AAAA… interview-graph deploy → 37.46.132.95`.

- [ ] **Step 2: Положить в GitHub**

Run:
```bash
gh secret set DEPLOY_INTERVIEW_SSH_KEY < .deploy/interview_deploy_key
gh variable set DEPLOY_HOST --body 37.46.132.95
gh secret list; gh variable list
```
Expected: в списках `DEPLOY_INTERVIEW_SSH_KEY` и `DEPLOY_HOST 37.46.132.95`. Старые `SSH_*`/`OWNER_PASSWORD` пока остаются — удаляются в Task 9 после первой удачной выкладки.

- [ ] **Step 3: Ничего не коммитить** — `git status` должен быть чист от `.deploy/`.

---

### Task 6: Документация в репозитории

**Files:**
- Modify: `DEPLOY.md` (полная замена)
- Modify: `README.md` — места, где упомянуты `:8800`, `bootstrap.sh`, `SSH_HOST`
- Delete: `deploy/bootstrap.sh`
- Modify: `Dockerfile:5` — комментарий ссылается на `deploy/bootstrap.sh` → на `deploy/interview.service`
- Modify: `docs/superpowers/specs/2026-09-09-hosting-alongside-portfolio-design.md` — §4/§5: юнит ставит только `install.sh`; деплой-пользователь `deploy`, не `deploy-interview`

**Interfaces:** нет.

- [ ] **Step 1: Переписать `DEPLOY.md`**

```markdown
# Деплой

Сервис живёт на сервере портфолио рядом с `paveldiordits.site` и `lexis.paveldiordits.site`:
**https://interview.paveldiordits.site**. Любой merge в `main` запускает выкладку.

```
push в main ─▶ GitHub Actions (.github/workflows/deploy.yml)
                 ├─ npm ci && npm run build                 фронт собирается на раннере (node на сервере нет)
                 ├─ tar czf backend content frontend/dist
                 └─ ssh deploy@<сервер> < interview.tar.gz  ключ прибит к одной команде:
                        └─ sudo /usr/local/bin/deploy-interview.sh
                              распаковка → /opt/interview · venv (pip только при смене requirements)
                              · systemctl restart interview · health :8770
                 └─ curl https://interview.paveldiordits.site/api/health → 200, /api/graph → 401
```

| Путь на сервере                                           | Назначение                                        | Переживает выкладку |
|-----------------------------------------------------------|---------------------------------------------------|---------------------|
| `/opt/interview`                                          | код + контент + `frontend/dist` + `backend/.venv` | нет (кроме venv)    |
| `/var/lib/interview/interview.db`                         | SQLite: сессии, оценки, кандидаты, банк вопросов  | **да**              |
| `/etc/interview.env`                                      | owner-креды (600, root)                           | да                  |
| `/etc/systemd/system/interview.service`                   | uvicorn на `127.0.0.1:8770`, hardened             | да (ставит install) |
| `/etc/nginx/sites-available/interview.paveldiordits.site` | фронт-дверь, TLS от certbot                       | да                  |

## Разовая настройка сервера

Сервер: `37.46.132.95`, Ubuntu 24.04, nginx + certbot уже стоят (сайт и lexis). Все команды — с ноутбука
(SSH к серверу из сети X5 не проходит — только из домашней/через VPN).

1. Ключ раннера — пара в `.deploy/` (в git не попадает):
   `ssh-keygen -t ed25519 -N '' -C 'interview-graph deploy' -f .deploy/interview_deploy_key`
2. GitHub → `gh secret set DEPLOY_INTERVIEW_SSH_KEY < .deploy/interview_deploy_key`,
   `gh variable set DEPLOY_HOST --body 37.46.132.95`.
3. Провижининг (идемпотентен, можно повторять при правке юнита/nginx):
   ```bash
   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/interview-deploy && mkdir -p /root/interview-deploy \
     && tar xzf - -C /root/interview-deploy \
     && DEPLOY_PUBKEY="'"$(cat .deploy/interview_deploy_key.pub)"'" OWNER_EMAIL=<почта> OWNER_PASSWORD=<пароль> \
        bash /root/interview-deploy/install.sh'
   ```
   Без `OWNER_PASSWORD` пароль сгенерируется и напечатается **один раз**. Owner сидится в БД при первом
   старте; чтобы сменить потом — править в БД, `/etc/interview.env` после этого не читается для смены.
4. DNS на reg.ru: `A interview → 37.46.132.95`. Проверка: `dig +short interview.paveldiordits.site`.
5. TLS: `ssh root@37.46.132.95 certbot --nginx -d interview.paveldiordits.site --redirect`.
6. Merge в `main` → выкладка → https://interview.paveldiordits.site.

## Что умеет ключ раннера

Строка в `~deploy/.ssh/authorized_keys`: `command="sudo -n /usr/local/bin/deploy-interview.sh",no-port-forwarding,
no-X11-forwarding,no-agent-forwarding,no-pty`. Скрипт — `root:root 755`, sudoers разрешает `deploy` ровно его.
Архив проверяется до любых изменений на диске: не gzip или нет `backend/app/main.py` / `frontend/dist/index.html` /
`content` → выход 1, `/opt` не тронут. Юнит скрипт **не ставит** (только `install.sh`) — архив не может подменить `User=`.

## Откат

Предыдущей копии кода на сервере нет — откат = `git revert` в `main` (выкладка идёт автоматически) либо
`workflow_dispatch` на нужном коммите. БД выкладкой не трогается.

## Диагностика

```bash
ssh root@37.46.132.95 'systemctl status interview; journalctl -u interview -n 50 --no-pager'
ssh root@37.46.132.95 'curl -s http://127.0.0.1:8770/api/health; nginx -t'
```

## Локально

`./run.sh` (:8000), `./run.sh dev` (:8001, своя БД), `docker compose up -d --build` — см. README.
Dev-контура на сервере нет: проверять перед merge локально.
```

- [ ] **Step 2: README, Dockerfile, bootstrap, спека**

Run: `grep -n '8800\|bootstrap\|SSH_HOST\|45\.114' README.md Dockerfile AGENTS.md CLAUDE.md` — каждое вхождение заменить на новую схему (адрес `https://interview.paveldiordits.site`, `DEPLOY.md`). `git rm deploy/bootstrap.sh`. В `CLAUDE.md` строка «merge в `main` триггерит автодеплой на сервер (порт 8800, см. `DEPLOY.md`)» → «… на interview.paveldiordits.site (см. `DEPLOY.md`)». В спеке §4: «юнит едет с кодом — как у lexis» → «юнит ставит только `install.sh`»; §5: `deploy-interview` → существующий `deploy`, вторая строка в `authorized_keys`.

- [ ] **Step 3: Гейт**

Run: `grep -rn '8800\|8801\|bootstrap.sh\|SSH_HOST\|interview-src' --include='*.md' --include='*.yml' --include='Dockerfile' --include='*.sh' . | grep -v node_modules | grep -v '\.venv' | grep -v 'docs/superpowers/plans'`
Expected: только упоминания в спеке (§7 «Снос старого» и «Зачем» — про NL) и в этом плане.

- [ ] **Step 4: Commit**

```bash
git add -A DEPLOY.md README.md Dockerfile CLAUDE.md AGENTS.md deploy/ docs/superpowers/specs/
git commit -m "docs(deploy): новая схема — сервер портфолио, forced command, provisioning; bootstrap.sh снят"
```

---

### Task 7: Проверки ветки, ревью, PR в dev — затем серверные шаги владельца

**Files:** нет новых.

- [ ] **Step 1: Регрессия** — `cd backend && . .venv/bin/activate && pytest -q` → все зелёные (код приложения не трогали); `cd frontend && npm run build` → зелёная (тот же шаг, что на раннере).

- [ ] **Step 2: Финальное ревью ветки** — агент `review-agent` по `git diff dev...HEAD`; замечания уровня «дефект» правятся до PR.

- [ ] **Step 3: Push и PR в `dev`**

```bash
git push -u origin feature/hosting-portfolio-server
gh pr create --base dev --title "Размещение рядом с портфолио: interview.paveldiordits.site, forced-command деплой" --body-file - <<'EOF'
Спека: docs/superpowers/specs/2026-09-09-hosting-alongside-portfolio-design.md

- deploy/: interview.service (127.0.0.1:8770, hardened), nginx-блок с SSE-локейшном, forced-command-скрипт с локальным тестом, install.sh (гейт в ubuntu:24.04)
- .github/workflows/deploy.yml: сборка на раннере, tar.gz в stdin, host-key закреплён, внешний гейт health 200 / graph 401; deploy-dev.yml снят
- DEPLOY.md переписан, bootstrap.sh удалён

Выкладка сработает после merge dev → main, когда сервер провижинен и DNS разъехался (шаги в DEPLOY.md).
EOF
```
CI на PR должен быть зелёным.

- [ ] **Step 4: Серверные шаги — владелец, дословно (после merge PR в `dev`, до merge в `main`)**

Из корня репозитория на ветке с `deploy/`:
```
! tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/interview-deploy && mkdir -p /root/interview-deploy && tar xzf - -C /root/interview-deploy && DEPLOY_PUBKEY="'"$(cat .deploy/interview_deploy_key.pub)"'" OWNER_EMAIL=diordic@gmail.com bash /root/interview-deploy/install.sh'
```
Expected: `✓ провижининг готов`, напечатан owner-пароль (сохранить), `nginx … test is successful`. Затем DNS на reg.ru `A interview → 37.46.132.95`; когда `dig +short interview.paveldiordits.site` вернёт IP:
```
! ssh root@37.46.132.95 'certbot --nginx -d interview.paveldiordits.site --redirect'
```
Expected: `Successfully deployed certificate`.

- [ ] **Step 5: Merge в `main` = первая выкладка**

```bash
gh pr merge --squash   # PR в dev
git checkout dev && git pull --ff-only
gh pr create --base main --head dev --title "Синхронизация main с dev: размещение рядом с портфолио" --body "Первая выкладка на interview.paveldiordits.site."
gh workflow enable Deploy
gh pr merge --merge
gh run watch
```
Expected: Deploy зелёный, последний шаг печатает `✓ health 200, graph 401`.

- [ ] **Step 6: Боевой гейт руками**
`curl -s https://interview.paveldiordits.site/api/health` → `{"status":"ok",…}`; вход owner-кредами в браузере — доска открывается; сессия в двух вкладках — оценка из первой появляется во второй без перезагрузки (SSE через nginx).

---

### Task 8: Снос NL-инстанса (только после Task 7 Step 6)

**Files:** нет в репозитории. Архив БД: `~/dev/backups/interview-nl-2026-09-09/`.

- [ ] **Step 1: Архив обеих БД** (через KZ-squid; `P` — ProxyCommand):

```bash
P="python3 $HOME/.ssh/proxy-connect.py %h %p"
mkdir -p ~/dev/backups/interview-nl-2026-09-09
scp -o ProxyCommand="$P" root@45.114.62.236:/var/lib/interview/interview.db     ~/dev/backups/interview-nl-2026-09-09/prod-interview.db
scp -o ProxyCommand="$P" root@45.114.62.236:/var/lib/interview-dev/interview.db ~/dev/backups/interview-nl-2026-09-09/dev-interview.db
ls -la ~/dev/backups/interview-nl-2026-09-09/
```
Expected: два файла, 200704 и 450560 байт.

- [ ] **Step 2: Остановить и снести**

```bash
ssh -o ProxyCommand="$P" root@45.114.62.236 '
  systemctl disable --now interview interview-dev
  rm -f /etc/systemd/system/interview.service /etc/systemd/system/interview-dev.service
  systemctl daemon-reload
  rm -rf /opt/interview /opt/interview-dev /var/lib/interview /var/lib/interview-dev /home/deploy/interview-src /home/deploy/interview-src-dev
  ufw delete allow 8800/tcp; ufw delete allow 8801/tcp
  ss -lntp | grep -E ":880[01]" || echo "порты 8800/8801 свободны"
  ufw status | grep -E "880[01]" || echo "ufw: правил на 8800/8801 нет"'
```
Expected: последние две строки — «свободны» и «правил нет».

- [ ] **Step 3: Проверка снаружи** — `curl -s -m 5 -o /dev/null -w '%{http_code}\n' http://45.114.62.236:8800/` → `000` (отказ соединения).

---

### Task 9: Хвосты — секреты, инфрадоки, память

**Files:**
- Modify: `~/dev/docs/infra/servers/servers.yaml` — новый узел `37.46.132.95`
- Modify: `~/.claude/projects/-Users-user-dev-projects-personal-interview-graph/memory/prod-deploy-disabled.md` → переименовать в актуальное состояние; `MEMORY.md` — строка индекса

- [ ] **Step 1: Старые секреты долой**

```bash
for s in SSH_HOST SSH_USER SSH_PRIVATE_KEY SSH_KNOWN_HOSTS SSH_PORT OWNER_PASSWORD; do gh secret delete "$s" 2>/dev/null && echo "удалён $s"; done
gh secret list
```
Expected: остался только `DEPLOY_INTERVIEW_SSH_KEY`.

- [ ] **Step 2: `servers.yaml`** — в `other:` добавить блок:

```yaml
  37.46.132.95:               # сервер портфолио · Ubuntu 24.04 · ssh root@37.46.132.95 · 1 vCPU / 1.8 ГБ / swap 0.9 ГБ
    note: |
      НЕТ в ACL squid own_servers — из сети X5 SSH не проходит ни напрямую, ни через KZ. Только дом/VPN.
      Host-key: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1sEThhqUNxeSWgjUtOOuulxk6EMVNAizFdjoCAPlXY
      Пользователь deploy — ключи GitHub Actions с forced command (сайт: deploy-site.sh, interview: deploy-interview.sh).
    sshd:      22/tcp
    nginx:     80/tcp, 443/tcp · paveldiordits.site (статика, репо portfolio) · lexis.paveldiordits.site · interview.paveldiordits.site · certbot
    lexis:     127.0.0.1:8765 · lexis.service · /opt/lexis · /var/lib/lexis · MemoryMax=1200M
    interview: 127.0.0.1:8770 · interview.service · /opt/interview · /var/lib/interview/interview.db · /etc/interview.env (owner) · MemoryMax=400M
               выкладка: репо interview-graph, DEPLOY.md; архив старых NL-баз — ~/dev/backups/interview-nl-2026-09-09/
```
И в `other: 45.114.62.236:` удалить строки `interview:` и `interview-dev:`. Обновить дату слепка в шапке файла. Коммит в `~/dev/docs`.

- [ ] **Step 3: Память** — файл `prod-deploy-disabled.md` заменить на `hosting-portfolio-server-2026-09-09.md` (`type: project`): сервис на `interview.paveldiordits.site`, деплой включён, forced command, NL снесён, SSH к серверу только вне X5, архив баз. Строку в `MEMORY.md` заменить.

---

## Self-review

- **Spec coverage:** §1 адрес/TLS → T7 Step 4; §2 юнит → T1; §3 nginx → T1; §4 workflow + скрипт → T2, T4; §5 install → T3; §6 секреты → T5, T9; §7 снос → T8; §8 доки → T6, T9. Уточнения спеки (юнит только через install; пользователь `deploy`) → T6 Step 2.
- **Placeholders:** нет; все файлы даны целиком; серверные команды дословные.
- **Consistency:** порт 8770, `DEPLOY_INTERVIEW_SSH_KEY`, `DEPLOY_HOST`, пользователь `deploy`, путь `/usr/local/bin/deploy-interview.sh`, штамп `.req.sha256`, переменные `APP_DIR/DATA_DIR/DEPLOY_DRY_RUN` — одинаковы в T1–T6.
