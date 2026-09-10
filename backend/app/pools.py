"""Конфигурация пулов направлений: content/<pool>/pool.yaml.

Пул — самостоятельный банк вопросов со своей таксономией блоков (см. спек
docs/superpowers/specs/2026-09-02-pools-and-main-menu-design.md). Отсюда берут
порядок и подписи колонок фронт, веса — sampler, допустимые block/subblock — импортёр.

Невалидный pool.yaml не роняет сервис: каталог пропускается с предупреждением в лог,
как сегодня битый контент попадает в errors, а не в 500.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

log = logging.getLogger("interview")

_ID_RE = re.compile(r"^[a-z0-9-]+$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class PoolConfigError(ValueError):
    """pool.yaml есть, но не проходит валидацию."""


@dataclass(frozen=True)
class SubblockCfg:
    id: str
    label: str


@dataclass(frozen=True)
class BlockCfg:
    id: str
    label: str
    color: str
    weight: int
    subblocks: Tuple[SubblockCfg, ...]


@dataclass(frozen=True)
class LevelCfg:
    id: str
    label: str


# Уровни пула без `levels:` в pool.yaml — прежняя четвёрка, чтобы существующие пулы и их файлы
# остались валидными без правок. Порядок = сложность по возрастанию.
DEFAULT_LEVELS: Tuple[LevelCfg, ...] = (
    LevelCfg("base", "Base"),
    LevelCfg("junior", "Junior"),
    LevelCfg("middle", "Middle"),
    LevelCfg("senior", "Senior"),
)


@dataclass(frozen=True)
class PoolCfg:
    id: str
    label: str
    description: str
    blocks: Tuple[BlockCfg, ...]
    levels: Tuple[LevelCfg, ...] = DEFAULT_LEVELS
    # Каталог content/<pool>/ — только у пулов-сидов; у направлений, созданных из UI, его нет.
    dir: Optional[Path] = None

    @property
    def block_ids(self) -> frozenset:
        return frozenset(b.id for b in self.blocks)

    @property
    def level_ids(self) -> frozenset:
        return frozenset(l.id for l in self.levels)

    def subblock_ids(self, block_id: str) -> frozenset:
        for b in self.blocks:
            if b.id == block_id:
                return frozenset(s.id for s in b.subblocks)
        return frozenset()

    def to_dict(self) -> dict:
        """Форма для /api/pools — без пути к каталогу."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "blocks": [
                {
                    "id": b.id,
                    "label": b.label,
                    "color": b.color,
                    "weight": b.weight,
                    "subblocks": [{"id": s.id, "label": s.label} for s in b.subblocks],
                }
                for b in self.blocks
            ],
            "levels": [{"id": l.id, "label": l.label} for l in self.levels],
        }


