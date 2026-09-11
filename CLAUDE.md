# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Подробный гид для агентов — `AGENTS.md` (карта репозитория, скиллы, конвенции контента,
> учёт фич в GitHub Issues). Здесь — выжимка для быстрого старта. При расхождении доверяй `AGENTS.md`.

## Что это
Локальная доска самоподготовки по темам — **Ladder**: тема раскладывается на колонки × свои уровни (ступени),
карточки разбираются чек-листом «знаю / повторить / не знаю». Ядро —
**swimlane-доска вопросов**: вертикальные колонки по направлениям (frameworks / databases /
python / platform), внутри карточки ранжированы по уровням сложности — рядам, которые задаёт сам пул
(`levels` в `pool.yaml`, 2–8; без `levels` — base → junior → middle → senior).
Карточка = вопрос/задача + ответ. Рёбер/ветвления между вопросами нет — это доска,
а не граф зависимостей. Контент импортируется из Markdown/JSON. Без входа сайт открывается как демо
(два направления, RU/EN, чек-лист в браузере), полный режим — после входа; см. «Режимы и роли».
Бэкенд **FastAPI + SQLite**, фронт **React + Vite + React Flow (@xyflow)**.

## Команды

```bash
./run.sh                 # prod-профиль: venv + сборка фронта (если нет dist) + uvicorn → :8000
./run.sh --build         # форс-пересборка фронта
./run.sh dev             # dev-профиль: порт 8001, своя БД interview-dev.db, --reload

docker compose up -d --build  # тот же сервис в контейнере → :8000 (логин admin/admin)
docker compose down -v        # остановить и снести том с БД

# Бэкенд-тесты (из backend/, в активированном venv)
cd backend && . .venv/bin/activate && pytest -q
pytest tests/test_app.py -q                       # один файл
pytest tests/test_app.py::test_name -q            # один тест

# Фронт
cd frontend && npm run build     # tsc --noEmit + vite build (типы проверяются здесь)
npm run dev                      # Vite :5173, проксирует /api на :8000
npm run smoke                    # headless playwright-smoke реального рантайма; нужен сервер :8000 (лучше на свежей БД)
```

Dev hot-reload вручную: `uvicorn app.main:app --reload --port 8000` (из `backend/`) + `npm run dev`.

## Архитектура

**Бэкенд** (`backend/app/`) — поток данных «контент-файлы → импорт → БД → API → доска»:
- `pools.py` — читает `content/<pool>/pool.yaml` (блоки, под-колонки, цвета, веса, уровни `levels`) — таксономия пула.
  `pool.yaml` — сид таблицы `pools` (как контент для `nodes`); в рантайме направления читаются из БД
  (`db.list_pools`), создаются/правятся/удаляются через `POST/PUT/DELETE /api/pools`. Колонки —
  данные направления: `POST` принимает ровно одно из `preset` / `blocks`, `PUT` — `blocks`
  (`[{id?, label, color, subblocks?}]`; колонка вне списка удаляется с вопросами, исчезнувшая
  под-колонка оставляет вопросы в колонке). Редактор — `frontend/src/components/BlocksEditor.tsx`.
- `importer.py` — парсит `content/<pool>/<block>/*.md|*.json` через `python-frontmatter` в `Node`,
  проверяя block/subblock/difficulty по `pool.yaml`; `pool` ноды ставится по каталогу, не во frontmatter.
- `sync.py` — `content/ → БД` без рестарта: при старте и по `POST /api/pools/sync` (owner) создаёт новые
  направления, обновляет конфиги, upsert-ит seed-ноды по id; ноды с `source='user'` (созданные или правленные
  в UI) не трогает — конфликт id идёт в отчёт; исчезнувшие из файлов seed-ноды прячет (`hidden`), вернувшиеся
  разворачивает; при ошибках импорта в пуле скрытие пропускает. `/api/graph` скрытые не отдаёт.
- `models.py` — pydantic `Node` с `extra="forbid"`: добавление поля ноды = правка `models.py`
  **И** `frontend/src/types.ts` **И** миграция всех контент-файлов, иначе импорт падает.
- `db.py` — SQLite: направления, банк вопросов, пользователи и чек-лист (`progress`).
  `tenancy.py` — изоляция тенантов. `auth.py` — пароли, server-side auth-сессии, RBAC;
  `optional_user` (пользователь или None без 401) — только в `GET /api/pools` и `GET /api/graph` (демо-чтение).
- `main.py` — FastAPI; полные схемы ручек в Swagger UI на `/docs`. CRUD для MCP: `GET /api/pools/{id}`,
  `GET /api/nodes` (фильтры) и `GET /api/nodes/{id}`, `POST/PUT /api/nodes` со всеми полями и переносом,
  топики `/api/pools/{id}/topics[/{topic}]`, словарь тегов `GET /api/tags` (`tags.py`).

