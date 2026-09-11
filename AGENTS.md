# AGENTS.md — гид для агентов по проекту Ladder

Точка входа для любого агента, работающего в этом репозитории. Человеку — см. `README.md`.

## Что это
Локальная доска самоподготовки по темам — **Ladder**: тема → колонки × свои уровни (ступени) → карточки → чек-лист
«знаю / повторить / не знаю». Другого режима нет: кандидатов, сессий, оценок и отчётов по ним в продукте
не осталось. Ядро — **swimlane-доска вопросов**: вертикальные колонки по направлениям (Фреймворки /
Базы данных / Python / Платформа), внутри — карточки, ранжированные по уровням сложности, которые
задаёт сам пул (`levels` в `pool.yaml`, 2–8; без `levels` — base → junior → middle → senior).
Каждая карточка = вопрос/задача + ответ. Контент импортируется из Markdown/JSON.
Без входа сайт открывается как демо (два направления, RU/EN, чек-лист в браузере), полный режим — после
входа (см. «Режимы и роли»). Бэкенд: **FastAPI + SQLite**. Фронт: **React + Vite + React Flow**.

Размер банка считается на лету через `GET /api/graph` (на момент написания ~60 нод:
frameworks 29, databases 22, python 5, platform 4) — точные числа не держим в доке, они дрейфуют.

## Быстрый старт
```bash
./run.sh                 # venv + сборка фронта (если надо) + uvicorn → http://localhost:8000
./run.sh --build         # форс-пересборка фронта
```
Dev (hot reload): `uvicorn app.main:app --reload --port 8000` (из `backend/`, venv) + `npm run dev` (из
`frontend/`, Vite :5173 проксирует `/api` на :8000). Деплой на https://ladder.paveldiordits.site — только ручной запуск `Deploy`
(см. `DEPLOY.md`); merge в `main` ничего не выкладывает; фичи идут через `dev`.

## Карта репозитория
- `backend/app/` — `models.py` (pydantic `Node`, `extra="forbid"`), `importer.py` (.md+.json через
  python-frontmatter), `pools.py` (таксономия пула), `sync.py` (засев пресетов `content/` → БД; явное
  обновление — `update=true`), `db.py` (SQLite:
  направления, банк, чек-лист, аккаунты), `auth.py`/`tenancy.py` (`optional_user` — только демо-чтение
  `GET /api/pools` и `GET /api/graph`), `main.py` (FastAPI).
- `frontend/src/` — `router.ts`/`Router.tsx` (hash-роутер: `#/`, `#/demo`, `#/login`, `#/people`,
  `#/board/<pool>`, `#/bank/<pool>`; `redirectFor` — маршруты режима, языковой эффект — пара направления),
  `session.tsx` (`useSession`, `useCan`, `useHomeHref`), `progressStore.ts` (чек-лист: сервер или
  `localStorage`), `poolLang.ts` (`poolsForLang`, `pairOf`),
  `pages/BoardPage.tsx` (доска пула: состояние, `buildNodes`, шапка, панель ⚙), `pages/`
  (`Landing`, `HomePage`, `BankPage`, `PeoplePage`, `PageShell`), `api.ts` (обёртки над `/api`),
  `layout.ts` (`swimlaneLayout(nodes, pool)`, `subOf`),
  `types.ts` (`QNode`, `PoolConfig` + `blockOrder/blockLabel/blockColor/subLabel` и
  `levelOrder/levelLabel/levelColor` вместо констант, `Block = string`, `Difficulty/Kind`),
  `theme.tsx` (тема на всё приложение, светлая по умолчанию; кнопка `ThemeToggle` в шапках; оформления доски — «Изыскания» 58
  по умолчанию и «Брутализм в цвете» 37), `floating.ts` (`useFloatingWindow` — плавающие окна над доской: карточка по центру
  и фильтры), `styles.css` (CSS-переменные тем), `main.tsx`.
  `components/` — узлы канвы (QuestionNode, BlockGroupNode, SubHeadNode, BandsNode, GuidesNode) и
  оверлеи/панели (DetailDrawer — открытая карточка по центру или справа, BankBrowser, UploadModal, ShortcutsHelp,
  AccountMenu, ChangePasswordModal).
  Тесты: `frontend/smoke.mjs`, `frontend/screenshot.mjs`.
- `content/` — **только пресеты** (`data-engineer`, `system-analyst` и их `-en`; spec
  `docs/superpowers/specs/2026-09-11-content-in-db-design.md`): `content/<pool>/pool.yaml` — таксономия и веса,
  `content/<pool>/<block>/*.md|*.json` — вопросы. Остальные направления (Kafka, Spark, X5, новые) живут только в БД
  и заносятся через MCP/API; источник правды — база на сервере.
