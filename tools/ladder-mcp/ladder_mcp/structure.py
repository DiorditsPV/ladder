"""Правка структуры направления поверх `PUT /api/pools/{id}` (read-modify-write).

API принимает колонки и уровни целыми списками: колонка/уровень вне списка удаляется (с вопросами), новые
элементы без `id` получают id из названия, порядок в списке — порядок на доске. Здесь — чистые функции над
этими списками, без HTTP.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

# Палитра колонок — та же, что в редакторе направлений (frontend BlocksEditor.BLOCK_PALETTE).
PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#db2777", "#64748b"]


def blocks_payload(pool: dict) -> List[dict]:
    """Колонки направления в форме тела PUT (id сохраняются — это «существующие» колонки)."""
    return [
        {
            "id": b["id"],
            "label": b["label"],
            "color": b["color"],
            "weight": b.get("weight", 1),
            "subblocks": [{"id": s["id"], "label": s["label"]} for s in b.get("subblocks") or []],
        }
        for b in pool["blocks"]
    ]


def levels_payload(pool: dict) -> List[dict]:
    return [{"id": lv["id"], "label": lv["label"]} for lv in pool["levels"]]


def next_color(blocks: Iterable[dict]) -> str:
    """Первый цвет палитры, которого ещё нет у колонок; все заняты — по кругу."""
    blocks = list(blocks)
    used = {b.get("color") for b in blocks}
    for color in PALETTE:
        if color not in used:
            return color
    return PALETTE[len(blocks) % len(PALETTE)]


def index_of(items: List[dict], item_id: str, what: str) -> int:
    for i, item in enumerate(items):
        if item.get("id") == item_id:
            return i
    available = ", ".join(str(item.get("id")) for item in items) or "none"
    raise KeyError(f"{what} '{item_id}' not found (available: {available})")


def insert_at(items: List[dict], item: dict, position: Optional[int]) -> List[dict]:
    """Вставить элемент: position — 0-based индекс, None или за краем — в конец, отрицательный — с конца."""
    if position is None or position >= len(items):
        items.append(item)
    else:
        items.insert(max(0, position if position >= 0 else len(items) + position + 1), item)
    return items


def move_to(items: List[dict], index: int, position: Optional[int]) -> List[dict]:
    if position is None:
        return items
    item = items.pop(index)
    return insert_at(items, item, position)


def new_id(before: Iterable[dict], after: Iterable[dict]) -> Optional[str]:
    """Id элемента, который появился после PUT (сервер назначает id новым по названию)."""
    old = {item["id"] for item in before if item.get("id")}
    for item in after:
        if item["id"] not in old:
            return item["id"]
    return None
