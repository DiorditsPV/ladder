"""Синхронизация content/ → БД: направления и seed-ноды из файлов.

Источник правды — БД: вопросы заносятся через UI, API и MCP, а content/ хранит только пресеты
(data-engineer, system-analyst и их EN-переводы) для свежих установок и демо (spec 2026-09-11-content-in-db).

Два режима:
- **засев** (по умолчанию: старт сервера, POST /api/pools/sync) — файлы создают направление, если его нет, и
  карточки, id которых нет в БД; существующее не перезаписывается и не прячется. Так деплой не может затереть
  накопленное: ни правки колонок и уровней, ни карточки, чьих файлов в репозитории нет.
- **обновление** (`update=True`, явное действие владельца, лучше с `only=<pool>` и сначала `dry_run=True`) —
  конфиг направления переписывается из pool.yaml, seed-ноды upsert-ятся по id, пользовательские
  (source='user') — не трогаются (конфликт id — в отчёт), исчезнувшие из файлов seed-ноды прячутся
  (на них могут ссылаться статусы чек-листа) — но только если пул распарсился без ошибок: битые файлы
  неотличимы от удалённых вопросов, поэтому при непустом errors скрытие для пула пропускается целиком.
  Флаг hidden у seed-нод пишет только sync — такая нода, спрятанная ранее и снова появившаяся в файлах,
  разворачивается при upsert. Удаление seed-карточки из UI (DELETE /api/nodes/{id}) — tombstone
  (hidden=1, source='user'): sync её не трогает как любую user-ноду и не считает конфликтом id.
  Конфиг направления обновляется без каскадных удалений (см. db.set_pool_config).

`dry_run` — тот же прогон на временной копии БД: отчёт точный, живая БД не меняется.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .db import Database
from .importer import load_pool_content
from .pools import PoolCfg, blocks_to_json, levels_to_json, load_pools


class UnknownPoolError(KeyError):
    """Направления с таким id нет в content/ (для `only=`)."""


def _cfg(pool: PoolCfg) -> Dict:
    return {
        "id": pool.id,
        "label": pool.label,
        "description": pool.description,
        "blocks": json.loads(blocks_to_json(pool.blocks)),
        "levels": json.loads(levels_to_json(pool.levels)),
        # Флаги демо-режима — свойство контента: update переносит их из pool.yaml (и сбрасывает, если убраны).
        "demo": pool.demo,
        "lang": pool.lang,
        "translation_of": pool.translation_of,
    }


def _config_differs(existing: Dict, cfg: Dict) -> bool:
    """Отличается ли конфиг направления в БД от pool.yaml (для отчёта: что перепишет update)."""
    keys = ("label", "description", "blocks", "levels", "lang", "translation_of")
    if any((existing.get(k) or None) != (cfg.get(k) or None) for k in keys):
        return True
    return bool(existing.get("demo")) != bool(cfg.get("demo"))


def seed_pool(db: Database, tenant_id: str, pool: PoolCfg, report: Dict) -> None:
    """Засев одного направления: создать, если нет; добавить карточки, id которых нет в БД (id уникальны в
    тенанте, поэтому занятый в другом направлении тоже пропускается). Ничего не перезаписывает и не прячет."""
    existing = db.get_pool(tenant_id, pool.id)
    if existing is not None and existing["deleted_at"] is not None:
        return  # удалённое направление файлы не воскрешают
    if existing is None:
        db.upsert_pool_seed(tenant_id, _cfg(pool))
        report["created"].append(pool.id)
    nodes, errors = load_pool_content(pool)
    report["errors"].extend({"file": e.file, "error": e.error} for e in errors)
    taken = {n["id"] for n in db.list_nodes(tenant_id)}
    added = 0
    for node in nodes:
        if node.id in taken:
            report["skipped"] += 1
            continue
        db.upsert_node(tenant_id, node.model_dump(), source="seed")
        taken.add(node.id)
        added += 1
    report["nodes_upserted"] += added
    if existing is not None and added:
        report["updated"].append(pool.id)


def update_pool(db: Database, tenant_id: str, pool: PoolCfg, report: Dict) -> None:
    """Явное обновление направления из файлов: конфиг, seed-ноды, скрытие исчезнувших. Tombstone — пропуск."""
    existing = db.get_pool(tenant_id, pool.id)
    if existing is not None and existing["deleted_at"] is not None:
        return
    cfg = _cfg(pool)
    if existing is None:
        db.upsert_pool_seed(tenant_id, cfg)
        report["created"].append(pool.id)
    else:
        if _config_differs(existing, cfg):
            report["config_changed"].append(pool.id)
        db.set_pool_config(tenant_id, pool.id, cfg)
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


# Прежнее имя (обновление одного направления) — для внешних вызовов и тестов.
sync_pool = update_pool


def sync_pools(
    db: Database,
    tenant_id: str,
    content_dir: Path,
    *,
    update: bool = False,
    only: Optional[str] = None,
    dry_run: bool = False,
) -> Dict:
    """Каталоги с pool.yaml в content_dir (или только `only`). По умолчанию — засев, update=True — обновление.
    Возвращает сводку для лога/ответа API; dry_run — прогон на временной копии БД."""
    pools = load_pools(content_dir)
    if only is not None:
        if only not in pools:
            raise UnknownPoolError(only)
        pools = {only: pools[only]}
    report: Dict = {
        "mode": "update" if update else "seed",
        "dry_run": dry_run,
        "created": [],
        "updated": [],
        "config_changed": [],
        "nodes_upserted": 0,
        "skipped": 0,
        "hidden": [],
        "conflicts": [],
        "errors": [],
    }
    step = update_pool if update else seed_pool
    if not dry_run:
        db.ensure_tenant(tenant_id)
        for pool in pools.values():
            step(db, tenant_id, pool, report)
        return report
    with tempfile.TemporaryDirectory(prefix="ladder-sync-dry-") as tmp:
        copy_path = Path(tmp) / "dry.db"
        src = sqlite3.connect(db.path)
        dst = sqlite3.connect(copy_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        scratch = Database(copy_path)
        scratch.ensure_tenant(tenant_id)
        for pool in pools.values():
            step(scratch, tenant_id, pool, report)
    return report