- `backend/tests/` — pytest (`test_app.py` импорт/API и состав `content/`, `test_nodes.py` CRUD нод, `test_pools.py`/
  `test_pool_crud.py`/`test_levels.py` направления и уровни, `test_sync.py` засев/обновление, `test_progress.py`
  чек-лист, `test_auth.py` auth/RBAC/тенант-изоляция, `test_demo_access.py` анонимное демо-чтение,
  `test_accounts.py` пароли и аккаунты, `test_write_topic.py` скрипт `ladder-topic`, `test_backup_script.py`
  снимки и счётчики `deploy/ladder-backup.py`). `Q_IDEAS.txt` — реестр вопросов + идеи.
- `deploy/` — выкладка и страховка контента (см. `DEPLOY.md`, «Контент и бэкапы»): `deploy-ladder.sh` (снимок до
  рестарта, сверка карточек после), `ladder-backup.py` + `ladder-backup.{service,timer}` (ночные снимки),
  `install-backup.sh`, `backup-pull.sh` (снимок и JSON к себе), `export_json.py` (выгрузка направлений через API).
- `backend/tests/test_api_crud.py` — CRUD API для MCP (направление по id, карточки со всеми полями и переносом,
  фильтры, топики, теги, права).
- `tools/ladder-mcp/` — MCP-сервер поверх API (`ladder_mcp/server.py` — 25 инструментов, включая `sync_from_files`
  для пресетов, `client.py` — HTTP-клиент
  с логином, `structure.py` — read-modify-write колонок и уровней); тесты `tools/ladder-mcp/tests` (in-process
  против настоящего FastAPI), проверка по stdio — `scripts/stdio_smoke.py`. Подробно — его README.
- `REPORT.md` — отчёт-исследование и архитектурные решения. `.claude/skills/` — скиллы (ниже).

## API (FastAPI)
Граф/контент: `GET /api/graph` (ноды + ошибки импорта), `GET /api/pools`, `GET /api/graph?pool=`,
`POST /api/import`, `POST/PUT/DELETE /api/nodes`. Направления: `POST /api/pools` (ровно одно из
`preset` — существующее направление, копируются колонки и вопросы, — или `blocks` — свои колонки
без вопросов; id — транслитерация названия), `PUT /api/pools/{id}` (название/описание/`blocks`:
`[{id?, label, color, subblocks?: [{id?, label}]}]` — у существующих колонок id передаётся как есть,
новые получают id из названия; колонка, которой нет в списке, удаляется вместе с вопросами,
исчезнувшая под-колонка оставляет вопросы в колонке без под-колонки), `DELETE /api/pools/{id}`
(вопросы удаляются, id остаётся занятым tombstone'ом), `POST /api/pools/sync` (owner: засев из `content/` —
только недостающие направления и карточки; `update=true` — явное обновление пресета из файлов, `pool=<id>` — одно
направление, 404 без каталога; `dry_run=true` — прогон на копии БД, ответ — отчёт `created/updated/config_changed/
nodes_upserted/nodes_changed/skipped/hidden/conflicts/errors`; у направлений в `GET /api/pools[/{id}]` флаг `has_files` —
есть пресет в `content/`, только у них на главной пункт «Обновить из файлов»: предпросмотр → подтверждение). Чек-лист: `GET /api/progress?pool=`, `PUT/DELETE /api/progress/{node_id}`.
Аутентификация: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
`POST /api/auth/password` (свой пароль: неверный текущий → 403, не 401; новый короче 8 → 422; остальные сессии
отзываются). Аккаунты (owner): `GET /api/users`, `POST /api/users` (без `password` — одноразовый пароль в ответе,
один раз; роль по умолчанию viewer), `POST /api/users/{id}/password` (сброс: новый одноразовый, сессии отозваны),
`DELETE /api/users/{id}` (вместе с сессиями и чек-листом; себя — 400). Без сессии доступны только
`GET /api/pools` (направления с `demo: true`, без `progress`) и `GET /api/graph?pool=<демо>` — остальное 401.
Для MCP и скриптов (spec 2026-09-11-api-mcp): `GET /api/pools/{id}`; `POST /api/pools` принимает явный `id` (занят —
409); `GET /api/nodes?pool=&block=&subblock=&difficulty=&topic=&tag=&kind=&q=&include_hidden=` и `GET /api/nodes/{id}`
(все поля + `hidden`, `source`); `POST /api/nodes` — ещё `id` (явный, 409), `subblock`, `weight`, `starterCode`,
`rubric`, ответ — вся карточка; `PUT /api/nodes/{id}` — любые поля и перенос (`pool`, `block`, `subblock`,
`difficulty`; `""` снимает `subblock`/`title`/`starterCode`; прежняя под-колонка при переносе снимается), ответ
`{updated, node}`; теги — slug, не больше 5. Топики: `GET /api/pools/{id}/topics`, `PUT|DELETE
/api/pools/{id}/topics/{topic}` (переименовать/удалить у всех карточек, `block` — сузить колонкой). `GET /api/tags` —
словарь концептов (`app/tags.py`) + использованные в направлении. Структуру колонок и уровней MCP правит через
`PUT /api/pools/{id}` (read-modify-write). Правка через API помечает карточку `source=user` — sync её не перетирает.
Служебное: `GET /api/health`. Полные схемы — Swagger UI на `/docs`.

