#!/usr/bin/env bash
# Страховка контента на сервере (от root, идемпотентно): ladder-backup, ночной таймер снимков и серверный
# скрипт деплоя со снимком до выкладки и проверкой карточек после. Не трогает данные, юнит сервиса и ключи.
# Зовётся из install.sh; отдельно — чтобы обновить эти скрипты без полного провижининга (см. DEPLOY.md):
#   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/ladder-deploy && mkdir -p /root/ladder-deploy \
#     && tar xzf - -C /root/ladder-deploy && bash /root/ladder-deploy/install-backup.sh'
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
[ "$(id -u)" = 0 ] || { echo "✗ запускать от root" >&2; exit 1; }
for f in ladder-backup.py ladder-backup.service ladder-backup.timer deploy-ladder.sh; do
  [ -f "$HERE/$f" ] || { echo "✗ рядом нет $f" >&2; exit 1; }
done

install -m 755 -o root -g root "$HERE/ladder-backup.py" /usr/local/bin/ladder-backup
install -m 755 -o root -g root "$HERE/deploy-ladder.sh" /usr/local/bin/deploy-ladder.sh
install -d -m 700 -o root -g root /var/backups/ladder
install -m 644 "$HERE/ladder-backup.service" /etc/systemd/system/ladder-backup.service
install -m 644 "$HERE/ladder-backup.timer" /etc/systemd/system/ladder-backup.timer
systemctl daemon-reload
systemctl enable --now ladder-backup.timer >/dev/null
echo "→ ladder-backup, deploy-ladder.sh и таймер установлены; следующий запуск: $(systemctl show ladder-backup.timer -p NextElapseUSecRealtime --value 2>/dev/null || echo '?')"
if [ -f /var/lib/ladder/ladder.db ]; then
  echo "→ контрольный снимок: $(/usr/local/bin/ladder-backup manual)"
  echo "→ карточки: $(/usr/local/bin/ladder-backup --counts)"
fi
