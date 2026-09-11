"""Синхронизация content/ → БД: направления и seed-ноды из файлов.

Источник правды для вопросов — БД (UI их правит), но файлы content/ — способ массово завозить
и перегенерировать темы (скилл ladder-topic). Поэтому: seed-ноды upsert-ятся из файлов по id,
пользовательские (source='user') — не трогаются (конфликт id — в отчёт), исчезнувшие из файлов
seed-ноды прячутся (на них могут ссылаться статусы чек-листа) — но только если пул распарсился без ошибок:
битые файлы неотличимы от удалённых вопросов, поэтому при непустом errors скрытие для пула
пропускается целиком (упавшие файлы не должны прятать весь банк). Флаг hidden у seed-нод пишет
только sync — поэтому такая нода, спрятанная ранее и снова появившаяся в файлах, автоматически
разворачивается при upsert (учитывается в nodes_upserted, отдельного ключа отчёта для этого нет).
Удаление seed-карточки из UI (DELETE /api/nodes/{id}) — это tombstone (hidden=1, source='user'),
а не DELETE (см. main.remove_node): файл остаётся источником, поэтому sync её не трогает как
любую user-ноду, но такая скрытая tombstone-нода не считается конфликтом id — иначе она сыпала
бы шумом в отчёт при каждом sync (см. user_ids_all/user_visible ниже).
Конфиг направления обновляется без каскадных удалений (см. db.set_pool_config).
Вызывается при старте сервера и по POST /api/pools/sync.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .db import Database
from .importer import load_pool_content
from .pools import PoolCfg, blocks_to_json, levels_to_json, load_pools


def _cfg(pool: PoolCfg) -> Dict:
    return {
        "id": pool.id,
        "label": pool.label,
        "description": pool.description,
        "blocks": json.loads(blocks_to_json(pool.blocks)),
        "levels": json.loads(levels_to_json(pool.levels)),
        # Флаги демо-режима — свойство контента: sync переносит их из pool.yaml (и сбрасывает, если убраны).
        "demo": pool.demo,
        "lang": pool.lang,
        "translation_of": pool.translation_of,
    }


def sync_pool(db: Database, tenant_id: str, pool: PoolCfg, report: Dict) -> None:
    """Одно направление: конфиг, ноды, скрытие исчезнувших. Tombstone — пропуск целиком."""
    existing = db.get_pool(tenant_id, pool.id)
    if existing is not None and existing["deleted_at"] is not None:
        return
    if existing is None:
        db.upsert_pool_seed(tenant_id, _cfg(pool))
        report["created"].append(pool.id)
    else:
        db.set_pool_config(tenant_id, pool.id, _cfg(pool))
        report["updated"].append(pool.id)

    nodes, errors = load_pool_content(pool)
    report["errors"].extend({"file": e.file, "error": e.error} for e in errors)
    # Два множества user-нод: user_ids_all — вся защита от upsert (включая tombstone —
    # скрытую, но всё ещё source='user'); user_visible — только видимые, по ним репортим
    # конфликт id (иначе tombstone сыпал бы шумом в conflicts на каждый sync).
    user_ids_all = set(db.list_node_ids(tenant_id, pool.id, source="user"))
    user_visible = set(db.list_node_ids(tenant_id, pool.id, source="user", hidden=False))
    hidden_ids = set(db.list_node_ids(tenant_id, pool.id, source="seed", hidden=True))
    file_ids: List[str] = []
    for node in nodes:
        if node.id in user_ids_all:
            if node.id in user_visible:
                report["conflicts"].append(node.id)
            continue
        db.upsert_node(tenant_id, node.model_dump(), source="seed")
        if node.id in hidden_ids:
            # вернулась в файлы — флаг hidden пишет только sync, снимаем его здесь же
            db.set_node_hidden(tenant_id, node.id, False)
        report["nodes_upserted"] += 1
        file_ids.append(node.id)
    if errors:
        # хотя бы один файл пула не распарсился — не прячем весь банк из-за неполного file_ids
        return
    # seed-ноды, которых больше нет в файлах, — спрятать (один раз: уже скрытые не считаем)
    for nid in db.list_node_ids(tenant_id, pool.id, source="seed", hidden=False):
        if nid not in file_ids and nid not in user_ids_all:
            db.set_node_hidden(tenant_id, nid, True)
            report["hidden"].append(nid)


def sync_pools(db: Database, tenant_id: str, content_dir: Path) -> Dict:
    """Все каталоги с pool.yaml в content_dir. Возвращает сводку для лога/ответа API."""
    report: Dict = {"created": [], "updated": [], "nodes_upserted": 0, "hidden": [], "conflicts": [], "errors": []}
    db.ensure_tenant(tenant_id)
    for pool in load_pools(content_dir).values():
        sync_pool(db, tenant_id, pool, report)
    return report
