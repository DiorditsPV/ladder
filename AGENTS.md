# AGENTS.md — гид для агентов по проекту Ladder

Точка входа для любого агента, работающего в этом репозитории. Человеку — см. `README.md`.

## Что это
Локальная доска самоподготовки по темам — **Ladder**: тема → колонки × свои уровни (ступени) → карточки → чек-лист
«знаю / повторить / не знаю». Другого режима нет: кандидатов, сессий, оценок и отчётов по ним в продукте
не осталось. Ядро — **swimlane-доска вопросов**: вертикальные колонки по направлениям (Фреймворки /
Базы данных / Python / Платформа), внутри — карточки, ранжированные по уровням сложности, которые
задаёт сам пул (`levels` в `pool.yaml`, 2–8; без `levels` — base → junior → middle → senior).
Каждая карточка = вопрос/задача + ответ. Контент импортируется из Markdown/JSON.
Только локально. Бэкенд: **FastAPI + SQLite**. Фронт: **React + Vite + React Flow**.

Размер банка считается на лету через `GET /api/graph` (на момент написания ~60 нод:
frameworks 29, databases 22, python 5, platform 4) — точные числа не держим в доке, они дрейфуют.

## Быстрый старт
```bash
./run.sh                 # venv + сборка фронта (если надо) + uvicorn → http://localhost:8000
./run.sh --build         # форс-пересборка фронта
```
Dev (hot reload): `uvicorn app.main:app --reload --port 8000` (из `backend/`, venv) + `npm run dev` (из
`frontend/`, Vite :5173 проксирует `/api` на :8000). Деплой на https://interview.paveldiordits.site — только ручной запуск `Deploy`
(см. `DEPLOY.md`); merge в `main` ничего не выкладывает; фичи идут через `dev`.

## Карта репозитория
- `backend/app/` — `models.py` (pydantic `Node`, `extra="forbid"`), `importer.py` (.md+.json через
  python-frontmatter), `pools.py` (таксономия пула), `sync.py` (`content/` → БД), `db.py` (SQLite:
  направления, банк, чек-лист), `auth.py`/`tenancy.py`, `main.py` (FastAPI).
- `frontend/src/` — `router.ts`/`Router.tsx` (hash-роутер: `#/`, `#/board/<pool>`, `#/bank/<pool>`),
  `pages/BoardPage.tsx` (доска пула: состояние, `buildNodes`, шапка, панель ⚙), `pages/`
  (`HomePage`, `BankPage`, `PageShell`), `api.ts` (обёртки над `/api`),
  `layout.ts` (`swimlaneLayout(nodes, pool)`, `subOf`),
  `types.ts` (`QNode`, `PoolConfig` + `blockOrder/blockLabel/blockColor/subLabel` и
  `levelOrder/levelLabel/levelColor` вместо констант, `Block = string`, `Difficulty/Kind`),
  `report.ts` (HTML-экспорт банка), `styles.css` (CSS-переменные тем), `main.tsx`.
  `components/` — узлы канвы (QuestionNode, BlockGroupNode, SubHeadNode, BandsNode, GuidesNode) и
  оверлеи/панели (DetailDrawer, BankBrowser, UploadModal, ShortcutsHelp).
  Тесты: `frontend/smoke.mjs`, `frontend/screenshot.mjs`.
- `content/<pool>/pool.yaml` — таксономия и веса пула; `content/<pool>/<block>/*.md|*.json` — его вопросы.
- `backend/tests/` — pytest (`test_app.py` импорт/API, `test_nodes.py` CRUD нод, `test_pools.py`/
  `test_pool_crud.py`/`test_levels.py` направления и уровни, `test_sync.py`, `test_progress.py`
  чек-лист, `test_auth.py` auth/RBAC/тенант-изоляция). `Q_IDEAS.txt` — реестр вопросов + идеи.
- `REPORT.md` — отчёт-исследование и архитектурные решения. `.claude/skills/` — скиллы (ниже).

## API (FastAPI)
Граф/контент: `GET /api/graph` (ноды + ошибки импорта), `GET /api/pools`, `GET /api/graph?pool=`,
`POST /api/import`, `POST/PUT/DELETE /api/nodes`. Направления: `POST /api/pools` (ровно одно из
`preset` — существующее направление, копируются колонки и вопросы, — или `blocks` — свои колонки
без вопросов; id — транслитерация названия), `PUT /api/pools/{id}` (название/описание/`blocks`:
`[{id?, label, color, subblocks?: [{id?, label}]}]` — у существующих колонок id передаётся как есть,
новые получают id из названия; колонка, которой нет в списке, удаляется вместе с вопросами,
исчезнувшая под-колонка оставляет вопросы в колонке без под-колонки), `DELETE /api/pools/{id}`
(вопросы удаляются, id остаётся занятым tombstone'ом), `POST /api/pools/sync` (owner: перечитать
`content/`). Чек-лист: `GET /api/progress?pool=`, `PUT/DELETE /api/progress/{node_id}`.
Аутентификация: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
`GET/POST /api/users` (owner). Служебное: `GET /api/health`. Полные схемы — Swagger UI на `/docs`.

