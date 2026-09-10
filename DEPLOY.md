# Деплой

Сервис живёт на сервере портфолио рядом с `paveldiordits.site` и `lexis.paveldiordits.site`:
**https://ladder.paveldiordits.site**. Выкладка — **только вручную**: *Actions → Deploy → Run workflow* (ветка `main`)
или `gh workflow run Deploy --ref main`. Merge в `main` ничего не выкладывает: основной режим сервиса — локальный,
сервер — необязательная публичная копия.

```
Run workflow ─▶ GitHub Actions (.github/workflows/deploy.yml, workflow_dispatch)
                 ├─ npm ci && npm run build                 фронт собирается на раннере (node на сервере нет)
                 ├─ tar czf backend content frontend/dist
                 ├─ ssh deploy@<сервер> < ladder.tar.gz  ключ прибит к одной команде:
                 │      └─ sudo /usr/local/bin/deploy-ladder.sh
                 │            распаковка → /opt/ladder · venv (pip только при смене requirements)
                 │            · systemctl restart ladder · health :8770
                 └─ curl https://ladder.paveldiordits.site/api/health → 200, /api/graph → 401
```

| Путь на сервере                                           | Назначение                                        | Переживает выкладку  |
| --------------------------------------------------------- | ------------------------------------------------- | -------------------- |
| `/opt/ladder`                                          | код + контент + `frontend/dist` + `backend/.venv` | нет (кроме venv)     |
| `/var/lib/ladder/ladder.db`                         | SQLite: сессии, оценки, кандидаты, банк вопросов  | **да**               |
| `/etc/ladder.env`                                      | owner-креды (600, root)                           | да                   |
| `/etc/systemd/system/ladder.service`                   | uvicorn на `127.0.0.1:8770`, hardened             | да (ставит install)  |
| `/etc/nginx/sites-available/ladder.paveldiordits.site` | фронт-дверь, TLS от certbot                       | да                   |

Что лежит в `deploy/`: `ladder.service` (юнит), `nginx-ladder.conf` (server-блок),
`deploy-ladder.sh` (forced command, принимает архив со stdin), `install.sh` (разовый провижининг),
`test-deploy-ladder.sh` (локальный тест скрипта выкладки — `bash deploy/test-deploy-ladder.sh`).

## Разовая настройка сервера

Сервер: `37.46.132.95`, Ubuntu 24.04, nginx + certbot уже стоят (сайт и lexis). Все команды — с ноутбука
(SSH к серверу из сети X5 не проходит — только из домашней сети или через VPN).

1. Ключ раннера — пара в `.deploy/` (в git не попадает):
   `ssh-keygen -t ed25519 -N '' -C 'ladder deploy' -f .deploy/ladder_deploy_key`
2. GitHub: `gh secret set DEPLOY_LADDER_SSH_KEY < .deploy/ladder_deploy_key` и
   `gh variable set DEPLOY_HOST --body 37.46.132.95`.
3. Провижининг (идемпотентен, можно повторять при правке юнита или nginx-блока):
   ```bash
   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/ladder-deploy && mkdir -p /root/ladder-deploy \
     && tar xzf - -C /root/ladder-deploy \
     && DEPLOY_PUBKEY="'"$(cat .deploy/ladder_deploy_key.pub)"'" OWNER_EMAIL=<почта> OWNER_PASSWORD=<пароль> \
        bash /root/ladder-deploy/install.sh'
   ```
   Без `OWNER_PASSWORD` пароль сгенерируется и напечатается **один раз**. Owner сидится в БД при первом
   старте (`seed.py`); менять потом — в БД, `/etc/ladder.env` для смены уже не читается.
4. DNS на reg.ru: `A interview → 37.46.132.95`. Проверка: `dig +short ladder.paveldiordits.site`.
5. TLS: `ssh root@37.46.132.95 certbot --nginx -d ladder.paveldiordits.site --redirect`.
6. Merge в `main` → выкладка → https://ladder.paveldiordits.site.

## Что умеет ключ раннера

Строка в `~deploy/.ssh/authorized_keys`: `command="sudo -n /usr/local/bin/deploy-ladder.sh",no-port-forwarding,
no-X11-forwarding,no-agent-forwarding,no-pty`. Скрипт — `root:root 755`, sudoers разрешает `deploy` ровно его.
Архив проверяется до любых изменений на диске: не gzip, или нет `backend/app/main.py` / `frontend/dist/index.html` /
`content` → выход 1, `/opt` не тронут. Юнит скрипт **не ставит** (только `install.sh`) — архив не может подменить `User=`.

## Откат

Предыдущей копии кода на сервере нет — откат = `git revert` в `main` (выкладка идёт автоматически) либо
*Actions → Deploy → Run workflow* на нужном коммите. БД выкладкой не трогается.

## Диагностика

```bash
ssh root@37.46.132.95 'systemctl status ladder; journalctl -u ladder -n 50 --no-pager'
ssh root@37.46.132.95 'curl -s http://127.0.0.1:8770/api/health; nginx -t'
```

## Локально

`./run.sh` (:8000), `./run.sh dev` (:8001, своя БД), `docker compose up -d --build` — см. README.
Dev-контура на сервере нет: проверять перед merge локально.