def _req_str(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise PoolConfigError(f"{where}: '{key}' must be a non-empty string")
    return v.strip()


def parse_blocks(raw_blocks: object) -> Tuple[BlockCfg, ...]:
    """Список блоков из YAML (`blocks:`) или из JSON таблицы pools — одна валидация на оба пути."""
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise PoolConfigError("pool must declare a non-empty 'blocks' list")

    blocks = []
    seen = set()
    for rb in raw_blocks:
        if not isinstance(rb, dict):
            raise PoolConfigError("each block must be a mapping")
        bid = _req_str(rb, "id", "block")
        if not _ID_RE.match(bid):
            raise PoolConfigError(f"block id '{bid}' must match [a-z0-9-]+")
        if bid in seen:
            raise PoolConfigError(f"duplicate block id '{bid}'")
        seen.add(bid)
        color = _req_str(rb, "color", f"block {bid}")
        if not _COLOR_RE.match(color):
            raise PoolConfigError(f"block {bid}: color must be #rrggbb")
        weight = rb.get("weight", 1)
        if not isinstance(weight, int) or weight < 0:
            raise PoolConfigError(f"block {bid}: weight must be a non-negative integer")
        subs = []
        sub_seen = set()
        for rs in rb.get("subblocks") or []:
            if not isinstance(rs, dict):
                raise PoolConfigError(f"block {bid}: each subblock must be a mapping")
            sid = _req_str(rs, "id", f"subblock of {bid}")
            if not _ID_RE.match(sid):
                raise PoolConfigError(f"subblock id '{sid}' must match [a-z0-9-]+")
            if sid in sub_seen:
                raise PoolConfigError(f"block {bid}: duplicate subblock '{sid}'")
            sub_seen.add(sid)
            subs.append(SubblockCfg(id=sid, label=_req_str(rs, "label", f"subblock {sid}")))
        blocks.append(
            BlockCfg(
                id=bid,
                label=_req_str(rb, "label", f"block {bid}"),
                color=color,
                weight=weight,
                subblocks=tuple(subs),
            )
        )
    return tuple(blocks)


def parse_levels(raw_levels: object) -> Tuple[LevelCfg, ...]:
    """Уровни из YAML (`levels:`) или JSON таблицы pools: 2–8 штук, id — slug, уникален, label непустой."""
    if not isinstance(raw_levels, list):
        raise PoolConfigError("'levels' must be a list")
    if not 2 <= len(raw_levels) <= 8:
        raise PoolConfigError("pool must declare between 2 and 8 levels")
    out, seen = [], set()
    for rl in raw_levels:
        if not isinstance(rl, dict):
            raise PoolConfigError("each level must be a mapping")
        lid = _req_str(rl, "id", "level")
        if not _ID_RE.match(lid):
            raise PoolConfigError(f"level id '{lid}' must match [a-z0-9-]+")
        if lid in seen:
            raise PoolConfigError(f"duplicate level id '{lid}'")
        seen.add(lid)
        out.append(LevelCfg(id=lid, label=_req_str(rl, "label", f"level {lid}")))
    return tuple(out)


def levels_to_json(levels: Tuple[LevelCfg, ...]) -> str:
    """Уровни в JSON для столбца pools.levels (та же форма, что в /api/pools)."""
    return json.dumps([{"id": l.id, "label": l.label} for l in levels], ensure_ascii=False)


def _parse_pool(data: dict, pool_dir: Path) -> PoolCfg:
    if not isinstance(data, dict):
        raise PoolConfigError("pool.yaml must be a mapping")
    pid = _req_str(data, "id", "pool")
    if not _ID_RE.match(pid):
        raise PoolConfigError(f"pool id '{pid}' must match [a-z0-9-]+")
    if pid != pool_dir.name:
        raise PoolConfigError(f"pool id '{pid}' must equal directory name '{pool_dir.name}'")
    return PoolCfg(
        id=pid,
        label=_req_str(data, "label", "pool"),
        description=str(data.get("description") or "").strip(),
        blocks=parse_blocks(data.get("blocks")),
        levels=parse_levels(data["levels"]) if data.get("levels") is not None else DEFAULT_LEVELS,
        dir=pool_dir,
    )


def blocks_to_json(blocks: Tuple[BlockCfg, ...]) -> str:
    """Блоки в JSON для столбца pools.blocks (та же форма, что в /api/pools)."""
    return json.dumps(
        [
            {
                "id": b.id,
                "label": b.label,
                "color": b.color,
                "weight": b.weight,
                "subblocks": [{"id": s.id, "label": s.label} for s in b.subblocks],
            }
            for b in blocks
        ],
        ensure_ascii=False,
    )


def pool_from_row(row: dict) -> PoolCfg:
    """Пул из строки таблицы pools (`blocks` — уже распарсенный список). Валидация та же, что для YAML."""
    return PoolCfg(
        id=row["id"],
        label=row["label"],
        description=str(row.get("description") or "").strip(),
        blocks=parse_blocks(row.get("blocks")),
        levels=parse_levels(row["levels"]) if row.get("levels") else DEFAULT_LEVELS,
        dir=None,
    )


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slug_from_label(label: str) -> str:
    """Id направления из названия: транслитерация ru→lat, [a-z0-9-]+; пусто → 'pool'.

    Id живёт в URL, БД и localStorage, поэтому только латиница; занятость id
    (в том числе tombstone удалённого направления) разрешает вызывающий суффиксом.
    """
    s = "".join(_TRANSLIT.get(ch, ch) for ch in label.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "pool"


def _unique_slug(label: object, taken: set, fallback: str) -> str:
    base = slug_from_label(label) if isinstance(label, str) else ""
    if base == "pool":  # slug_from_label подставляет 'pool' на пустое — здесь нужен свой fallback
        base = fallback if not (isinstance(label, str) and label.strip()) else base
    base = base or fallback
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}-{n}", n + 1
    taken.add(sid)
    return sid


def normalize_levels(raw: object, existing: Tuple[LevelCfg, ...] = ()) -> List[dict]:
    """Уровни из UI → форма для parse_levels: новым (без id) id даётся транслитерацией подписи,
    уникально среди переданных и текущих (`-2`, `-3`…). Валидацию делает parse_levels."""
    if not isinstance(raw, list):
        raise PoolConfigError("levels must be a list")
    taken = {l.id for l in existing} | {rl.get("id") for rl in raw if isinstance(rl, dict) and isinstance(rl.get("id"), str)}
    out: List[dict] = []
    for rl in raw:
        if not isinstance(rl, dict):
            raise PoolConfigError("each level must be a mapping")
        lid = rl.get("id") if isinstance(rl.get("id"), str) else _unique_slug(rl.get("label"), taken, "level")
        out.append({"id": lid, "label": rl.get("label")})
    return out


def normalize_blocks(raw: object, existing: Tuple[BlockCfg, ...] = ()) -> List[dict]:
    """Колонки из UI → форма для parse_blocks.

    Новым колонкам/под-колонкам (без id) id даётся транслитерацией названия, уникально в
    направлении / внутри колонки (`-2`, `-3`…); вес — прежний по id или 1 (из UI вес не правится).
    Валидацию названий/цветов делает parse_blocks — здесь только достраиваем поля.
    """
    if not isinstance(raw, list):
        raise PoolConfigError("blocks must be a list")
    old = {b.id: b for b in existing}
    # Занятые id — и переданные, и ВСЕ текущие: удалённая в этом же сохранении колонка не должна
    # отдать свой id новой с тем же названием, иначе её вопросы «выживут» вместо обещанного удаления.
    taken = set(old) | {rb.get("id") for rb in raw if isinstance(rb, dict) and isinstance(rb.get("id"), str)}
    out: List[dict] = []
    for rb in raw:
        if not isinstance(rb, dict):
            raise PoolConfigError("each block must be a mapping")
        bid = rb.get("id") if isinstance(rb.get("id"), str) else _unique_slug(rb.get("label"), taken, "block")
        weight = rb.get("weight")
        if not isinstance(weight, int) or isinstance(weight, bool):  # bool — подкласс int
            weight = old[bid].weight if bid in old else 1
        raw_subs = rb.get("subblocks")
        if raw_subs is None:
            raw_subs = []
        if not isinstance(raw_subs, list):
            raise PoolConfigError(f"block {bid}: subblocks must be a list")
        old_subs = {s.id for s in old[bid].subblocks} if bid in old else set()
        sub_taken = old_subs | {rs.get("id") for rs in raw_subs if isinstance(rs, dict) and isinstance(rs.get("id"), str)}
        subs = []
        for rs in raw_subs:
            if not isinstance(rs, dict):
                raise PoolConfigError(f"block {bid}: each subblock must be a mapping")
            sid = rs.get("id") if isinstance(rs.get("id"), str) else _unique_slug(rs.get("label"), sub_taken, "sub")
            subs.append({"id": sid, "label": rs.get("label")})
        out.append({"id": bid, "label": rb.get("label"), "color": rb.get("color"), "weight": weight, "subblocks": subs})
    return out


def load_pool(pool_dir: Path) -> PoolCfg:
    """Прочитать один каталог пула. Бросает PoolConfigError / OSError / yaml.YAMLError."""
    data = yaml.safe_load((pool_dir / "pool.yaml").read_text(encoding="utf-8"))
    return _parse_pool(data, pool_dir)


def load_pools(content_dir: Path) -> Dict[str, PoolCfg]:
    """Все валидные пулы в content_dir, по id. Каталоги без pool.yaml пропускаются молча,
    с невалидным — с предупреждением."""
    out: Dict[str, PoolCfg] = {}
    if not content_dir.exists():
        return out
    for d in sorted(p for p in content_dir.iterdir() if p.is_dir()):
        if not (d / "pool.yaml").exists():
            continue
        try:
            cfg = load_pool(d)
        except (PoolConfigError, yaml.YAMLError, OSError) as exc:
            log.warning("pool '%s' skipped: %s", d.name, exc)
            continue
        out[cfg.id] = cfg
    return out


def block_weights(pool: PoolCfg) -> Dict[str, int]:
    """Веса блоков для sampler (порядок блоков сохраняется)."""
    return {b.id: b.weight for b in pool.blocks}


def default_pool_id(pools: Iterable[str]) -> str | None:
    """Пул по умолчанию для запросов без ?pool: data-engineer, иначе первый по алфавиту."""
    ids = sorted(pools)
    if not ids:
        return None
    return "data-engineer" if "data-engineer" in ids else ids[0]
