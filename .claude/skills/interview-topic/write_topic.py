#!/usr/bin/env python3
"""Детерминированная часть скилла interview-topic: JSON темы → content/<pool>/ (+ проверка покрытия, sync).

    python3 .claude/skills/interview-topic/write_topic.py topic.json [--fresh] [--per-cell N] [--sync] [--api URL]

Вход — JSON:
  {"pool": {"id", "label", "description", "blocks": [{"id","label","color","subblocks"?: [{"id","label"}]}],
            "levels": [{"id","label"}]},
   "cards": [{"id","block","subblock"?,"difficulty","title","topic","tags","question","answer","kind"?}]}

Что делает: валидирует (уровни 2–8; теги 1–3 из 17 концептов ∪ pool.tags — свои теги темы вне дата-инженерии;
difficulty ∈ levels; block/subblock ∈ pool; id = "<pool>-<block>-NN"), предупреждает об ответах короче 400 или
длиннее 2000 знаков, пишет pool.yaml (веса блоков ∝ числу карточек, pool.tags — как документация словаря) и карточки
через python-frontmatter в нормализованном формате проекта, печатает матрицу «колонка × уровень», покрытие
под-колонок и ячейки тоньше --per-cell. --check — только проверка и матрица, без записи. --fresh сносит каталог темы; без него существующие файлы остаются, карточки
с занятыми id пропускаются (режим дополнения). --sync: POST /api/pools/sync + проверка /api/graph → 0 ошибок.
Запускать из корня репозитория с активированным backend/.venv (нужен python-frontmatter).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import frontmatter
import yaml

TAGS = {"architecture", "orchestration", "optimization", "partitioning", "deployment", "storage", "streaming",
        "consistency", "data-modeling", "quality", "distributed", "sql", "monitoring", "memory", "file-formats",
        "domain", "concurrency"}
ID_RE = re.compile(r"^[a-z0-9-]+$")
COLORS = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#db2777", "#64748b"]


def die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def validate(spec: dict) -> None:
    pool, cards = spec.get("pool") or {}, spec.get("cards") or []
    for key in ("id", "label", "blocks", "levels"):
        if not pool.get(key):
            die(f"pool.{key} обязателен")
    if not ID_RE.match(pool["id"]):
        die(f"pool.id '{pool['id']}' — только [a-z0-9-]")
    if not 2 <= len(pool["levels"]) <= 8:
        die("уровней должно быть от 2 до 8")
    lids = [l["id"] for l in pool["levels"]]
    if len(set(lids)) != len(lids) or not all(ID_RE.match(x) for x in lids):
        die("id уровней — уникальные slug'и")
    if not all((l.get("label") or "").strip() for l in pool["levels"]):
        die("у каждого уровня нужен label")
    bids = [b["id"] for b in pool["blocks"]]
    if len(set(bids)) != len(bids) or not all(ID_RE.match(x) for x in bids):
        die("id колонок — уникальные slug'и")
    subs = {b["id"]: {s["id"] for s in (b.get("subblocks") or [])} for b in pool["blocks"]}
    extra = pool.get("tags") or []
    if not all(isinstance(t, str) and ID_RE.match(t) for t in extra):
        die("pool.tags — список slug'ов (латиница, дефисы)")
    allowed = TAGS | set(extra)
    seen = set()
    for c in cards:
        cid = c.get("id") or ""
        if not ID_RE.match(cid) or not cid.startswith(f"{pool['id']}-{c.get('block')}-"):
            die(f"карточка '{cid}': id должен быть '{pool['id']}-<block>-NN'")
        if cid in seen:
            die(f"дубль id '{cid}'")
        seen.add(cid)
        if c.get("block") not in subs:
            die(f"{cid}: block '{c.get('block')}' не объявлен")
        if c.get("subblock") and c["subblock"] not in subs[c["block"]]:
            die(f"{cid}: subblock '{c['subblock']}' не объявлен в '{c['block']}'")
        if subs[c["block"]] and not c.get("subblock"):
            die(f"{cid}: у колонки '{c['block']}' есть под-колонки — укажи subblock")
        if c.get("difficulty") not in lids:
            die(f"{cid}: difficulty '{c.get('difficulty')}' не из levels {lids}")
        tags = c.get("tags") or []
        if not 1 <= len(tags) <= 3 or not set(tags) <= allowed:
            die(f"{cid}: tags — 1–3 из 17 концептов ∪ pool.tags {sorted(extra)}, получено {tags}")
        for key in ("title", "topic", "question", "answer"):
            if not (c.get(key) or "").strip():
                die(f"{cid}: поле '{key}' пустое")
        if c["question"].lstrip().startswith("#") or any(line.startswith("#") for line in c["answer"].splitlines()):
            die(f"{cid}: строки вопроса/ответа не должны начинаться с '#' (маркеры разбиения тела)")


def write_pool_yaml(pool: dict, cards: list, path: Path) -> None:
    per_block = Counter(c["block"] for c in cards)
    total = sum(per_block.values()) or 1
    blocks = []
    for i, b in enumerate(pool["blocks"]):
        entry = {"id": b["id"], "label": b["label"], "color": b.get("color") or COLORS[i % len(COLORS)],
                 "weight": max(1, round(100 * per_block[b["id"]] / total))}
        if b.get("subblocks"):
            entry["subblocks"] = [{"id": s["id"], "label": s["label"]} for s in b["subblocks"]]
        blocks.append(entry)
    doc = {"id": pool["id"], "label": pool["label"], "description": pool.get("description") or "",
           "blocks": blocks, "levels": [{"id": l["id"], "label": l["label"]} for l in pool["levels"]]}
    if pool.get("tags"):
        doc["tags"] = list(pool["tags"])  # словарь темы сверх 17 концептов; бэкенд ключ не читает
    header = (f"# Направление «{pool['label']}» — сгенерировано скиллом interview-topic.\n"
              f"# levels — ряды матрицы снизу вверх (первый — самый лёгкий); weight блоков ∝ числу карточек.\n")
    path.write_text(header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_card(card: dict, path: Path) -> None:
    meta = {"block": card["block"], "difficulty": card["difficulty"], "id": card["id"],
            "kind": card.get("kind") or "question", "tags": list(card["tags"]), "title": card["title"].strip(),
            "topic": card["topic"].strip(), "weight": int(card.get("weight") or 1)}
    if card.get("subblock"):
        meta["subblock"] = card["subblock"]
    post = frontmatter.Post(f"## Вопрос\n{card['question'].strip()}\n\n## Ответ\n{card['answer'].strip()}\n", **meta)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post, sort_keys=True, allow_unicode=True) + "\n", encoding="utf-8")


def coverage(pool: dict, cards: list, per_cell: int) -> int:
    lids = [l["id"] for l in pool["levels"]]
    cnt = Counter((c["block"], c["difficulty"]) for c in cards)
    w = max(len(b["id"]) for b in pool["blocks"]) + 2
    print("матрица покрытия (колонка × уровень):")
    print(" " * w + "".join(f"{l:>10}" for l in lids))
    thin = 0
    for b in pool["blocks"]:
        row = ""
        for l in lids:
            n = cnt[(b["id"], l)]
            mark = "" if n >= per_cell else "!"
            thin += n < per_cell
            row += f"{str(n) + mark:>10}"
        print(f"{b['id']:<{w}}{row}")
    print(f"карточек: {len(cards)}; ячеек тоньше {per_cell}: {thin}")
    by_sub = Counter((c["block"], c.get("subblock")) for c in cards if c.get("subblock"))
    for b in pool["blocks"]:
        for sb in b.get("subblocks") or []:
            n = by_sub[(b["id"], sb["id"])]
            print(f"  под-колонка {b['id']}/{sb['id']}: {n}{'  !' if n < per_cell else ''}")
    return thin


def warn_lengths(cards: list) -> None:
    """Мягкая проверка: ответ короче 400 знаков — почти наверняка пустой, длиннее 2000 — лекция."""
    for c in cards:
        n = len((c.get("answer") or "").strip())
        if n < 400 or n > 2000:
            print(f"  ! {c['id']}: ответ {n} знаков (ориентир 400–1500)")


def sync(api: str, pool_id: str) -> None:
    import urllib.request
    import http.cookiejar
    email = os.environ.get("INTERVIEW_OWNER_EMAIL", "owner@interview.local")
    password = os.environ.get("INTERVIEW_OWNER_PASSWORD", "interview-dev")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    body = json.dumps({"email": email, "password": password}).encode()
    opener.open(urllib.request.Request(f"{api}/api/auth/login", data=body, headers={"Content-Type": "application/json"}))
    rep = json.loads(opener.open(urllib.request.Request(f"{api}/api/pools/sync", data=b"", method="POST")).read())
    print("sync:", {k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()})
    if rep["errors"]:
        for e in rep["errors"]:
            print(f"  ✗ {e['file']}: {e['error']}")
        die("sync: ошибки импорта")
    graph = json.loads(opener.open(f"{api}/api/graph?pool={pool_id}").read())
    print(f"/api/graph?pool={pool_id}: {len(graph['nodes'])} нод, ошибок {len(graph['errors'])}")
    if graph["errors"]:
        die("/api/graph: ошибки импорта")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="JSON темы")
    ap.add_argument("--content", default="content", help="каталог content/ (по умолчанию ./content)")
    ap.add_argument("--fresh", action="store_true", help="снести каталог темы перед записью")
    ap.add_argument("--per-cell", type=int, default=2, help="минимум карточек в ячейке колонка × уровень")
    ap.add_argument("--sync", action="store_true", help="после записи: POST /api/pools/sync и проверка /api/graph")
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--check", action="store_true", help="только валидация и матрица, ничего не писать")
    a = ap.parse_args()

    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    validate(spec)
    pool, cards = spec["pool"], spec["cards"]
    warn_lengths(cards)
    if a.check:
        sys.exit(2 if coverage(pool, cards, a.per_cell) else 0)
    root = Path(a.content) / pool["id"]
    if a.fresh and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    existing = {p.stem for p in root.rglob("*.md")} | {p.stem for p in root.rglob("*.json")}
    written, skipped = 0, 0
    for c in cards:
        if c["id"] in existing:
            skipped += 1
            continue
        write_card(c, root / c["block"] / f"{c['id']}.md")
        written += 1
    all_cards = cards if a.fresh else cards + [
        {"block": frontmatter.load(str(p)).metadata.get("block"), "difficulty": frontmatter.load(str(p)).metadata.get("difficulty")}
        for p in root.rglob("*.md") if p.stem in existing and p.stem not in {c["id"] for c in cards}
    ]
    write_pool_yaml(pool, all_cards, root / "pool.yaml")
    print(f"content/{pool['id']}: записано {written}, пропущено (id занят) {skipped}, pool.yaml обновлён")
    thin = coverage(pool, all_cards, a.per_cell)
    if a.sync:
        sync(a.api, pool["id"])
    sys.exit(2 if thin else 0)


if __name__ == "__main__":
    main()
