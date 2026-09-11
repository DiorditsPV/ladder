#!/usr/bin/env python3
"""Детерминированная часть скилла ladder-topic: JSON темы → направление в Ladder (+ проверка покрытия).

    python3 .claude/skills/ladder-topic/write_topic.py topic.json --check [--per-cell N]
    python3 .claude/skills/ladder-topic/write_topic.py topic.json --upload [--api URL] [--overwrite]
    python3 .claude/skills/ladder-topic/write_topic.py topic.json --files [--fresh] [--sync] [--api URL]

Режимы (ровно один):
  --check  — валидация и матрица покрытия, ничего не пишет;
  --upload — основной путь (spec 2026-09-11-content-in-db): направление заносится через API в работающий Ladder
             (`--api`, по умолчанию $LADDER_URL или http://localhost:8000; вход — $LADDER_EMAIL/$LADDER_PASSWORD,
             для локального dev — $INTERVIEW_OWNER_EMAIL/$INTERVIEW_OWNER_PASSWORD). Нет направления — создаётся с id
             колонок/уровней из JSON; есть — недостающие колонки, под-колонки и уровни дописываются (ничего не
             удаляется). Карточки создаются с явными id; занятый id пропускается, с --overwrite — обновляется;
  --files  — только для пресетов в content/ (data-engineer, system-analyst): запись файлов, --sync — явное
             обновление пресета на сервере (POST /api/pools/sync?pool=<id>&update=true).

Вход — JSON:
  {"pool": {"id", "label", "description", "blocks": [{"id","label","color","subblocks"?: [{"id","label"}]}],
            "levels": [{"id","label"}]},
   "cards": [{"id","block","subblock"?,"difficulty","title","topic","tags","question","answer","kind"?}]}

Валидирует схему, уровни 2–8 и 1–3 тега из 17 концептов проекта; пишет pool.yaml и карточки
через python-frontmatter. Печатает распределение по колонкам, уровням и под-колонкам.
Количество карточек и длина ответа не доказывают качество: квоты по умолчанию нет.
--per-cell N — только явно запрошенный минимум (0 отключает его), нарушение даёт exit 2.
--check ничего не записывает. --fresh удаляет каталог темы; без него занятые id пропускаются.
--sync: POST /api/pools/sync + проверка /api/graph; заранее проверь адрес и доступ сервера к файлам.
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
        if not 1 <= len(tags) <= 3 or not set(tags) <= TAGS:
            die(f"{cid}: tags — 1–3 из 17 концептов проекта, получено {tags}")
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
    header = (f"# Направление «{pool['label']}» — сгенерировано скиллом ladder-topic.\n"
              f"# levels — ряды матрицы сверху вниз (первый — самый лёгкий, верхний ряд); weight блоков ∝ числу карточек.\n")
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


def coverage(pool: dict, cards: list, per_cell: int | None = None) -> int:
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
            below_minimum = per_cell is not None and n < per_cell
            mark = "!" if below_minimum else ""
            thin += below_minimum
            row += f"{str(n) + mark:>10}"
        print(f"{b['id']:<{w}}{row}")
    print(f"карточек: {len(cards)}" + (f"; ячеек тоньше {per_cell}: {thin}" if per_cell is not None else "; квота не задана"))
    by_sub = Counter((c["block"], c.get("subblock")) for c in cards if c.get("subblock"))
    for b in pool["blocks"]:
        for sb in b.get("subblocks") or []:
            n = by_sub[(b["id"], sb["id"])]
            print(f"  под-колонка {b['id']}/{sb['id']}: {n}{'  !' if per_cell is not None and n < per_cell else ''}")
    return thin


def api_client(api: str):
    """httpx.Client с сессией Ladder. Креды — LADDER_* (боевой/общий случай) или INTERVIEW_OWNER_* (локальный dev)."""
    import httpx

    email = os.environ.get("LADDER_EMAIL") or os.environ.get("INTERVIEW_OWNER_EMAIL", "owner@interview.local")
    password = os.environ.get("LADDER_PASSWORD") or os.environ.get("INTERVIEW_OWNER_PASSWORD", "interview-dev")
    http = httpx.Client(base_url=api.rstrip("/"), timeout=60)
    r = http.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        die(f"{api}: вход не удался ({r.status_code}) — проверь LADDER_EMAIL/LADDER_PASSWORD")
    return http


def _detail(r) -> str:
    try:
        return str(r.json().get("detail"))
    except ValueError:
        return r.text[:200]


def _ok(r):
    if r.status_code >= 400:
        die(f"{r.request.method} {r.request.url.path}: {r.status_code} {_detail(r)}")
    return r.json()


def _blocks_payload(pool: dict, cards: list) -> list:
    """Колонки для POST /api/pools: id из JSON, цвет — из JSON или палитры, вес ∝ числу карточек."""
    per_block = Counter(c["block"] for c in cards)
    total = sum(per_block.values()) or 1
    return [
        {"id": b["id"], "label": b["label"], "color": b.get("color") or COLORS[i % len(COLORS)],
         "weight": max(1, round(100 * per_block[b["id"]] / total)),
         "subblocks": [{"id": s["id"], "label": s["label"]} for s in b.get("subblocks") or []]}
        for i, b in enumerate(pool["blocks"])
    ]


def _extend_structure(current: dict, pool: dict, cards: list):
    """Недостающие в направлении колонки/под-колонки/уровни из JSON (ничего не удаляет и не переставляет
    существующее). Возвращает (blocks, levels, что добавлено) — blocks/levels None, если менять нечего."""
    added: list = []
    blocks = [{"id": b["id"], "label": b["label"], "color": b["color"], "weight": b.get("weight", 1),
               "subblocks": [{"id": s["id"], "label": s["label"]} for s in b.get("subblocks") or []]}
              for b in current["blocks"]]
    by_id = {b["id"]: b for b in blocks}
    fresh = {b["id"]: b for b in _blocks_payload(pool, cards)}
    for b in pool["blocks"]:
        if b["id"] not in by_id:
            entry = dict(fresh[b["id"]])
            entry["color"] = b.get("color") or COLORS[len(blocks) % len(COLORS)]
            blocks.append(entry)
            by_id[b["id"]] = entry
            added.append(f"колонка {b['id']}")
            continue
        have = {s["id"] for s in by_id[b["id"]]["subblocks"]}
        for s in b.get("subblocks") or []:
            if s["id"] not in have:
                by_id[b["id"]]["subblocks"].append({"id": s["id"], "label": s["label"]})
                added.append(f"под-колонка {b['id']}/{s['id']}")
    levels = [{"id": lv["id"], "label": lv["label"]} for lv in current["levels"]]
    have_levels = {lv["id"] for lv in levels}
    prev = None
    for lv in pool["levels"]:
        if lv["id"] not in have_levels:
            at = 0 if prev is None else next(i for i, x in enumerate(levels) if x["id"] == prev) + 1
            levels.insert(at, {"id": lv["id"], "label": lv["label"]})
            have_levels.add(lv["id"])
            added.append(f"уровень {lv['id']}")
        prev = lv["id"]
    changed_blocks = any(a.startswith(("колонка", "под-колонка")) for a in added)
    changed_levels = any(a.startswith("уровень") for a in added)
    return (blocks if changed_blocks else None), (levels if changed_levels else None), added


def upload(spec: dict, http, *, overwrite: bool = False) -> dict:
    """JSON темы → направление через API. `http` — httpx.Client с сессией (в тестах — TestClient)."""
    pool, cards = spec["pool"], spec["cards"]
    pid = pool["id"]
    report = {"pool_created": False, "structure_added": [], "created": 0, "updated": 0, "skipped": 0, "errors": []}
    r = http.get(f"/api/pools/{pid}")
    if r.status_code == 404:
        _ok(http.post("/api/pools", json={
            "id": pid, "label": pool["label"], "description": pool.get("description") or "",
            "blocks": _blocks_payload(pool, cards),
            "levels": [{"id": lv["id"], "label": lv["label"]} for lv in pool["levels"]],
        }))
        report["pool_created"] = True
    else:
        blocks, levels, added = _extend_structure(_ok(r), pool, cards)
        if added:
            body = {k: v for k, v in (("blocks", blocks), ("levels", levels)) if v is not None}
            _ok(http.put(f"/api/pools/{pid}", json=body))
            report["structure_added"] = added
    for c in cards:
        payload = {"pool": pid, "id": c["id"], "block": c["block"], "difficulty": c["difficulty"],
                   "title": c["title"].strip(), "topic": c["topic"].strip(), "tags": list(c["tags"]),
                   "question": c["question"].strip(), "answer": c["answer"].strip(),
                   "kind": c.get("kind") or "question", "weight": int(c.get("weight") or 1)}
        if c.get("subblock"):
            payload["subblock"] = c["subblock"]
        for key in ("starterCode", "rubric"):
            if c.get(key):
                payload[key] = c[key]
        r = http.post("/api/nodes", json=payload)
        if r.status_code == 200:
            report["created"] += 1
        elif r.status_code == 409 and overwrite:
            update = {k: v for k, v in payload.items() if k != "id"}
            update.setdefault("subblock", "")  # в JSON под-колонки нет — снять и на сервере
            u = http.put(f"/api/nodes/{c['id']}", json=update)
            if u.status_code == 200:
                report["updated"] += 1
            else:
                report["errors"].append({"id": c["id"], "error": f"{u.status_code} {_detail(u)}"})
        elif r.status_code == 409:
            report["skipped"] += 1
        else:
            report["errors"].append({"id": c["id"], "error": f"{r.status_code} {_detail(r)}"})
    return report


def sync(api: str, pool_id: str) -> None:
    """--files --sync: явное обновление пресета на сервере из его content/ (update=true, только этот пул)."""
    http = api_client(api)
    rep = _ok(http.post("/api/pools/sync", params={"pool": pool_id, "update": "true"}))
    print("sync:", {k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()})
    if rep["errors"]:
        for e in rep["errors"]:
            print(f"  ✗ {e['file']}: {e['error']}")
        die("sync: ошибки импорта")
    graph = _ok(http.get("/api/graph", params={"pool": pool_id}))
    print(f"/api/graph?pool={pool_id}: {len(graph['nodes'])} нод, ошибок {len(graph['errors'])}")
    if graph["errors"]:
        die("/api/graph: ошибки импорта")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="JSON темы")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="только валидация и матрица; ничего не пишет")
    mode.add_argument("--upload", action="store_true", help="занести направление через API (основной путь)")
    mode.add_argument("--files", action="store_true", help="записать в content/ — только для пресетов")
    ap.add_argument("--overwrite", action="store_true", help="--upload: обновлять карточки с занятыми id")
    ap.add_argument("--content", default="content", help="--files: каталог content/ (по умолчанию ./content)")
    ap.add_argument("--fresh", action="store_true", help="--files: снести каталог темы перед записью")
    ap.add_argument("--per-cell", type=int, default=None, help="явно заданный минимум в ячейке; по умолчанию квоты нет")
    ap.add_argument("--sync", action="store_true", help="--files: после записи — явное обновление пресета на сервере")
    ap.add_argument("--api", default=os.environ.get("LADDER_URL") or os.environ.get("API_URL", "http://localhost:8000"))
    a = ap.parse_args()
    if a.per_cell is not None and a.per_cell < 0:
        ap.error("--per-cell должен быть неотрицательным")

    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    validate(spec)
    pool, cards = spec["pool"], spec["cards"]
    if a.check:
        sys.exit(2 if coverage(pool, cards, a.per_cell) else 0)
    if a.upload:
        http = api_client(a.api)
        rep = upload(spec, http, overwrite=a.overwrite)
        what = "создано" if rep["pool_created"] else "дополнено"
        print(f"{a.api} · {pool['id']} ({what}): карточек создано {rep['created']}, обновлено {rep['updated']}, "
              f"пропущено (id занят) {rep['skipped']}")
        for item in rep["structure_added"]:
            print(f"  + {item}")
        for err in rep["errors"]:
            print(f"  ✗ {err['id']}: {err['error']}")
        server_cards = _ok(http.get("/api/nodes", params={"pool": pool["id"]}))
        thin = coverage(pool, server_cards, a.per_cell)
        if rep["errors"]:
            die(f"ошибок: {len(rep['errors'])}")
        sys.exit(2 if thin else 0)
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
