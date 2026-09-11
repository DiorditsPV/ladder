# ladder-mcp — MCP-сервер Ladder

MCP-сервер для правки направлений и вопросов через API Ladder: направления, их вертикальная структура (колонки и
под-колонки), горизонтальная (уровни), топики и карточки-вопросы. Работает с любым экземпляром — локальным
контейнером или боевым сайтом — по HTTP, от имени аккаунта с правом правки (owner или member).

## Установка

```bash
python3 -m venv tools/ladder-mcp/.venv
tools/ladder-mcp/.venv/bin/pip install -e tools/ladder-mcp
```

Нужен Python 3.10+. Зависимости — `mcp` 2.x и `httpx`.

## Подключение

Переменные окружения:

| Переменная        | Что это                        | По умолчанию            |
|-------------------|--------------------------------|-------------------------|
| `LADDER_URL`      | адрес сервиса                  | `http://localhost:8000` |
| `LADDER_EMAIL`    | логин аккаунта с правом правки | —                       |
| `LADDER_PASSWORD` | пароль этого аккаунта          | —                       |

Для боевого сайта заведите отдельный аккаунт на странице «Люди» и дайте ему роль member (правка контента без
управления людьми); пароль владельца в конфиг MCP класть не нужно.

Claude Code:

```bash
claude mcp add ladder \
  -e LADDER_URL=https://ladder.paveldiordits.site -e LADDER_EMAIL=<почта> -e LADDER_PASSWORD=<пароль> \
  -- /абсолютный/путь/tools/ladder-mcp/.venv/bin/ladder-mcp
```

Claude Desktop и другие клиенты — тот же запуск в `mcpServers`:

```json
{
  "mcpServers": {
    "ladder": {
      "command": "/абсолютный/путь/tools/ladder-mcp/.venv/bin/ladder-mcp",
      "env": {"LADDER_URL": "http://localhost:8000", "LADDER_EMAIL": "admin", "LADDER_PASSWORD": "admin"}
    }
  }
}
```

Проверка настройки без клиента — короткий цикл по stdio (создаёт и удаляет временное направление):

```bash
LADDER_URL=http://localhost:8000 LADDER_EMAIL=admin LADDER_PASSWORD=admin \
  tools/ladder-mcp/.venv/bin/python tools/ladder-mcp/scripts/stdio_smoke.py
```

## Инструменты

Словарь: направление — `pool`, колонка — `block`, под-колонка — `subblock`, уровень — ряд доски (`difficulty`
карточки), вопрос — карточка (`node`). Позиции — с нуля, уровни идут сверху вниз от простого к сложному.

| Группа      | Инструменты                                                                                                                                                                                                         |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Направления | `list_directions`, `get_direction` (структура + матрица покрытия), `create_direction` (свои колонки и уровни или копия другого), `update_direction`, `delete_direction`                                             |
| Вертикаль   | `add_column`, `update_column` (название, цвет, позиция), `delete_column`, `add_subcolumn`, `update_subcolumn`, `delete_subcolumn`                                                                                   |
| Горизонталь | `add_level`, `update_level` (название, позиция), `delete_level`                                                                                                                                                     |
| Топики      | `list_topics`, `rename_topic`, `delete_topic`                                                                                                                                                                       |
| Вопросы     | `list_questions` (фильтры по колонке, под-колонке, уровню, топику, тегу, виду, тексту), `get_question`, `create_question`, `create_questions` (пачкой), `update_question` (любые поля и перенос), `delete_question` |
| Теги        | `list_tags` — словарь сквозных концептов и уже использованные в направлении                                                                                                                                         |
| Пресеты     | `sync_from_files` — засев или явное обновление пресета из `content/` (`update_existing`); по умолчанию `dry_run` — отчёт на копии базы, без записи                                                                  |

Удаление колонки, уровня, топика или направления с вопросами выполняется только с `confirm=true`; колонку и
уровень можно удалить без потери вопросов — `move_questions_to` сначала переносит их. Карточка из файлов
`content/` при удалении прячется, а не стирается. Всё, что правится через MCP, помечается как правка
пользователя, и синхронизация из файлов его не перетирает; обычный засев вообще не трогает существующее.

## Тесты

```bash
backend/.venv/bin/pip install -r tools/ladder-mcp/requirements.txt
backend/.venv/bin/python -m pytest -q tools/ladder-mcp/tests -p no:cacheprovider
```

Тесты поднимают настоящий бэкенд в процессе (`httpx.ASGITransport`) на свежей БД и ходят в него через MCP-клиент.
