"""Словарь сквозных тегов карточек (см. AGENTS.md): 1–3 концепта на карточку, без названий технологий.

Тот же список держит скилл ladder-topic (`.claude/skills/ladder-topic/write_topic.py`, `TAGS`); API отдаёт его
в `GET /api/tags`, чтобы клиенты (UI, MCP) не хардкодили словарь. Тема вне дата-инженерии может завести свои
теги (`pool.tags` в pool.yaml) — поэтому API проверяет только форму тега (slug), а не принадлежность словарю.
"""

CONCEPT_TAGS = (
    "architecture",
    "orchestration",
    "optimization",
    "partitioning",
    "deployment",
    "storage",
    "streaming",
    "consistency",
    "data-modeling",
    "quality",
    "distributed",
    "sql",
    "monitoring",
    "memory",
    "file-formats",
    "domain",
    "concurrency",
)
