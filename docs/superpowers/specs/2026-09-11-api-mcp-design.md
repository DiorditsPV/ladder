# API и MCP для правки направлений и вопросов — дизайн

Дата: 2026-09-11. Цель владельца: «сделай api + mcp для создания карточек направлений и редактирования вопросов —
CRUD по вопросам и горизонтально-вертикальным темам и топикам; MCP должно покрывать всё необходимое для
редактирования направлений и вопросов, API — предоставлять всё нужное для MCP».

## Модель (как её видит MCP)
Направление (`pool`) → колонки (`blocks`, вертикаль; у колонки могут быть под-колонки `subblocks`) × уровни
(`levels`, горизонталь, ряды сверху вниз от простого к сложному) → карточки-вопросы (`nodes`). У карточки есть
`topic` (короткий slug подтемы внутри колонки), `tags` (1–3 сквозных концепта), `kind` (question|task).

## API (добавляется к существующему)
- `GET /api/pools/{id}` — одно направление (структура + счётчики + сводка чек-листа).
- `POST /api/pools` — необязательный `id` (slug; занятый, в т.ч. удалённым направлением, — 409).
- `GET /api/nodes?pool=&block=&subblock=&difficulty=&topic=&tag=&kind=&q=&include_hidden=` — список с фильтрами.
- `GET /api/nodes/{id}` — одна карточка (все поля + `hidden`, `source`).
- `POST /api/nodes` — ещё `id` (явный, 409 при занятом), `subblock`, `weight`, `starterCode`, `rubric`; ответ — вся карточка.
- `PUT /api/nodes/{id}` — любые поля карточки, включая перенос: `pool`, `block`, `subblock`, `difficulty`, а также
  `topic`, `tags`, `kind`, `weight`, `starterCode`, `rubric`; `""` в `subblock`/`title`/`starterCode` снимает значение.
  Ответ — `{"updated": id, "node": {...}}`.
- Теги (create/update): slug `[a-z0-9-]`, не больше 5, дубли схлопываются; иначе 422.
- Топики: `GET /api/pools/{id}/topics[?block=]` — `[{topic, block, count}]`; `PUT /api/pools/{id}/topics/{topic}`
  `{topic, block?}` — переименование у всех карточек; `DELETE /api/pools/{id}/topics/{topic}[?block=]` — удаление
  карточек топика (seed прячется, как в `DELETE /api/nodes`).
- `GET /api/tags[?pool=]` — словарь сквозных концептов + теги, уже использованные в направлении.
- Структура (колонки, под-колонки, уровни) — существующий `PUT /api/pools/{id}` со списками `blocks`/`levels`:
  MCP делает read-modify-write (переименование, порядок, добавление, удаление).
- Права: чтение — любой вошедший; запись — member/owner (как у существующих ручек); без входа — 401.

## MCP-сервер (`tools/ladder-mcp`, пакет `ladder_mcp`, Python, `mcp` 2.x, stdio)
Ходит в API по `LADDER_URL` с логином `LADDER_EMAIL`/`LADDER_PASSWORD` (cookie-сессия, повторный вход на 401).
Инструменты:
- направления: `list_directions`, `get_direction` (структура + матрица покрытия колонка × уровень),
  `create_direction`, `update_direction`, `delete_direction` (confirm);
- вертикаль: `add_column`, `update_column` (название, цвет, позиция), `delete_column` (confirm или перенос вопросов),
  `add_subcolumn`, `update_subcolumn`, `delete_subcolumn`;
- горизонталь: `add_level`, `update_level` (название, позиция), `delete_level` (confirm или перенос вопросов);
- топики: `list_topics`, `rename_topic`, `delete_topic` (confirm);
- вопросы: `list_questions`, `get_question`, `create_question`, `create_questions` (пачкой), `update_question`
  (включая перенос), `delete_question`;
- `list_tags`.
Удаление, которое тянет за собой вопросы, без `confirm=true` не выполняется — инструмент возвращает, сколько
вопросов пострадает.

## Проверка
pytest на новые ручки (включая права), pytest MCP через in-process клиент против FastAPI-приложения
(ASGITransport), e2e: MCP по stdio против живого uvicorn; CI гоняет оба набора.