**MCP** (`tools/ladder-mcp/`) — сервер поверх API: направления, колонки/под-колонки, уровни, топики, вопросы
(24 инструмента). Тесты: `backend/.venv/bin/python -m pytest -q tools/ladder-mcp/tests -p no:cacheprovider`
(нужен `pip install -r tools/ladder-mcp/requirements.txt`). Новую ручку, которую должен уметь MCP, — добавь и в
`ladder_mcp/server.py`, и в `TOOL_NAMES`, и в тест полного цикла.

**Фронт** (`frontend/src/`) — данные грузятся из `/api/graph` в рантайме:
- `router.ts`/`Router.tsx` — hash-роутер: `#/`, `#/demo`, `#/login`, `#/people`, `#/board/<pool>`, `#/bank/<pool>`;
  `redirectFor` уводит с маршрутов, недоступных режиму, языковой эффект — на пару направления.
- `session.tsx` — контекст сессии: `useSession()` (`user | null`, `refresh`, `logout`), `useCan()` (права режима/роли),
  `useHomeHref()`; `progressStore.ts` — чек-лист на сервере или в `localStorage`; `poolLang.ts` — `poolsForLang`, `pairOf`.
- `pages/BoardPage.tsx` — доска пула: состояние, `buildNodes`, шапка (фильтры, тема, ⚙, RU/EN, ••• — шпаргалка и банк),
  панель ⚙, окно фильтров.
- `pages/` — `Landing` (стартовый экран), `HomePage`, `BankPage`, `PeoplePage` (аккаунты, owner), `PageShell`.
- `layout.ts` — `swimlaneLayout(nodes, pool)`: порядок блоков, под-колонок и уровней из `pool.yaml` (`levelOrder`), `subOf`.
- `types.ts` — `QNode`, `PoolConfig` + `blockOrder/blockLabel/blockColor/subLabel` вместо констант,
  `Block = string`, перечисления `Difficulty/Kind`, `levelOrder/levelLabel/levelColor`.
- `components/` — узлы канвы (QuestionNode, BlockGroupNode, SubHeadNode …) + DetailDrawer (открытая карточка, два режима — ниже).
- `theme.tsx` — цветовая тема на всё приложение (светлая по умолчанию, ключ `ladder.theme`) и оформление доски
  `data-design`; выставляются до первой отрисовки (`initTheme` в `main.tsx`), переключатель `ThemeToggle` — в шапке каждой страницы.
  Оформлений два: «Изыскания» (58, по умолчанию) и «Брутализм в цвете» (37); тёмная тема одна на оба (`design-themes.css`).
- `floating.ts` — `useFloatingWindow`: плавающие окна над доской (карточка по центру, фильтры) — тащатся за шапку,
  место в `localStorage` как смещение от места по умолчанию, рисуются поджатыми в область доски.

**Уровни** — `levels` в `pool.yaml` (`[{id, label}]`, порядок = по возрастанию); `difficulty` карточки должна быть
одним из их `id`, иначе импорт падает. Хелперы фронта — `levelOrder/levelLabel/levelColor` рядом с `blockOrder`.

**Чек-лист разбора** — карточка имеет статус `known | review | unknown` (таблица `progress`, своя у
каждого пользователя; `PUT/DELETE /api/progress/{node_id}`, `GET /api/progress?pool=`, сводка `progress` в `/api/pools`).
Хоткеи `1/2/3` ставят статус и ведут к следующей карточке, `n` — к следующей неразобранной.
Статусы ставят HUD внизу доски и drawer; оценок 1–5 и режима интервью в продукте нет.
Открытая карточка — два режима (`ladder.cardMode`, ⚙ «Карточка вопроса» или кнопка в её шапке): **по центру** (по умолчанию) —
плавающее окно над доской с лёгким скримом: ответ виден сразу, ‹ › по матрице (текущая на доске встаёт сбоку от окна, где
свободнее), HUD на это время скрыт; окно тащится за шапку (`ladder.cardPos` — смещение от центра), размер тянется уголком
и правым краем (`ladder.cardSize`, по умолчанию ширина min(760px, 58vw)), двойной клик — центр / размер по умолчанию;
**справа** — панель, ширина тянется ручкой (`ladder.drawerWidth`). Корень обоих — `.drawer` + `.drawer--center|--side`.
Фильтры — плавающее окно `.filterpanel` (`ladder.filtersPos`, двойной клик по шапке — на место у правого края).

