# Размещение сервиса рядом с портфолио — дизайн

Дата: 2026-09-09 · статус: утверждён владельцем («приступай к выполнению»), ревью-гейты схлопнуты ·
контекст: сервер портфолио описан в `~/dev/docs/infra/servers/servers.yaml` (запись добавляется этой работой).

## Зачем

Сервис живёт на VPN-узле NL `45.114.62.236:8800` голым IP: автодеплой prod выключен с 2026-09-01,
на порту крутится код до PR #36 — публичный инстанс **без аутентификации** (в его БД нет таблицы
`users`). Портфолио `paveldiordits.site` и `lexis.paveldiordits.site` живут на другом сервере,
`37.46.132.95`, за nginx с TLS. Сервис переезжает туда же — под поддомен, за логин, с выкладкой по
образцу сайта. Старый инстанс гасится.

## Целевая схема

```
paveldiordits.site → 37.46.132.95   1 vCPU · 1.8 ГБ · swap 0.9 ГБ · Ubuntu 24.04 · nginx 1.24 · certbot

nginx :80/:443 ─┬─ paveldiordits.site            статика                          (портфолио)
                ├─ lexis.paveldiordits.site      → 127.0.0.1:8765  lexis.service   /var/lib/lexis
                └─ interview.paveldiordits.site  → 127.0.0.1:8770  interview.service  /var/lib/interview   ← новое

GitHub Actions (push в main) ─ npm ci && npm run build ─ tar.gz ─ ssh deploy-interview@host < tar.gz
                                                                      └─ forced command: /usr/local/bin/deploy-interview.sh
                                                                           распаковка → /opt/interview · venv sync · restart · health
```

## Компоненты

### 1. Адрес и TLS
- A-запись `interview.paveldiordits.site` → `37.46.132.95` на reg.ru (руками владельца; DNS уже
  обслуживает `lexis.` и `presentations.` на тот же IP).
- Сертификат: `certbot --nginx -d interview.paveldiordits.site --redirect` после появления записи.
  Корень поддомена, поэтому хеш-роутинг SPA (`#/board/<pool>`) работает без `--base` в Vite.

### 2. Процесс — `deploy/interview.service`
Слепок с `lexis.service` на том же сервере:
- `User=interview` (системный, `nologin`, home `/opt/interview`), `WorkingDirectory=/opt/interview/backend`.
- `ExecStart=/opt/interview/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8770`
  — **только localhost**, наружу через nginx.
- `Environment=INTERVIEW_DB_PATH=/var/lib/interview/interview.db`, `INTERVIEW_CONTENT_DIR=/opt/interview/content`,
  `INTERVIEW_FRONTEND_DIR=/opt/interview/frontend/dist`; `EnvironmentFile=/etc/interview.env` (owner-креды, 600, root).
- Hardening: `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `ReadWritePaths=/var/lib/interview`,
  `MemoryMax=400M`, `Restart=on-failure`, `RestartSec=3`.
- Данные `/var/lib/interview/` переживают выкладку; код `/opt/interview/` перезаписывается целиком.

### 3. nginx — `deploy/nginx-interview.conf`
Server-блок `interview.paveldiordits.site`, всё проксируется на `127.0.0.1:8770` (фронт отдаёт само
приложение через `StaticFiles` на `/`, поэтому `/var/www/` не нужен). Два локейшна:
- `location /` — обычный proxy_pass с `Host`, `X-Real-IP`, `X-Forwarded-For/Proto`.
- `location ~ ^/api/sessions/[0-9]+/events$` — SSE: `proxy_buffering off`, `proxy_cache off`,
  `proxy_read_timeout 1h`, `Connection ''`, `proxy_http_version 1.1`. Без этого nginx копит поток и
  живое обновление оценок залипает.
- `gzip on` для text/css, js, json, svg; `client_max_body_size 8m` (импорт контента через API).
Ставится в `/etc/nginx/sites-available/interview.paveldiordits.site` + симлинк в `sites-enabled`,
`nginx -t && systemctl reload nginx`. Certbot дописывает в этот же файл блок 443 и редирект.

### 4. Выкладка — forced command + tarball через stdin
Отличие от сайта: там сервер забирает готовую статику из репозитория, здесь нужна сборка фронта, а
node на сервере нет (и ставить его на 1 vCPU рядом с lexis не стоит). Поэтому собирает раннер:

**`.github/workflows/deploy.yml`** (переписывается):
1. `actions/checkout`, `setup-node 20`, `npm ci && npm run build` (tsc + vite — типы проверяются тут).
2. `tar czf` из `backend/` (без `.venv`, `__pycache__`, `*.db`), `content/`, `frontend/dist/`,
   `deploy/` → `interview.tar.gz`.
3. Ключ из `secrets.DEPLOY_INTERVIEW_SSH_KEY`, host-key **закреплён явно** в шаге (тот же
   `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1sEThhqUNxeSWgjUtOOuulxk6EMVNAizFdjoCAPlXY`, что у сайта),
   хост из `vars.DEPLOY_HOST` (уже есть в репозитории портфолио; здесь заводится своя переменная).
4. `ssh deploy-interview@$HOST < interview.tar.gz` — forced command читает архив со stdin.
5. Внешняя проверка: `curl https://interview.paveldiordits.site/api/health` → 200, и `GET /api/graph`
   без cookie → 401 (аутентификация включена — именно то, чего не было на NL).
