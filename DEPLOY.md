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
                 └─ curl https://ladder.paveldiordits.site (без cookie): /api/health → 200,
                        /api/pools → 200, /api/graph?pool=data-engineer → 200 (демо),
                        /api/graph?pool=data-engineer-x5 → 401 (остальное за входом)
```

| Путь на сервере                                        | Назначение                                        | Переживает выкладку |
|--------------------------------------------------------|---------------------------------------------------|---------------------|
| `/opt/ladder`                                          | код + контент + `frontend/dist` + `backend/.venv` | нет (кроме venv)    |
| `/var/lib/ladder/ladder.db`                            | SQLite: направления, банк вопросов, чек-лист      | **да**              |
| `/etc/ladder.env`                                      | owner-креды (600, root)                           | да                  |
| `/etc/systemd/system/ladder.service`                   | uvicorn на `127.0.0.1:8770`, hardened             | да (ставит install) |
| `/etc/nginx/sites-available/ladder.paveldiordits.site` | фронт-дверь, TLS от certbot                       | да                  |

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
   старте (`seed.py`); менять потом — в интерфейсе («Сменить пароль» в меню аккаунта или в ⚙ на доске),
   `/etc/ladder.env` для смены уже не читается.
4. DNS на reg.ru: `A ladder → 37.46.132.95`. Проверка: `dig +short ladder.paveldiordits.site`.
5. TLS: `ssh root@37.46.132.95 certbot --nginx -d ladder.paveldiordits.site --redirect`.
6. Merge в `main` → выкладка → https://ladder.paveldiordits.site.

## Режимы доступа

Сайт без входа открывается как **демо** (spec `docs/superpowers/specs/2026-09-11-demo-and-access-design.md`):
стартовый экран, «Открыть демо» → направления с `demo: true` в `pool.yaml` («Дата-инженер» и «Системный аналитик»,
на английском — их переводы `*-en`), чек-лист только в браузере посетителя. Без cookie бэкенд отвечает ровно на
`GET /api/pools` (демо-список) и `GET /api/graph?pool=<демо>`; всё остальное — 401. Шаг «Проверить боевой адрес»
в `deploy.yml` проверяет именно это: health 200, `/api/pools` 200, демо-граф 200, граф `data-engineer-x5` 401 —
если после выкладки закрытое направление читается без входа или демо не открывается, прогон падает.

**Полный режим** — вход по `https://ladder.paveldiordits.site/#/login` (на стартовом экране — приглушённая ссылка
«Вход»). Владелец заводит людей на странице «Люди» (`#/people`): почта → одноразовый пароль, показывается один раз;
там же сброс пароля и удаление аккаунта. Приглашённые (роль viewer) видят все направления и ведут свой чек-лист;
свой пароль каждый меняет сам («Сменить пароль»), остальные его сессии при этом завершаются.

Риск: ограничения частоты попыток входа нет — на публичном адресе это отдельная задача (spec, «Вне скоупа»).

## Что умеет ключ раннера

Строка в `~deploy/.ssh/authorized_keys`: `command="sudo -n /usr/local/bin/deploy-ladder.sh",no-port-forwarding,
no-X11-forwarding,no-agent-forwarding,no-pty`. Скрипт — `root:root 755`, sudoers разрешает `deploy` ровно его.
Архив проверяется до любых изменений на диске: не gzip, или нет `backend/app/main.py` / `frontend/dist/index.html` /
`content` → выход 1, `/opt` не тронут. Юнит скрипт **не ставит** (только `install.sh`) — архив не может подменить `User=`.

## Контент и бэкапы

Источник правды для вопросов — база на сервере (`/var/lib/ladder/ladder.db`): направления и карточки заносятся через
MCP, API и UI. В репозитории (`content/`) — только пресеты: `data-engineer`, `system-analyst` и их `-en`. Синхронизация
при старте сервиса только **засевает** недостающее (новое направление, карточки с новыми id) и никогда не
перезаписывает и не прячет существующее — деплой не может затереть накопленное. Обновить пресет из файлов — явно:
`POST /api/pools/sync?pool=<id>&update=true` (сначала `&dry_run=true`) или MCP `sync_from_files`.

Страховка (`deploy/install-backup.sh`, ставится из `install.sh`, повторный запуск безопасен):
- `ladder-backup` — согласованный снимок базы с проверкой целостности в `/var/backups/ladder` (700, root);
- таймер `ladder-backup.timer` — снимок каждую ночь около 03:30, хранятся 14 последних;
- `deploy-ladder.sh` перед рестартом снимает снимок `…-pre-deploy.db` (10 последних) и считает карточки по
  направлениям, после старта сравнивает: стало меньше хоть в одном — выкладка падает с путём к снимку.

Забрать копию к себе (снимок + JSON-выгрузка всех направлений, если заданы креды):

```bash
LADDER_EMAIL=<почта> LADDER_PASSWORD=<пароль> deploy/backup-pull.sh   # → ~/dev/backups/ladder/
```

Где что хранится (решение владельца 2026-09-12): в этом репозитории — только демонстрационный слой
(пресеты `data-engineer`, `system-analyst` и их `-en`), остальной контент боевой базы хранится **отдельно**.
Версионируемая копия — свой git-репозиторий `~/dev/ladder-content` (каталог `pools/`, по файлу на направление):
после заметных правок контента прогнать `backup-pull.sh` и скопировать туда свежий `export-*/`.

Обновить серверные скрипты страховки без полного провижининга:

```bash
tar czf - -C deploy . | ssh root@37.46.132.95 'rm -rf /root/ladder-deploy && mkdir -p /root/ladder-deploy \
  && tar xzf - -C /root/ladder-deploy && bash /root/ladder-deploy/install-backup.sh'
```

Восстановление из снимка (карточки, прогресс, аккаунты — всё в одном файле). Журналы SQLite рядом с базой
(`-journal`, `-wal`, `-shm`) удаляются до подмены — иначе SQLite применит чужой журнал к восстановленной базе:

```bash
ssh root@37.46.132.95 'systemctl stop ladder && ladder-backup manual \
  && rm -f /var/lib/ladder/ladder.db-journal /var/lib/ladder/ladder.db-wal /var/lib/ladder/ladder.db-shm \
  && install -o ladder -g ladder -m 644 /var/backups/ladder/<снимок>.db /var/lib/ladder/ladder.db \
  && systemctl start ladder'
```

## Откат

Предыдущей копии кода на сервере нет — откат = `git revert` в `main` и ручной *Actions → Deploy → Run workflow*
на нужном коммите. БД выкладкой не трогается; перед каждой выкладкой снимается её снимок (см. «Контент и бэкапы»).

## Диагностика

```bash
ssh root@37.46.132.95 'systemctl status ladder; journalctl -u ladder -n 50 --no-pager'
ssh root@37.46.132.95 'curl -s http://127.0.0.1:8770/api/health; nginx -t'
```

## Локально

`./run.sh` (:8000), `./run.sh dev` (:8001, своя БД), `docker compose up -d --build` — см. README.
Dev-контура на сервере нет: проверять перед merge локально.
