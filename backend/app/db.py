"""Персистентность в SQLite: тенанты, направления, банк вопросов (nodes) и чек-лист разбора.

Вопросы — источник правды в БД (а не в content/*.md): UI создаёт/правит/грузит их в
рантайме, и они должны переживать деплой (который перезаписывает код, но не БД из
INTERVIEW_DB_PATH). content/*.md остаются сидом при первом старте (см. seed.py).

Все доменные таблицы несут `tenant_id` (сейчас всегда 'default') — схема tenant-ready:
переход на мультитенант не требует миграции структуры (см. tenancy.py).
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# TTL сессии аутентификации: время жизни server-side auth-session и max_age cookie (см. main.py).
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 дней, секунды

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    tenant_id    TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(id),
    pool         TEXT NOT NULL DEFAULT 'data-engineer',  -- id пула (content/<pool>/)
    id           TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'question',
    block        TEXT NOT NULL,
    subblock     TEXT,
    topic        TEXT NOT NULL,
    title        TEXT,
    difficulty   TEXT NOT NULL DEFAULT 'middle',
    weight       INTEGER NOT NULL DEFAULT 1,
    question     TEXT NOT NULL,
    answer       TEXT NOT NULL DEFAULT '',
    starter_code TEXT,
    rubric       TEXT NOT NULL DEFAULT '[]',
    tags         TEXT NOT NULL DEFAULT '[]',
    source       TEXT NOT NULL DEFAULT 'seed',
    hidden       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS pools (
    tenant_id   TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(id),
    id          TEXT NOT NULL,                 -- = content/<pool>/ у сидов; slug из названия у UI-созданных
    label       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    blocks      TEXT NOT NULL,                 -- JSON: [{id,label,color,weight,subblocks:[{id,label}]}]
    levels      TEXT NOT NULL DEFAULT '[]',        -- JSON: [{id,label}]; '[]' → DEFAULT_LEVELS при чтении
    demo        INTEGER NOT NULL DEFAULT 0,    -- 1 = видно без входа (демо-режим)
    lang        TEXT NOT NULL DEFAULT 'ru',    -- язык контента направления
    translation_of TEXT,                       -- id оригинала, если это перевод
    source      TEXT NOT NULL DEFAULT 'seed',  -- seed | user
    deleted_at  TEXT,                          -- tombstone: сид не воскрешает, id остаётся занятым
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS users (
    tenant_id     TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(id),
    id            TEXT NOT NULL,                -- генерится сервером (token_hex)
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,                -- bcrypt; пароль в открытом виде не хранится
    role          TEXT NOT NULL DEFAULT 'member', -- owner | member | viewer
    created_at    TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, email)
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    token      TEXT PRIMARY KEY,                -- значение HttpOnly-cookie (server-side session)
    tenant_id  TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
    tenant_id  TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(id),
    user_id    TEXT NOT NULL,
    node_id    TEXT NOT NULL,
    status     TEXT NOT NULL,               -- known | review | unknown (чек-лист самоподготовки)
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id, node_id)
);
"""

# rubric/tags хранятся в БД JSON-строками (паттерн SQLite без доп. таблиц).
_NODE_JSON_FIELDS = ("rubric", "tags")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_node(row: sqlite3.Row) -> Dict:
    """Строка БД → dict ноды (JSON-поля десериализуются, starterCode через alias)."""
    d = dict(row)
    for f in _NODE_JSON_FIELDS:
        d[f] = json.loads(d.get(f) or "[]")
    d["hidden"] = bool(d.get("hidden"))
    # models.Node принимает starter_code по alias starterCode; отдаём snake_case как есть.
    return d


