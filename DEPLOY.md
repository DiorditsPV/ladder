# Деплой

Сервис живёт на сервере портфолио рядом с `paveldiordits.site` и `lexis.paveldiordits.site`:
**https://interview.paveldiordits.site**. Выкладка — **только вручную**: *Actions → Deploy → Run workflow* (ветка `main`)
или `gh workflow run Deploy --ref main`. Merge в `main` ничего не выкладывает: основной режим сервиса — локальный,
сервер — необязательная публичная копия.

```
Run workflow ─▶ GitHub Actions (.github/workflows/deploy.yml, workflow_dispatch)
                 ├─ npm ci && npm run build                 фронт собирается на раннере (node на сервере нет)
                 ├─ tar czf backend content frontend/dist
                 ├─ ssh deploy@<сервер> < interview.tar.gz  ключ прибит к одной команде:
                 │      └─ sudo /usr/local/bin/deploy-interview.sh
                 │            распаковка → /opt/interview · venv (pip только при смене requirements)
                 │            · systemctl restart interview · health :8770
                 └─ curl https://interview.paveldiordits.site/api/health → 200, /api/graph → 401
```

| Путь на сервере                                           | Назначение                                        | Переживает выкладку  |
| --------------------------------------------------------- | ------------------------------------------------- | -------------------- |
| `/opt/interview`                                          | код + контент + `frontend/dist` + `backend/.venv` | нет (кроме venv)     |
| `/var/lib/interview/interview.db`                         | SQLite: сессии, оценки, кандидаты, банк вопросов  | **да**               |
| `/etc/interview.env`                                      | owner-креды (600, root)                           | да                   |
| `/etc/systemd/system/interview.service`                   | uvicorn на `127.0.0.1:8770`, hardened             | да (ставит install)  |
| `/etc/nginx/sites-available/interview.paveldiordits.site` | фронт-дверь, TLS от certbot                       | да                   |

Что лежит в `deploy/`: `interview.service` (юнит), `nginx-interview.conf` (server-блок),
`deploy-interview.sh` (forced command, принимает архив со stdin), `install.sh` (разовый провижининг),
`test-deploy-interview.sh` (локальный тест скрипта выкладки — `bash deploy/test-deploy-interview.sh`).

## Разовая настройка сервера

Сервер: `37.46.132.95`, Ubuntu 24.04, nginx + certbot уже стоят (сайт и lexis). Все команды — с ноутбука
(SSH к серверу из сети X5 не проходит — только из домашней сети или через VPN).

1. Ключ раннера — пара в `.deploy/` (в git не попадает):
   `ssh-keygen -t ed25519 -N '' -C 'interview-graph deploy' -f .deploy/interview_deploy_key`
2. GitHub: `gh secret set DEPLOY_INTERVIEW_SSH_KEY < .deploy/interview_deploy_key` и
   `gh variable set DEPLOY_HOST --body 37.46.132.95`.
3. Провижининг (идемпотентен, можно повторять при правке юнита или nginx-блока):
   ```bash
   tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/interview-deploy && mkdir -p /root/interview-deploy \
     && tar xzf - -C /root/interview-deploy \
     && DEPLOY_PUBKEY="'"$(cat .deploy/interview_deploy_key.pub)"'" OWNER_EMAIL=<почта> OWNER_PASSWORD=<пароль> \
        bash /root/interview-deploy/install.sh'
   ```
   Без `OWNER_PASSWORD` пароль сгенерируется и напечатается **один раз**. Owner сидится в БД при первом
   старте (`seed.py`); менять потом — в БД, `/etc/interview.env` для смены уже не читается.
4. DNS на reg.ru: `A interview → 37.46.132.95`. Проверка: `dig +short interview.paveldiordits.site`.
5. TLS: `ssh root@37.46.132.95 certbot --nginx -d interview.paveldiordits.site --redirect`.
6. Merge в `main` → выкладка → https://interview.paveldiordits.site.

## Что умеет ключ раннера

Строка в `~deploy/.ssh/authorized_keys`: `command="sudo -n /usr/local/bin/deploy-interview.sh",no-port-forwarding,
no-X11-forwarding,no-agent-forwarding,no-pty`. Скрипт — `root:root 755`, sudoers разрешает `deploy` ровно его.
Архив проверяется до любых изменений на диске: не gzip, или нет `backend/app/main.py` / `frontend/dist/index.html` /
`content` → выход 1, `/opt` не тронут. Юнит скрипт **не ставит** (только `install.sh`) — архив не может подменить `User=`.

## Откат

Предыдущей копии кода на сервере нет — откат = `git revert` в `main` (выкладка идёт автоматически) либо
*Actions → Deploy → Run workflow* на нужном коммите. БД выкладкой не трогается.

## Диагностика

```bash
ssh root@37.46.132.95 'systemctl status interview; journalctl -u interview -n 50 --no-pager'
ssh root@37.46.132.95 'curl -s http://127.0.0.1:8770/api/health; nginx -t'
```

## Локально

`./run.sh` (:8000), `./run.sh dev` (:8001, своя БД), `docker compose up -d --build` — см. README.
Dev-контура на сервере нет: проверять перед merge локально.