`concurrency: deploy-production`, `cancel-in-progress: false`. `deploy-dev.yml` **удаляется** — dev-контур
не переносится, проверка перед выкладкой — локально (`./run.sh dev` / docker).

**`deploy/deploy-interview.sh`** (на сервере `/usr/local/bin/deploy-interview.sh`, root, 755 — ставится
`install.sh`; принадлежит root, чтобы деплой-пользователь не мог его подменить):
1. Читает stdin в `mktemp` архив; проверяет, что это gzip и в нём есть `backend/app/main.py`,
   `frontend/dist/index.html`, `content/` — иначе выход 1, ничего не трогая.
2. Распаковывает во временный каталог, `rsync -a --delete --exclude .venv` → `/opt/interview/`,
   `chown -R interview:interview`.
3. venv: `python3 -m venv` при отсутствии, `pip install -q -r requirements.txt` от `interview`.
   Хеш `requirements.txt` кэшируется в `/opt/interview/.req.sha256` — pip запускается только при
   изменении (экономия минут на 1 vCPU).
4. `install -m 644 deploy/interview.service /etc/systemd/system/` (юнит едет с кодом — как у lexis),
   `daemon-reload`, `systemctl restart interview`.
5. Health: до 15 с ждёт `curl -fsS http://127.0.0.1:8770/api/health`; при провале печатает
   `journalctl -u interview -n 40` и выходит 1 (раннер краснеет).
Скрипт запускается от **root** через `sudo`: в `authorized_keys` деплой-пользователя ключ прибит к
`command="sudo /usr/local/bin/deploy-interview.sh"`, а в `/etc/sudoers.d/deploy-interview` —
`deploy-interview ALL=(root) NOPASSWD: /usr/local/bin/deploy-interview.sh`. Это единственное, что ключ
умеет: `no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty`.

### 5. Разовый провижининг — `deploy/install.sh`
Идемпотентный, запускается владельцем от root **один раз** (и повторно при правке nginx/юнита):
```
ssh root@37.46.132.95 'bash -s' < deploy/install.sh
```
- Пользователи: `interview` (сервис) и `deploy-interview` (только для CI, `nologin`-shell не
  подходит — sshd нужен shell для forced command, ставится `/bin/sh`).
- Каталоги `/opt/interview`, `/var/lib/interview` с владельцем `interview`; `python3-venv`, `rsync`.
- `/etc/interview.env` (600, root): `INTERVIEW_OWNER_EMAIL`, `INTERVIEW_OWNER_PASSWORD` — берутся из
  переменных `OWNER_EMAIL`/`OWNER_PASSWORD` окружения запуска, иначе пароль генерируется и печатается.
  Owner сидится в БД **один раз** при первом старте (см. `seed.py`), смена потом — только через БД.
- `/usr/local/bin/deploy-interview.sh` (root:root 755), sudoers-строка, `authorized_keys` с forced
  command для публичного ключа из `DEPLOY_PUBKEY` (переменная окружения запуска).
- nginx: копирует `nginx-interview.conf`, симлинк, `nginx -t`, `reload`. Certbot **не** запускается
  автоматически — отдельная команда после DNS (печатается в конце).
- Не запускает деплой: первый код приедет из GitHub Actions.

### 6. Секреты и переменные
| Где                                                         | Что                                         |
|-------------------------------------------------------------|---------------------------------------------|
| локально `.deploy/interview_deploy_key{,.pub}` (gitignored) | новая пара ed25519 только для этого сервера |
| GitHub secret `DEPLOY_INTERVIEW_SSH_KEY`                    | приватный ключ                              |
| GitHub var `DEPLOY_HOST`                                    | `37.46.132.95`                              |
| сервер `/etc/interview.env`                                 | owner-креды                                 |
Старые секреты `SSH_HOST/SSH_USER/SSH_PRIVATE_KEY/SSH_KNOWN_HOSTS/SSH_PORT/OWNER_PASSWORD` удаляются
после успешного первого деплоя — чтобы забытый workflow не смог целиться в NL.