**Режимы и роли** (spec 2026-09-11) — режим следует из сессии. Без входа — демо: `#/` стартовый экран,
`#/demo` демо-главная (только направления с `demo: true`), доска и банк — только демо-направлений (остальные
адреса → `#/demo`), чек-лист в `localStorage` (`ladder.progress.<pool>`), правок нет. Вход —
`#/login`; `#/people` — аккаунты (owner): заведение с одноразовым паролем, сброс, удаление; свой пароль — «Сменить
пароль» (меню аккаунта на главной, ⚙ на доске). Роли: owner — всё; member — ещё и правка контента; viewer —
чтение всех направлений и свой чек-лист. Анонимно бэкенд отдаёт ровно `GET /api/pools` (демо, без `progress`) и
`GET /api/graph?pool=<демо>`, остальное — 401. Флаги направления в `pool.yaml`: `demo` (bool), `lang` (`ru|en`),
`translation_of` (id оригинала) — свойства контента, из UI не правятся; при EN-интерфейсе главная показывает
перевод вместо оригинала, переключатель языка на доске ведёт на пару. Права во фронте — `useCan()`.

**Под-колонки** внутри блока задаются полем `subblock` во frontmatter, порядок и подписи — в `subblocks`
соответствующего блока в `pool.yaml`: data-engineer — frameworks → `airflow|pyspark|dbt|streaming`; databases →
`sql|dbms|storage|formats`; data-engineer-x5 — sql → `queries|indexes`; system-analyst — см. его `pool.yaml`.

## Грабли (важно)
- **Ground truth контента — через `cat`/`grep`/`GET /api/graph`, НЕ через Read-инструмент.**
  Контент-файлы нормализуются скриптами; Read может вернуть устаревший кэш.
- **Правки контента — через `python-frontmatter`** (`f.write_text(frontmatter.dumps(post) + "\n")`),
  чтобы сохранить нормализованный формат, а не ручным редактированием frontmatter.
- **Изменения `content/` не требуют пересборки фронта** (грузится из API в рантайме).
  Изменения `frontend/src/` — требуют `npm run build`.
- **Новый тип ноды на канве** = регистрация в `nodeTypes` (BoardPage.tsx).
- **Теги — только из ~17 сквозных концептов** (architecture, orchestration, optimization, …),
  1–3 на ноду, без тех-имён (технология видна по колонке). Полный список — в `AGENTS.md`.
- `main` — стабильная ветка, merge в неё **ничего не деплоит**; выкладка на ladder.paveldiordits.site — только
  ручной запуск `Deploy` (см. `DEPLOY.md`). Фичи всё равно идут через `dev`.
- **Новый пул** = каталог `content/<id>/` с `pool.yaml` (id = имя каталога); id нод уникальны в пределах
  тенанта — используйте префикс пула.
- **Удаление seed-карточки из UI** прячет её (`hidden`, `source=user`) — файл остаётся источником;
  чтобы удалить насовсем, удали файл и сделай sync.
- **Новое мутирующее действие в UI** — прячь по `useCan()` (`session.tsx`): в демо оно получит 401, у viewer — 403.
  Статус карточки пиши через `useProgressStore()`, не через `api.setProgress` напрямую — иначе демо сломается.
- **Демо-направление** = `demo: true` в `pool.yaml`; перевод — отдельный пул `<id>-en` с `lang: en` и
  `translation_of: <id>`, id карточек = id оригинала + `-en`, колонки/уровни/теги — как у оригинала.

## Проверка изменений
Скилл **interview-verify** (или вручную): import 0 ошибок (`/api/graph`) → `pytest` →
при правке фронта `npm run build` + `npm run i18n:check` (ключи `t("…")` есть в `src/i18n/en.ts`) + `npm run smoke` (нужен сервер) → рестарт uvicorn.
Smoke идёт в режиме карточки «по центру»: пока она открыта, HUD скрыт — шаги с HUD сначала закрывают её Esc.
Smoke начинается без входа (демо, EN-пара `data-engineer-en`), входит по `#/login`, в конце заводит и удаляет viewer'а —
гоняй на свежей БД: `INTERVIEW_DB_PATH=$(mktemp -d)/s.db INTERVIEW_OWNER_PASSWORD=interview-dev uvicorn app.main:app --port 8003`
и `SMOKE_URL=http://localhost:8003/ npm run smoke`.
При переименовании нод/тегов/классов, на которые опирается smoke, обнови `frontend/smoke.mjs`.

## Скиллы проекта (`.claude/skills/`)
`ladder-topic` (тема → направление со своими уровнями, главный способ завести контент), `interview-ideas` (работа с `Q_IDEAS.txt`), `interview-refactor` (ревизия вопросов),
`interview-balance` (покрытие/пробелы), `interview-verify` (полная проверка). Вызывать через Skill.