## Модель ноды и формат контента
Frontmatter (ключи алфавитные, `tags` — block-style): `id`, `kind` (question|task), `block`
(значения — блоки из `content/<pool>/pool.yaml` того пула; data-engineer: frameworks|databases|python|platform,
system-analyst: requirements|modeling|data|integration, data-engineer-x5: python|sql|spark|airflow|clickhouse|ai),
`subblock`, `topic`, `title` (короткий заголовок карточки),
`difficulty` (один из `levels[].id` пула; по умолчанию base|junior|middle|senior), `weight`, `tags` (1–3), для `task` — `starterCode`, `rubric`.
Тело: `## Вопрос` / `## Ответ` (для задач — `## Задача` / `## Эталон`). Не начинай строки тела с `#`
вне блоков кода (это маркеры разбиения). Полный текст — в drawer; на карточке только `title` + теги.

**Под-колонки** внутри блока задаются полем `subblock`, порядок и подписи — в `subblocks` соответствующего
блока в `content/<pool>/pool.yaml`: data-engineer → frameworks: `airflow|pyspark|dbt|streaming`,
databases: `sql|dbms|storage|formats`; data-engineer-x5 → sql: `queries|indexes`; system-analyst — свои
под-колонки по блокам, см. `pool.yaml`.

## Конвенции и грабли (ВАЖНО)
- **Ground truth — через `cat`/`grep`/`/api/graph`, НЕ через Read-инструмент**: контент-файлы
  нормализуются скриптами, и Read может отдать устаревший кэш.
- **Правки контента — через `python-frontmatter`** (`backend/.venv`), запись
  `f.write_text(frontmatter.dumps(post) + "\n")` — сохраняет нормализованный формат.
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
- Удаление seed-карточки из UI прячет её (`hidden`, `source=user`) — файл остаётся источником;
  чтобы удалить насовсем, удали файл и сделай sync.

## Проверка изменений
Используй скилл **interview-verify** (или вручную): import 0 ошибок (`/api/graph`) → `pytest` →
при правке фронта `npm run build` + `npm run i18n:check` (ключи `t("…")` есть в `src/i18n/en.ts`) + `npm run smoke` (нужен сервер :8000) → (пере)запуск uvicorn.
При переименовании нод/тегов/классов, на которые опирается smoke — обнови `frontend/smoke.mjs`.

## Скиллы проекта (`.claude/skills/`)
Каждый скилл = `SKILL.md` (+ при необходимости sibling-скрипт на stdlib). Вызывай через Skill-инструмент.

| Скилл                  | Когда                                                | Что делает                                                                                                                                                   |
|------------------------|------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **ladder-topic**       | «разложи тему X / заведи направление / пересобери X» | тема → колонки × свои уровни → карточки в `content/<slug>/` → sync. Скрипт `write_topic.py` (JSON → файлы, матрица покрытия, `--fresh`/дополнение, `--sync`) |
| **interview-ideas**    | «добавь/допиши/реализуй идею»                        | работа с `Q_IDEAS.txt`: add / expand / реализовать `[ ]`→ноды `[x]`. Скрипт `regen_ledger.py` пересобирает реестр                                            |
| **interview-refactor** | «отрефактори/пересмотри сложность/почисти банк»      | ревизия существующих вопросов по сложности/актуальности/подаче. Скрипт `inventory.py`                                                                        |
| **interview-balance**  | «оцени покрытие/где пробелы»                         | матрица subblock×сложность vs веса, поиск дыр. Скрипт `coverage.py`                                                                                          |
| **interview-verify**   | «проверь, что не сломалось»                          | import + pytest + build + smoke + рестарт. Скрипт `check_import.py`                                                                                          |

## Учёт фич
Каталог фич и бэклог ведутся в **GitHub Issues** репозитория (а не в файлах репо). Реализованные
фичи — закрытые issue с пометкой о выполнении; идеи/планы — открытые issue (в т.ч. epic-и
«Платный / командный тир» и «Интеграции РФ»). Карта рынка интеграций остаётся в
[`docs/integrations/`](docs/integrations/README.md).