## Модель ноды и формат контента
Frontmatter (ключи алфавитные, `tags` — block-style): `id`, `kind` (question|task), `block`
(значения — колонки направления; у пресетов — из `content/<pool>/pool.yaml`: data-engineer:
frameworks|databases|python|platform, system-analyst: requirements|modeling|data|integration; у остальных — MCP `get_direction`),
`subblock`, `topic`, `title` (короткий заголовок карточки),
`difficulty` (один из `levels[].id` пула; по умолчанию base|junior|middle|senior), `weight`, `tags` (1–3), для `task` — `starterCode`, `rubric`.
Тело: `## Вопрос` / `## Ответ` (для задач — `## Задача` / `## Эталон`). Не начинай строки тела с `#`
вне блоков кода (это маркеры разбиения). Полный текст — в drawer; на карточке только `title` + теги.

**Под-колонки** внутри блока задаются полем `subblock`, порядок и подписи — в `subblocks` соответствующего
блока в `content/<pool>/pool.yaml`: data-engineer → frameworks: `airflow|pyspark|dbt|streaming`,
databases: `sql|dbms|storage|formats`; system-analyst — свои под-колонки по блокам, см. `pool.yaml`.

**Флаги направления** в `pool.yaml` (необязательные): `demo: true` — видно без входа; `lang` — язык контента
(`ru` по умолчанию или `en`); `translation_of: <id>` — это перевод. Демо сейчас — `data-engineer` и `system-analyst`
с переводами `data-engineer-en` / `system-analyst-en` (id карточки = id оригинала + `-en`; колонки, уровни, теги —
как у оригинала). Флаги — свойства контента: из файлов их переносит явное обновление пресета (`update=true`), из UI
они не правятся.

## Режимы и роли
Режим следует из сессии (spec `docs/superpowers/specs/2026-09-11-demo-and-access-design.md`).
- **Демо (без входа):** `#/` — стартовый экран, `#/demo` — демо-направления на языке интерфейса; доска и банк —
  только демо-направлений (прочие адреса → `#/demo`); чек-лист в `localStorage` (`ladder.progress.<pool>`), на сервер
  ничего не пишется; правок нет, локальное «Скрыть» остаётся.
- **Вход** — `#/login` (незаметная ссылка «Вход» на стартовом экране); после входа `#/demo` и `#/login` ведут на `#/`.
- **Роли:** owner — всё, включая `#/people` (аккаунты); member — ещё и правка контента; viewer — чтение всех направлений
  и свой чек-лист на сервере. Фронт прячет недоступные действия через `useCan()`; прогресс — `useProgressStore()`.
- **Язык контента:** при EN-интерфейсе главная показывает перевод вместо оригинала; переключатель на доске и в банке
  уводит на пару (`#/board/data-engineer` ↔ `#/board/data-engineer-en`). Прогресс у оригинала и перевода раздельный.

## Конвенции и грабли (ВАЖНО)
- **Ground truth — через `cat`/`grep`/`/api/graph`, НЕ через Read-инструмент**: контент-файлы
  нормализуются скриптами, и Read может отдать устаревший кэш.
- **Новый контент — в живую базу через MCP/API** (`tools/ladder-mcp`, `ladder-topic --upload`), не файлами; каталог
  в `content/` — только для пресета (`test_content_holds_only_presets` фиксирует состав).
- **Правки пресетов — через `python-frontmatter`** (`backend/.venv`), запись
  `f.write_text(frontmatter.dumps(post) + "\n")` — сохраняет нормализованный формат. На сервер правка попадает
  только явным `POST /api/pools/sync?pool=<id>&update=true` (сначала `dry_run=true`) — деплой лишь засевает.
- **Рёбер/ветвления нет** — поле `edges` удалено из модели; не добавляй.
- **Теги — только из 17 сквозных концептов**, 1–3 на ноду, без тех-имён (технология видна по колонке):
  architecture, orchestration, optimization, partitioning, deployment, storage, streaming, consistency,
  data-modeling, quality, distributed, sql, monitoring, memory, file-formats, domain, concurrency.
