#!/usr/bin/env bash
# Разовый провижининг сервера под сервис «Ladder» (Ubuntu 24.04, от root). Идемпотентен:
# повторный запуск обновляет юнит, nginx-блок и forced command, не трогая данные и /etc/ladder.env.
# Файлы deploy/ должны лежать рядом со скриптом — запуск с ноутбука одной командой (см. DEPLOY.md):
#   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/ladder-deploy && mkdir -p /root/ladder-deploy \
#     && tar xzf - -C /root/ladder-deploy && DEPLOY_PUBKEY="ssh-ed25519 AAAA…" bash /root/ladder-deploy/install.sh'
# Код НЕ выкладывает и юнит НЕ стартует: первая выкладка приедет из GitHub Actions.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DOMAIN=ladder.paveldiordits.site
APP=/opt/ladder
DATA=/var/lib/ladder
SVC_USER=ladder
DEPLOY_USER=deploy                       # тот же, что выкладывает сайт; ключ ladder — своя строка
PUBKEY="${DEPLOY_PUBKEY:?DEPLOY_PUBKEY='ssh-ed25519 …' — публичный ключ раннера (.deploy/ladder_deploy_key.pub)}"

[ "$(id -u)" = 0 ] || { echo "✗ запускать от root" >&2; exit 1; }
for f in ladder.service nginx-ladder.conf deploy-ladder.sh; do
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
if [ ! -f /etc/ladder.env ]; then
  EMAIL="${OWNER_EMAIL:-owner@interview.local}"
  # openssl, а не tr</dev/urandom | head: под pipefail head закрывает трубу раньше tr → 141 → set -e роняет скрипт
  PW="${OWNER_PASSWORD:-$(openssl rand -hex 12)}"
  printf 'INTERVIEW_OWNER_EMAIL=%s\nINTERVIEW_OWNER_PASSWORD=%s\n' "$EMAIL" "$PW" > /etc/ladder.env
  chmod 600 /etc/ladder.env
  echo "→ /etc/ladder.env создан. Вход owner: $EMAIL / $PW  — сохрани, второй раз не покажется"
else
  echo "→ /etc/ladder.env уже есть — не трогаю"
fi

# 4) forced command: скрипт root-only, sudo на одну команду, ключ прибит к ней ----
install -m 755 -o root -g root "$HERE/deploy-ladder.sh" /usr/local/bin/deploy-ladder.sh
# sudoers: сначала во временный файл и visudo -cf, в /etc/sudoers.d — только валидный (битый файл
# в sudoers.d ломает sudo всей машине ещё до того, как set -e остановит скрипт)
SUDO_TMP=$(mktemp)
printf '%s ALL=(root) NOPASSWD: /usr/local/bin/deploy-ladder.sh\n' "$DEPLOY_USER" > "$SUDO_TMP"
chmod 440 "$SUDO_TMP"
visudo -cf "$SUDO_TMP" >/dev/null
mv "$SUDO_TMP" /etc/sudoers.d/deploy-ladder
chown root:root /etc/sudoers.d/deploy-ladder
DEPLOY_HOME=$(getent passwd "$DEPLOY_USER" | cut -d: -f6)
AK="$DEPLOY_HOME/.ssh/authorized_keys"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$DEPLOY_HOME/.ssh"
touch "$AK"; chown "$DEPLOY_USER":"$DEPLOY_USER" "$AK"; chmod 600 "$AK"
KEY_BODY=$(printf '%s' "$PUBKEY" | awk '{print $1" "$2}')
LINE="command=\"sudo -n /usr/local/bin/deploy-ladder.sh\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $PUBKEY"
if grep -qF "$KEY_BODY" "$AK"; then
  # ключ уже есть — обновить его строку (вдруг менялся forced command), чужие строки не трогать
  cp "$AK" "$AK.bak-ladder"
  grep -vF "$KEY_BODY" "$AK" > "$AK.new" || true
  printf '%s\n' "$LINE" >> "$AK.new"
  mv "$AK.new" "$AK"; chown "$DEPLOY_USER":"$DEPLOY_USER" "$AK"; chmod 600 "$AK"
  echo "→ authorized_keys: строка ladder обновлена (резерв: $AK.bak-ladder)"
else
  printf '%s\n' "$LINE" >> "$AK"
  echo "→ authorized_keys: строка ladder добавлена"
fi
if sshd -T 2>/dev/null | grep -qi '^allowusers' && ! sshd -T 2>/dev/null | grep -i '^allowusers' | grep -qw "$DEPLOY_USER"; then
  echo "! sshd AllowUsers не содержит $DEPLOY_USER — раннер не войдёт, добавь его в sshd_config" >&2
fi

# 5) systemd — юнит ставим, но не стартуем (кода ещё нет) --------------------
install -m 644 "$HERE/ladder.service" /etc/systemd/system/ladder.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/ladder.service 2>&1 | grep -v '^$' || true

# 5b) хвосты прежнего имени сервиса (interview → ladder): старый юнит, sudoers и nginx-блок не должны остаться активными
if [ -f /etc/systemd/system/interview.service ]; then
  systemctl disable --now interview 2>/dev/null || true
  rm -f /etc/systemd/system/interview.service
  echo "→ убран старый interview.service"
fi
rm -f /etc/sudoers.d/deploy-interview /usr/local/bin/deploy-interview.sh /etc/nginx/sites-enabled/interview.paveldiordits.site /etc/nginx/sites-available/interview.paveldiordits.site
[ -f /etc/interview.env ] && [ ! -f /etc/ladder.env ] && mv /etc/interview.env /etc/ladder.env && echo "→ /etc/interview.env → /etc/ladder.env"
systemctl daemon-reload

# 6) nginx — файл, в который certbot уже дописал 443/redirect, не перезаписывать: иначе повторный
#    запуск тихо снимет HTTPS (nginx -t пройдёт, голый http-блок валиден) ---------------------
NGX="/etc/nginx/sites-available/$DOMAIN"
if [ -f "$NGX" ] && grep -qE 'managed by Certbot|listen 443 ssl' "$NGX"; then
  echo "→ nginx: $NGX уже под certbot — не перезаписываю. Правки блока переносить руками из $HERE/nginx-ladder.conf"
else
  install -m 644 "$HERE/nginx-ladder.conf" "$NGX"
fi
ln -sf "$NGX" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t
systemctl reload nginx

cat <<MSG

✓ провижининг готов. Дальше по порядку:
  1) DNS на reg.ru:  A  ladder  →  $(hostname -I 2>/dev/null | awk '{print $1}')
  2) когда запись разъедется:  certbot --nginx -d $DOMAIN --redirect
  3) merge в main → GitHub Actions выложит код и поднимет юнит
MSG