### 7. Снос старого — только после зелёного health на новом адресе
На NL `45.114.62.236` (доступен через KZ-squid):
1. Архив: `scp` обеих БД (`/var/lib/interview/interview.db`, `/var/lib/interview-dev/interview.db`)
   в `~/dev/docs/infra/servers/archive/interview-nl-2026-09-09/` — решение «чистый старт» обратимо.
2. `systemctl disable --now interview interview-dev`, удаление юнитов, `daemon-reload`.
3. `rm -rf /opt/interview /opt/interview-dev /var/lib/interview /var/lib/interview-dev ~deploy/interview-src*`.
4. `ufw delete allow 8800/tcp`, `ufw delete allow 8801/tcp`.
5. Workflow `Deploy` включается обратно (`gh workflow enable Deploy`) — теперь он целится в новый сервер.

### 8. Документация
- `DEPLOY.md` переписывается под новую схему (сервер, поддомен, forced command, provisioning, откат).
- `README.md`: адрес сервиса и блок деплоя, если упоминает `:8800`.
- `~/dev/docs/infra/servers/servers.yaml`: третий узел `37.46.132.95` — nginx, lexis, interview,
  deploy-пользователи, и что его **нет в ACL squid** (SSH только из домашней сети/через VPN).
- Память `prod-deploy-disabled` обновляется: деплой включён, цель — новый сервер.

## Решения и отвергнутые альтернативы
- **Поддомен, не подпуть.** `paveldiordits.site/interview` требует `--base` в Vite и правки хеш-роутов —
  не проверено; lexis уже задал паттерн поддомена.
- **Сборка на раннере, не на сервере.** Node на сервере нет; `vite build` на 1 vCPU / 1.8 ГБ рядом с
  lexis (`MemoryMax=1200M`) — риск OOM ради экономии одного шага в CI.
- **Tarball через stdin, не rsync.** Rsync требует shell без forced command → ключ раннера получает
  произвольные команды. Stdin сохраняет свойство «ключ умеет ровно одно».
- **Чистая БД, не миграция.** Обе NL-базы — тестовые (5 сессий, имена «Жора», «ч»), prod-база от 11 июня
  старой схемы. Контент засеивается из `content/`. Архивная копия снимается — решение обратимо.
- **Без basic-auth поверх.** Аутентификация в приложении есть (#36), гостевые ссылки (#83/#85) basic-auth
  сломал бы.
- **Dev-контур не переносится.** Один боевой экземпляр на сервере сайта; проверка перед выкладкой локально.

## Ограничения и риски
- **Память.** 1799 МБ, занято 501. `interview` укладывается в ~150–200 МБ RSS, потолок 400M. Формально
  `1200 + 400 > 1799 − система`, но одновременного пика нет, swap 899 МБ страхует. Если станет тесно —
  опустить `MemoryMax` lexis до 900M (одна строка, вне этой работы).
- **1 vCPU.** pip install при смене requirements — десятки секунд; кэш по хешу ограничивает это редкими
  выкладками. Health-check ждёт до 15 с — старт с импортом 108 нод укладывается.
- **SSH к серверу из сети X5 невозможен** (ни напрямую, ни через squid — IP не в ACL). Серверные шаги
  провижининга выполняет владелец через `!`-команды; CI-деплой от сети не зависит.
- **Первый старт без `/etc/interview.env`** → приложение сгенерирует случайный owner-пароль в лог.
  `install.sh` создаёт файл до первого деплоя, чтобы этого не случилось.

## Проверка
- Локально: `bash -n` на всех скриптах, `shellcheck` при наличии; `nginx -t` — на сервере в `install.sh`;
  workflow — `actionlint` при наличии, иначе первый прогон.
- Прогон упаковки локально: `tar` собирается из dev-дерева, `deploy-interview.sh` проверяет его состав
  (валидатор архива — отдельная функция, тестируется без сервера).
- `pytest` не затрагивается (кода приложения правка не касается), но гоняется как регрессия.
- Боевой гейт: `https://interview.paveldiordits.site/api/health` → 200; `/api/graph` без cookie → 401;
  вход owner-кредами → доска открывается; SSE — открыть сессию в двух вкладках, оценка видна во второй
  без перезагрузки.
- Снос NL — только после боевого гейта.