- `Node` имеет `extra="forbid"` → новое поле ноды = правка `models.py` + `types.ts` + миграция контента.
- Новый тип ноды на канве = регистрация в `nodeTypes` (BoardPage.tsx).
- Изменения контента не требуют пересборки фронта (данные грузятся из `/api/graph` в рантайме);
  изменения `frontend/src` — требуют `npm run build`.
- Чек-лист разбора: статусы `known|review|unknown` в таблице `progress` (per-user), хоткеи `1/2/3`,
  `n` — следующая неразобранная карточка. Счётчики колонок и рядов (уровней) — по `known`.
  Статусы ставят HUD и drawer; оценок 1–5 в продукте больше нет.
- Открытая карточка — два режима (`ladder.cardMode`): по центру (по умолчанию) — плавающее окно над доской со скримом: ответ
  виден сразу, ‹ › по той же матрице, что 1/2/3 (текущая на доске встаёт сбоку от окна — где свободнее, по его реальному
  прямоугольнику), HUD скрыт, пока оно открыто; тащится за шапку (`ladder.cardPos` — смещение от центра), размер — уголком
  и правым краем (`ladder.cardSize`), двойной клик — центр / размер по умолчанию; и справа (панель, ширина — ручкой,
  `ladder.drawerWidth`). Корень обоих — `.drawer` + модификатор `.drawer--center|--side`; smoke (окно браузера 1440×900) идёт
  по центру и перед шагами с HUD закрывает её Esc.
- Фильтры — плавающее окно `.filterpanel` (кнопка «Фильтры» в шапке): тащится за шапку (`ladder.filtersPos`), не выходит за
  канву, двойной клик — на место у правого края. С окном карточки перекрываются — сверху то, с которым работали последним.
  ⚙ — кнопка `.setbtn` в шапке доски рядом с темой; в ••• — шпаргалка клавиш и ссылка на банк.
- Удаление seed-карточки из UI прячет её (`hidden`, `source=user`) — файл остаётся источником, засев её не вернёт;
  чтобы удалить насовсем, удали файл и сделай явное обновление пресета (`update=true`).
- Новое мутирующее действие в UI прячь по `useCan()`: иначе в демо оно упрётся в 401, у viewer — в 403.
  Статус карточки — только через `useProgressStore()`, не через `api.setProgress` напрямую.

## Проверка изменений
Используй скилл **interview-verify** (или вручную): import 0 ошибок (`/api/graph`) → `pytest` →
при правке фронта `npm run build` + `npm run i18n:check` (ключи `t("…")` есть в `src/i18n/en.ts`) + `npm run smoke` (нужен сервер :8000) → (пере)запуск uvicorn.
Smoke идёт от демо без входа (стартовый экран, демо-доска, EN-пара) через вход по `#/login` к полному режиму и в конце
заводит viewer'а на «Люди», входит им и удаляет — гоняй на свежей БД (`INTERVIEW_DB_PATH` во временный файл).
При переименовании нод/тегов/классов, на которые опирается smoke — обнови `frontend/smoke.mjs`.

## Скиллы проекта (`.claude/skills/`)
Каждый скилл = `SKILL.md` (+ при необходимости sibling-скрипт на stdlib). Вызывай через Skill-инструмент.

| Скилл                  | Когда                                                | Что делает                                                                                                                                                                       |
|------------------------|------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **ladder-topic**       | «разложи тему X / заведи направление / пересобери X» | тема → колонки × свои уровни → карточки JSON → живая база. Скрипт `write_topic.py` (`--check` матрица покрытия, `--upload` через API, `--overwrite`; `--files` — только пресеты) |
| **interview-ideas**    | «добавь/допиши/реализуй идею»                        | работа с `Q_IDEAS.txt`: add / expand / реализовать `[ ]`→ноды `[x]`. Скрипт `regen_ledger.py` пересобирает реестр                                                                |
| **interview-refactor** | «отрефактори/пересмотри сложность/почисти банк»      | ревизия существующих вопросов по сложности/актуальности/подаче. Скрипт `inventory.py`                                                                                            |
| **interview-balance**  | «оцени покрытие/где пробелы»                         | матрица subblock×сложность vs веса, поиск дыр. Скрипт `coverage.py`                                                                                                              |
| **interview-verify**   | «проверь, что не сломалось»                          | import + pytest + build + smoke + рестарт. Скрипт `check_import.py`                                                                                                              |

## Учёт фич
Каталог фич и бэклог ведутся в **GitHub Issues** репозитория (а не в файлах репо). Реализованные
фичи — закрытые issue с пометкой о выполнении; идеи/планы — открытые issue (в т.ч. epic-и
«Платный / командный тир» и «Интеграции РФ»). Карта рынка интеграций остаётся в
[`docs/integrations/`](docs/integrations/README.md).

