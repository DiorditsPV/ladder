# Подпроект B: скилл `interview-topic` + пересборка `system-analyst` — план

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (content-задачи) / inline для скрипта и SKILL.md.

**Goal:** `/interview-topic <тема>` раскладывает тему на колонки × свои уровни и пишет карточки в `content/<slug>/`, сервис подхватывает через sync; `system-analyst` пересобран скиллом с собственными уровнями.

**Architecture:** детерминика — `write_topic.py` (JSON темы → файлы в нормализованном формате, валидация тегов/уровней/id, матрица покрытия, `--fresh`/дополнение, `--sync` + проверка `/api/graph`); суждение — `SKILL.md` (каркас темы, качество карточек, покрытие). Скилл пишется по TDD writing-skills: RED без скилла → GREEN с ним на SA.

**Spec:** `docs/superpowers/specs/2026-09-10-topic-study-pivot-design.md`, подпроект B.

## Global Constraints
- `data-engineer*` не трогать (`git diff --stat dev -- content/data-engineer*` пуст). `system-analyst` пересобирается `--fresh`.
- Теги — только 17 концептов, 1–3 на карточку; `difficulty` ∈ `levels` пула; id с префиксом `<pool>-`; frontmatter нормализован (`frontmatter.dumps(sort_keys=True)`), тело `## Вопрос`/`## Ответ`, строки тела не начинаются с `#`.
- Покрытие: каждая ячейка колонка × уровень ≥ `--per-cell` (по умолчанию 2).
- Тесты: `test_app.py::test_every_pool_imports_without_errors` (≥10 нод, title, 1–3 тега), `test_pool_crud` (preset SA), smoke SA не касается.
- Goal-режим владельца: гейт «подтверди каркас» в скилле остаётся для интерактивного запуска; здесь каркас SA утверждает контроллер рулингом.

### Task 1 (inline): `write_topic.py` + тест
Скрипт написан; тест `backend/tests/test_write_topic.py` — subprocess на tmp content: валидная тема → файлы, pool.yaml с levels/weights, матрица; невалидные (чужой тег, чужой уровень, без префикса) → exit 1; дополнение без `--fresh` не перетирает; `--fresh` сносит.

### Task 2 (inline, writing-skills): RED → `SKILL.md` → GREEN
RED: haiku без скилла делает «направление Kafka» в scratch — записать провалы. GREEN = Task 3.

### Task 3 (субагент + ревью): пересборка SA
Каркас (Ruling): колонки requirements(elicitation/analysis/documentation), modeling(process/uml), data(sql/data-model), integration(api/async); уровни `concepts` «Понятия» → `practice` «Практика» → `design` «Проектирование» → `expert` «Экспертиза»; per-cell 2 → ≥32 карточек. Контент-субагент (opus) выдаёт JSON по контракту скрипта → `--fresh --sync` → 0 ошибок → ревью карточек (sonnet: дубли, качество ответа, теги, уровень) → фикс → `pytest` → commit.

### Task 4: docs (AGENTS.md таблица скиллов, CLAUDE.md), PR в dev.