def _row_to_pool(row: sqlite3.Row) -> Dict:
    """Строка pools → dict направления: blocks/levels из JSON в список."""
    d = dict(row)
    d["blocks"] = json.loads(d.get("blocks") or "[]")
    d["levels"] = json.loads(d.get("levels") or "[]")
    d["demo"] = bool(d.get("demo"))
    return d


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_nodes(conn)
            self._migrate_pools(conn)

    @staticmethod
    def _migrate_pools(conn: sqlite3.Connection) -> None:
        """Уровни как данные направления: столбец pools.levels. Старые строки получают прежнюю
        четвёрку явно (не '[]'), чтобы ответ API не зависел от того, когда пул создан.
        Флаги демо-режима demo/lang/translation_of — столбцы с дефолтами (не демо, ru, не перевод)."""
        from .pools import DEFAULT_LEVELS, levels_to_json

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(pools)").fetchall()}
        if "levels" not in cols:
            conn.execute("ALTER TABLE pools ADD COLUMN levels TEXT NOT NULL DEFAULT '[]'")
        for col, ddl in (
            ("demo", "ALTER TABLE pools ADD COLUMN demo INTEGER NOT NULL DEFAULT 0"),
            ("lang", "ALTER TABLE pools ADD COLUMN lang TEXT NOT NULL DEFAULT 'ru'"),
            ("translation_of", "ALTER TABLE pools ADD COLUMN translation_of TEXT"),
        ):
            if col not in cols:
                conn.execute(ddl)
        conn.execute("UPDATE pools SET levels = ? WHERE levels = '[]'", (levels_to_json(DEFAULT_LEVELS),))

    @staticmethod
    def _migrate_nodes(conn: sqlite3.Connection) -> None:
        """Пулы направлений: столбец nodes.pool. Старые строки — бывший единственный банк,
        то есть 'data-engineer'. Индекс создаём здесь, а не в _SCHEMA: на старой БД столбца
        ещё нет в момент executescript."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(nodes)").fetchall()}
        if "pool" not in cols:
            conn.execute("ALTER TABLE nodes ADD COLUMN pool TEXT NOT NULL DEFAULT 'data-engineer'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_tenant_pool ON nodes(tenant_id, pool)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # --- tenants ---
    def ensure_tenant(self, tenant_id: str, name: Optional[str] = None) -> None:
        """Создать тенанта, если его ещё нет (идемпотентно)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tenants (id, name, created_at) VALUES (?, ?, ?)",
                (tenant_id, name or tenant_id, _now()),
            )

    # --- users (auth, per-tenant) ---
    def count_users(self, tenant_id: str) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM users WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()[0]

    def list_users(self, tenant_id: str) -> List[Dict]:
        """Пользователи тенанта без password_hash (хеш наружу не отдаём)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT tenant_id, id, email, role, created_at FROM users "
                "WHERE tenant_id = ? ORDER BY created_at",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_user_by_id(self, tenant_id: str, user_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE tenant_id = ? AND id = ?",
                (tenant_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, tenant_id: str, email: str) -> Optional[Dict]:
        """Полная строка (с password_hash) — для проверки пароля при логине."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE tenant_id = ? AND email = ?",
                (tenant_id, email),
            ).fetchone()
        return dict(row) if row else None

    def create_user(
        self, tenant_id: str, email: str, password_hash: str, role: str = "member"
    ) -> Dict:
        """Создать пользователя (id — случайный token_hex). Бросает sqlite3.IntegrityError
        при дубликате email в тенанте (UNIQUE(tenant_id, email))."""
        uid = secrets.token_hex(8)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (tenant_id, id, email, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, uid, email, password_hash, role, _now()),
            )
        return self.get_user_by_id(tenant_id, uid)

    # --- auth sessions (server-side, токен = значение cookie) ---
    def create_auth_session(self, tenant_id: str, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._conn() as conn:
            # Повторный логин инвалидирует прежние сессии того же пользователя:
            # один активный токен на аккаунт (старые cookie перестают работать).
            conn.execute(
                "DELETE FROM auth_sessions WHERE tenant_id = ? AND user_id = ?",
                (tenant_id, user_id),
            )
            conn.execute(
                "INSERT INTO auth_sessions (token, tenant_id, user_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (token, tenant_id, user_id, _now()),
            )
        return token

    def get_auth_session(self, token: str) -> Optional[Dict]:
        """Вернуть сессию по токену или None. Протухшую (старше SESSION_MAX_AGE) удалить и вернуть None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM auth_sessions WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                return None
            created = datetime.fromisoformat(row["created_at"])
            if datetime.now(timezone.utc) - created > timedelta(seconds=SESSION_MAX_AGE):
                conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
                return None
        return dict(row)

    def delete_auth_session(self, token: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))

    # --- nodes (банк вопросов, per-tenant) ---
    def count_nodes(self, tenant_id: str, pool: Optional[str] = None) -> int:
        sql, args = "SELECT COUNT(*) FROM nodes WHERE tenant_id = ?", [tenant_id]
        if pool is not None:
            sql += " AND pool = ?"
            args.append(pool)
        with self._conn() as conn:
            return conn.execute(sql, args).fetchone()[0]

    def list_nodes(self, tenant_id: str, pool: Optional[str] = None, include_hidden: bool = True) -> List[Dict]:
        sql, args = "SELECT * FROM nodes WHERE tenant_id = ?", [tenant_id]
        if pool is not None:
            sql += " AND pool = ?"
            args.append(pool)
        if not include_hidden:
            sql += " AND hidden = 0"
        sql += " ORDER BY block, subblock, id"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_row_to_node(r) for r in rows]

    def list_node_ids(self, tenant_id: str, pool: str, source: Optional[str] = None, hidden: Optional[bool] = None) -> List[str]:
        sql, args = "SELECT id FROM nodes WHERE tenant_id = ? AND pool = ?", [tenant_id, pool]
        if source is not None:
            sql += " AND source = ?"
            args.append(source)
        if hidden is not None:
            sql += " AND hidden = ?"
            args.append(int(hidden))
        with self._conn() as conn:
            return [r["id"] for r in conn.execute(sql + " ORDER BY id", args).fetchall()]

    def get_node(self, tenant_id: str, node_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM nodes WHERE tenant_id = ? AND id = ?",
                (tenant_id, node_id),
            ).fetchone()
        return _row_to_node(row) if row else None

    def upsert_node(self, tenant_id: str, node: Dict, source: str = "user") -> Dict:
        """Создать/обновить ноду. `node` — dict из models.Node (rubric/tags = списки)."""
        now = _now()
        rubric = json.dumps(node.get("rubric") or [], ensure_ascii=False)
        tags = json.dumps(node.get("tags") or [], ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO nodes (
                    tenant_id, id, pool, kind, block, subblock, topic, title, difficulty,
                    weight, question, answer, starter_code, rubric, tags, source,
                    hidden, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, id) DO UPDATE SET
                    pool=excluded.pool,
                    kind=excluded.kind, block=excluded.block, subblock=excluded.subblock,
                    topic=excluded.topic, title=excluded.title, difficulty=excluded.difficulty,
                    weight=excluded.weight, question=excluded.question, answer=excluded.answer,
                    starter_code=excluded.starter_code, rubric=excluded.rubric,
                    tags=excluded.tags, source=excluded.source, updated_at=excluded.updated_at
                    -- hidden НЕ обновляем: на нём держится «липкость» скрытия (sync/tombstone),
                    -- обычный upsert (UI-правка, /api/import) не должен её случайно снимать
                """,
                (
                    tenant_id, node["id"], node.get("pool", "data-engineer"),
                    node.get("kind", "question"), node["block"],
                    node.get("subblock"), node["topic"], node.get("title"),
                    node.get("difficulty", "middle"), int(node.get("weight", 1)),
                    node["question"], node.get("answer", ""), node.get("starter_code"),
                    rubric, tags, source, int(bool(node.get("hidden", False))), now, now,
                ),
            )
        return self.get_node(tenant_id, node["id"])

    def delete_node(self, tenant_id: str, node_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM nodes WHERE tenant_id = ? AND id = ?", (tenant_id, node_id)
            )
        return cur.rowcount > 0

    def tombstone_node(self, tenant_id: str, node_id: str) -> bool:
        """Спрятать ноду вместо удаления (source='user'): для seed-ноды, файл которой в content/
        остаётся источником — обычный DELETE её бы воскресил при следующем sync."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE nodes SET hidden = 1, source = 'user', updated_at = ? WHERE tenant_id = ? AND id = ?",
                (_now(), tenant_id, node_id),
            )
        return cur.rowcount > 0

    def set_node_hidden(self, tenant_id: str, node_id: str, hidden: bool) -> Optional[Dict]:
        with self._conn() as conn:
            conn.execute(
                "UPDATE nodes SET hidden = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                (int(hidden), _now(), tenant_id, node_id),
            )
        return self.get_node(tenant_id, node_id)

    def seed_nodes(self, tenant_id: str, nodes: List[Dict]) -> int:
        """Залить ноды как сид (source='seed'), не перетирая существующие.

        INSERT OR IGNORE по (tenant_id, id): повторный вызов идемпотентен и не трогает
        пользовательские правки. Возвращает число фактически вставленных нод.
        """
        now = _now()
        inserted = 0
        with self._conn() as conn:
            for node in nodes:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO nodes (
                        tenant_id, id, pool, kind, block, subblock, topic, title, difficulty,
                        weight, question, answer, starter_code, rubric, tags, source,
                        hidden, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', 0, ?, ?)
                    """,
                    (
                        tenant_id, node["id"], node.get("pool", "data-engineer"),
                        node.get("kind", "question"), node["block"],
                        node.get("subblock"), node["topic"], node.get("title"),
                        node.get("difficulty", "middle"), int(node.get("weight", 1)),
                        node["question"], node.get("answer", ""), node.get("starter_code"),
                        json.dumps(node.get("rubric") or [], ensure_ascii=False),
                        json.dumps(node.get("tags") or [], ensure_ascii=False),
                        now, now,
                    ),
                )
                inserted += cur.rowcount
        return inserted

    # --- pools (направления: сид из content/<pool>/pool.yaml, CRUD из UI; per-tenant) ---
    def list_pools(self, tenant_id: str) -> List[Dict]:
        """Живые направления в порядке создания (сиды идут в порядке каталогов content/)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pools WHERE tenant_id = ? AND deleted_at IS NULL ORDER BY rowid",
                (tenant_id,),
            ).fetchall()
        return [_row_to_pool(r) for r in rows]

    def get_pool(self, tenant_id: str, pool_id: str) -> Optional[Dict]:
        """Направление по id, включая tombstone (deleted_at не None) — для проверки занятости id."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pools WHERE tenant_id = ? AND id = ?", (tenant_id, pool_id)
            ).fetchone()
        return _row_to_pool(row) if row else None

    def upsert_pool_seed(self, tenant_id: str, pool: Dict) -> bool:
        """Сид конфига направления: INSERT OR IGNORE — правки из UI и tombstone переживают рестарт.

        `pool` — {id, label, description, blocks: list, levels?: list, demo?, lang?, translation_of?}.
        Возвращает True, если строка вставлена.
        """
        now = _now()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO pools (
                    tenant_id, id, label, description, blocks, levels, demo, lang, translation_of,
                    source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', ?, ?)
                """,
                (
                    tenant_id, pool["id"], pool["label"], pool.get("description") or "",
                    json.dumps(pool["blocks"], ensure_ascii=False),
                    json.dumps(pool.get("levels") or [], ensure_ascii=False),
                    int(bool(pool.get("demo"))), pool.get("lang") or "ru", pool.get("translation_of"),
                    now, now,
                ),
            )
        return cur.rowcount == 1

    def create_pool(
        self,
        tenant_id: str,
        pool_id: str,
        label: str,
        description: str,
        blocks: List[Dict],
        copy_from: Optional[str] = None,
        levels: Optional[List[Dict]] = None,
    ) -> Dict:
        """Направление из UI (source='user'); с copy_from — ещё и копия его вопросов.

        Строка пула и копии нод пишутся одной транзакцией: падение посередине (в том числе
        коллизия id ноды) откатывает всё, «пула-сироты» без вопросов не остаётся.
        Занятость id пула проверяет вызывающий (get_pool). Уровни: без copy_from — переданные
        (или '[]' → DEFAULT_LEVELS при чтении); с copy_from и levels=None — уровни пресета.
        """
        now = _now()
        if copy_from is not None and levels is None:
            levels = self.get_pool(tenant_id, copy_from)["levels"]
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pools (
                    tenant_id, id, label, description, blocks, levels, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'user', ?, ?)
                """,
                (
                    tenant_id, pool_id, label, description, json.dumps(blocks, ensure_ascii=False),
                    json.dumps(levels or [], ensure_ascii=False), now, now,
                ),
            )
            if copy_from is not None:
                self._copy_nodes(conn, tenant_id, copy_from, pool_id, now)
        return self.get_pool(tenant_id, pool_id)

    def set_pool_config(self, tenant_id: str, pool_id: str, cfg: Dict) -> None:
        """Конфиг направления из файлов (sync): label/description/blocks/levels и флаги demo/lang/translation_of
        без побочных удалений вопросов — в отличие от update_pool, где смена колонок/уровней из UI режет вопросы.
        Флаги — свойство контента: пишет их только sync, из UI они не правятся."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE pools SET label = ?, description = ?, blocks = ?, levels = ?, demo = ?, lang = ?, "
                "translation_of = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                (cfg["label"], cfg.get("description") or "", json.dumps(cfg["blocks"], ensure_ascii=False),
                 json.dumps(cfg["levels"], ensure_ascii=False), int(bool(cfg.get("demo"))),
                 cfg.get("lang") or "ru", cfg.get("translation_of"), _now(), tenant_id, pool_id),
            )

    def update_pool(self, tenant_id: str, pool_id: str, fields: Dict) -> Optional[Dict]:
        """Правка названия/описания/колонок/уровней (остальные ключи игнорируются). None — нет или удалено.

        `blocks`/`levels` — уже валидированные списки dict (см. pools.normalize_blocks + parse_blocks,
        pools.normalize_levels + parse_levels). Смена колонок и её последствия для вопросов — одна
        транзакция: вопросы исчезнувших колонок удаляются, вопросы исчезнувших под-колонок остаются
        в колонке без под-колонки; вопросы исчезнувших уровней удаляются.
        """
        current = self.get_pool(tenant_id, pool_id)
        if current is None or current["deleted_at"] is not None:
            return None
        allowed = {k: v for k, v in fields.items() if k in ("label", "description")}
        blocks = fields.get("blocks")
        levels = fields.get("levels")
        if not allowed and blocks is None and levels is None:
            return current
        now = _now()
        with self._conn() as conn:
            if allowed:
                sets = ", ".join(f"{k} = ?" for k in allowed)
                conn.execute(
                    f"UPDATE pools SET {sets}, updated_at = ? WHERE tenant_id = ? AND id = ?",
                    (*allowed.values(), now, tenant_id, pool_id),
                )
            if blocks is not None:
                conn.execute(
                    "UPDATE pools SET blocks = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                    (json.dumps(blocks, ensure_ascii=False), now, tenant_id, pool_id),
                )
                kept = [b["id"] for b in blocks]
                if not kept:  # `NOT IN ()` удалил бы все вопросы; непустоту гарантирует parse_blocks у вызывающего
                    raise ValueError("blocks must not be empty")
                marks = ",".join("?" * len(kept))
                conn.execute(
                    f"DELETE FROM nodes WHERE tenant_id = ? AND pool = ? AND block NOT IN ({marks})",
                    (tenant_id, pool_id, *kept),
                )
                for b in blocks:
                    subs = [s["id"] for s in b.get("subblocks") or []]
                    sub_marks = ",".join("?" * len(subs))
                    cond = f"AND subblock NOT IN ({sub_marks})" if subs else ""
                    conn.execute(
                        f"UPDATE nodes SET subblock = NULL, updated_at = ? WHERE tenant_id = ? AND pool = ? "
                        f"AND block = ? AND subblock IS NOT NULL {cond}",
                        (now, tenant_id, pool_id, b["id"], *subs),
                    )
            if levels is not None:
                kept_l = [l["id"] for l in levels]
                if not kept_l:
                    raise ValueError("levels must not be empty")
                conn.execute(
                    "UPDATE pools SET levels = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                    (json.dumps(levels, ensure_ascii=False), now, tenant_id, pool_id),
                )
                marks = ",".join("?" * len(kept_l))
                conn.execute(
                    f"DELETE FROM nodes WHERE tenant_id = ? AND pool = ? AND difficulty NOT IN ({marks})",
                    (tenant_id, pool_id, *kept_l),
                )
        return self.get_pool(tenant_id, pool_id)

    def delete_pool(self, tenant_id: str, pool_id: str) -> Optional[int]:
        """Удалить направление: вопросы стираются, строка остаётся tombstone'ом (id занят, сид
        не воскрешает). Возвращает число удалённых нод; None — нет или уже удалено."""
        current = self.get_pool(tenant_id, pool_id)
        if current is None or current["deleted_at"] is not None:
            return None
        now = _now()
        with self._conn() as conn:
            removed = conn.execute(
                "DELETE FROM nodes WHERE tenant_id = ? AND pool = ?", (tenant_id, pool_id)
            ).rowcount
            conn.execute(
                "UPDATE pools SET deleted_at = ?, updated_at = ? WHERE tenant_id = ? AND id = ?",
                (now, now, tenant_id, pool_id),
            )
        return removed

    def copy_nodes(self, tenant_id: str, src_pool: str, dst_pool: str) -> int:
        """Скопировать все ноды src в dst (пресет → новое направление) одной транзакцией.

        Возвращает число скопированных. Коллизия id (`<dst>-<id>` уже занят чужой нодой) —
        sqlite3.IntegrityError, ничего не копируется.
        """
        with self._conn() as conn:
            return self._copy_nodes(conn, tenant_id, src_pool, dst_pool, _now())

    @staticmethod
    def _copy_nodes(
        conn: sqlite3.Connection, tenant_id: str, src_pool: str, dst_pool: str, now: str
    ) -> int:
        """Копии нод внутри открытой транзакции: id с префиксом dst, source='user', hidden=0.

        Обычный INSERT (не upsert): чужая нода с таким же id не перетирается молча — ошибка
        целостности откатывает транзакцию целиком.
        """
        rows = conn.execute(
            "SELECT * FROM nodes WHERE tenant_id = ? AND pool = ? ORDER BY rowid", (tenant_id, src_pool)
        ).fetchall()
        for r in rows:
            conn.execute(
                """
                INSERT INTO nodes (
                    tenant_id, id, pool, kind, block, subblock, topic, title, difficulty,
                    weight, question, answer, starter_code, rubric, tags, source,
                    hidden, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 0, ?, ?)
                """,
                (
                    tenant_id, f"{dst_pool}-{r['id']}", dst_pool, r["kind"], r["block"], r["subblock"],
                    r["topic"], r["title"], r["difficulty"], r["weight"], r["question"], r["answer"],
                    r["starter_code"], r["rubric"], r["tags"], now, now,
                ),
            )
        return len(rows)

    # --- progress (чек-лист разбора, per-user) ---
    PROGRESS_STATUSES = ("known", "review", "unknown")

    def set_progress(self, tenant_id: str, user_id: str, node_id: str, status: str) -> Dict[str, str]:
        """Статус карточки для пользователя (upsert). Валидность status проверяет вызывающий."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO progress (tenant_id, user_id, node_id, status, updated_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id, node_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
                """,
                (tenant_id, user_id, node_id, status, _now()),
            )
        return {"node_id": node_id, "status": status}

    def clear_progress(self, tenant_id: str, user_id: str, node_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM progress WHERE tenant_id = ? AND user_id = ? AND node_id = ?", (tenant_id, user_id, node_id)
            )
        return cur.rowcount > 0

    def get_progress(self, tenant_id: str, user_id: str, pool: str) -> Dict[str, str]:
        """{node_id: status} по видимым нодам пула — статусы спрятанных нод не отдаём, но и не стираем."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT p.node_id, p.status FROM progress p
                JOIN nodes n ON n.tenant_id = p.tenant_id AND n.id = p.node_id
                WHERE p.tenant_id = ? AND p.user_id = ? AND n.pool = ? AND n.hidden = 0
                """,
                (tenant_id, user_id, pool),
            ).fetchall()
        return {r["node_id"]: r["status"] for r in rows}

    def progress_summary(self, tenant_id: str, user_id: str, pool: str) -> Dict[str, int]:
        """Сводка для главной: сколько known/review/unknown среди видимых нод пула и total = видимых нод."""
        counts = Counter(self.get_progress(tenant_id, user_id, pool).values())
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE tenant_id = ? AND pool = ? AND hidden = 0", (tenant_id, pool)
            ).fetchone()[0]
        return {"known": counts["known"], "review": counts["review"], "unknown": counts["unknown"], "total": total}
