"""MCP-сервер Ladder: направления, их структура (колонки, под-колонки, уровни), топики и вопросы через HTTP API.

Запуск (stdio):  LADDER_URL=… LADDER_EMAIL=… LADDER_PASSWORD=… python -m ladder_mcp
Словарь API ↔ MCP: direction = pool, column = block, subcolumn = subblock, level = difficulty-row, question = node.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from .client import LadderClient, LadderError, seg
from .structure import blocks_payload, index_of, insert_at, levels_payload, move_to, new_id, next_color

INSTRUCTIONS = """\
Ladder is a self-study board. A direction is a topic laid out as a matrix: columns (vertical areas of the topic,
optionally split into subcolumns) × levels (horizontal rows ordered from the easiest at the top to the hardest at
the bottom). Each cell holds question cards. A card has a direct question, a reference answer, a short `topic`
slug (a subtopic inside its column), 1–3 `tags` from the concept vocabulary (list_tags) and a kind
(question | task; a task may have starter code and self-check criteria).

Good cards: one direct question about the essence, understandable without extra context and answerable aloud in
3–5 minutes — no invented mini-cases; answer 400–1500 characters: essence first, then the mechanism, then an
example; title 3–7 words; no line of a question or an answer may start with '#'. Inside every column (subcolumn)
the cards should form a ladder from basics at the top level to expert at the bottom level.

Call get_direction first to see ids, the structure and the coverage matrix (column × level counts). Deleting a
column, level, topic or direction that holds questions needs confirm=true — or move the questions first with
move_questions_to. Positions are 0-based. Everything edited here is marked as user-edited, so a content sync from
files will not overwrite it.
"""

TOOL_NAMES = [
    "list_directions", "get_direction", "create_direction", "update_direction", "delete_direction",
    "add_column", "update_column", "delete_column", "add_subcolumn", "update_subcolumn", "delete_subcolumn",
    "add_level", "update_level", "delete_level",
    "list_topics", "rename_topic", "delete_topic",
    "list_questions", "get_question", "create_question", "create_questions", "update_question", "delete_question",
    "list_tags", "sync_from_files",
]

Kind = Literal["question", "task"]
DirectionId = Annotated[str, Field(description="Direction id (slug), e.g. 'apache-kafka'")]
ColumnId = Annotated[str, Field(description="Column id inside the direction (see get_direction)")]
LevelId = Annotated[str, Field(description="Level id inside the direction (see get_direction)")]
Position = Annotated[Optional[int], Field(description="0-based position; omit to append at the end")]


class ColumnSpec(BaseModel):
    label: str = Field(description="Column name shown on the board")
    color: Optional[str] = Field(default=None, description="#rrggbb; omitted — next palette colour")
    subcolumns: List[str] = Field(default_factory=list, description="Subcolumn names, in board order")


class QuestionSpec(BaseModel):
    column_id: str
    level_id: str
    question: str
    answer: str = ""
    title: Optional[str] = None
    topic: Optional[str] = Field(default=None, description="Subtopic slug; omitted — derived from the title")
    subcolumn_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    kind: Kind = "question"
    starter_code: Optional[str] = None
    rubric: List[str] = Field(default_factory=list, description="Self-check criteria (tasks)")
    question_id: Optional[str] = Field(default=None, description="Explicit card id (slug); omitted — generated")
    weight: int = 1


def _slug(text: str, fallback: str = "general") -> str:
    translit = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    })
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().translate(translit)).strip("-")
    return slug[:40].strip("-") or fallback


def _column_out(block: dict, counts: Optional[Dict[str, int]] = None, sub_counts: Optional[Dict[str, int]] = None) -> dict:
    out = {
        "id": block["id"],
        "label": block["label"],
        "color": block["color"],
        "subcolumns": [
            {"id": s["id"], "label": s["label"], **({"questions": sub_counts.get(s["id"], 0)} if sub_counts is not None else {})}
            for s in block.get("subblocks") or []
        ],
    }
    if counts is not None:
        out["questions"] = counts.get(block["id"], 0)
    return out


def _question_brief(node: dict) -> dict:
    question = node.get("question") or ""
    return {
        "id": node["id"],
        "title": node.get("title"),
        "column": node["block"],
        "subcolumn": node.get("subblock"),
        "level": node["difficulty"],
        "topic": node["topic"],
        "tags": node.get("tags") or [],
        "kind": node.get("kind", "question"),
        "hidden": node.get("hidden", False),
        "question": question if len(question) <= 200 else question[:197] + "…",
    }


def _question_body(direction_id: str, spec: QuestionSpec) -> dict:
    body: Dict[str, Any] = {
        "pool": direction_id,
        "block": spec.column_id,
        "difficulty": spec.level_id,
        "question": spec.question,
        "answer": spec.answer,
        "topic": spec.topic or _slug(spec.title or spec.question),
        "tags": spec.tags,
        "kind": spec.kind,
        "rubric": spec.rubric,
        "weight": spec.weight,
    }
    for key, value in (("title", spec.title), ("subblock", spec.subcolumn_id), ("starterCode", spec.starter_code),
                       ("id", spec.question_id)):
        if value is not None:
            body[key] = value
    return body


def build_server(client: LadderClient) -> MCPServer:
    server = MCPServer("ladder", instructions=INSTRUCTIONS)

    async def api(method: str, path: str, *, json: Any = None, **params: Any) -> Any:
        try:
            return await client.request(method, path, json=json, params=params)
        except LadderError as exc:
            raise ToolError(f"Ladder API {exc.status}: {exc.detail}") from exc

    async def pool(direction_id: str) -> dict:
        return await api("GET", f"/api/pools/{seg(direction_id)}")

    async def questions_of(direction_id: str, **filters: Any) -> List[dict]:
        return await api("GET", "/api/nodes", pool=direction_id, **filters)

    async def put_structure(direction_id: str, **fields: Any) -> dict:
        return await api("PUT", f"/api/pools/{seg(direction_id)}", json=fields)

    def lookup(items: List[dict], item_id: str, what: str) -> int:
        try:
            return index_of(items, item_id, what)
        except KeyError as exc:
            raise ToolError(str(exc.args[0])) from exc

    async def direction_view(direction_id: str) -> dict:
        p = await pool(direction_id)
        nodes = await questions_of(direction_id)
        by_col: Dict[str, int] = {}
        by_sub: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        coverage: Dict[str, Dict[str, int]] = {b["id"]: {lv["id"]: 0 for lv in p["levels"]} for b in p["blocks"]}
        for n in nodes:
            by_col[n["block"]] = by_col.get(n["block"], 0) + 1
            by_level[n["difficulty"]] = by_level.get(n["difficulty"], 0) + 1
            if n.get("subblock"):
                key = f"{n['block']}/{n['subblock']}"
                by_sub[key] = by_sub.get(key, 0) + 1
            if n["block"] in coverage and n["difficulty"] in coverage[n["block"]]:
                coverage[n["block"]][n["difficulty"]] += 1
        columns = []
        for b in p["blocks"]:
            subs = {s["id"]: by_sub.get(f"{b['id']}/{s['id']}", 0) for s in b.get("subblocks") or []}
            columns.append(_column_out(b, by_col, subs))
        return {
            "id": p["id"],
            "label": p["label"],
            "description": p.get("description", ""),
            "lang": p.get("lang", "ru"),
            "demo": p.get("demo", False),
            "translation_of": p.get("translation_of"),
            "questions": len(nodes),
            "columns": columns,
            "levels": [{"id": lv["id"], "label": lv["label"], "questions": by_level.get(lv["id"], 0)} for lv in p["levels"]],
            "coverage": coverage,
        }

    # ---------- направления ----------

    @server.tool()
    async def list_directions() -> dict:
        """List all directions (topics) with their columns, levels and question counts."""
        pools = await api("GET", "/api/pools")
        return {"directions": [
            {
                "id": p["id"], "label": p["label"], "description": p.get("description", ""),
                "lang": p.get("lang", "ru"), "demo": p.get("demo", False), "translation_of": p.get("translation_of"),
                "questions": (p.get("counts") or {}).get("nodes", 0),
                "columns": [_column_out(b) for b in p["blocks"]],
                "levels": [{"id": lv["id"], "label": lv["label"]} for lv in p["levels"]],
            }
            for p in pools
        ]}

    @server.tool()
    async def get_direction(direction_id: DirectionId) -> dict:
        """Get one direction: columns with subcolumns, levels (top = easiest), question counts and the coverage
        matrix `coverage[column_id][level_id]` = number of questions in that cell."""
        return await direction_view(direction_id)

    @server.tool()
    async def create_direction(
        label: Annotated[str, Field(description="Direction name, e.g. 'Apache Kafka'")],
        description: str = "",
        columns: Annotated[Optional[List[ColumnSpec]], Field(description="Columns (vertical areas); required unless copy_from")] = None,
        levels: Annotated[Optional[List[str]], Field(description="2–8 level names from easiest to hardest; omitted — Base/Junior/Middle/Senior")] = None,
        direction_id: Annotated[Optional[str], Field(description="Explicit id (slug); omitted — derived from the label")] = None,
        copy_from: Annotated[Optional[str], Field(description="Copy columns, levels and questions of this direction")] = None,
    ) -> dict:
        """Create a direction: either with its own columns and levels, or as a copy of another direction."""
        body: Dict[str, Any] = {"label": label, "description": description}
        if direction_id:
            body["id"] = direction_id
        if copy_from:
            if columns or levels:
                raise ToolError("pass either copy_from or columns/levels, not both")
            body["preset"] = copy_from
        else:
            if not columns:
                raise ToolError("at least one column is required (or copy_from an existing direction)")
            blocks: List[dict] = []
            for col in columns:
                blocks.append({"label": col.label, "color": col.color or next_color(blocks),
                               "subblocks": [{"label": s} for s in col.subcolumns]})
            body["blocks"] = blocks
            if levels is not None:
                body["levels"] = [{"label": name} for name in levels]
        created = await api("POST", "/api/pools", json=body)
        return await direction_view(created["id"])

    @server.tool()
    async def update_direction(direction_id: DirectionId, label: Optional[str] = None, description: Optional[str] = None) -> dict:
        """Rename a direction or change its description."""
        fields = {k: v for k, v in (("label", label), ("description", description)) if v is not None}
        if not fields:
            raise ToolError("nothing to update: pass label and/or description")
        await put_structure(direction_id, **fields)
        return await direction_view(direction_id)

    @server.tool()
    async def delete_direction(direction_id: DirectionId, confirm: bool = False) -> dict:
        """Delete a direction together with all its questions. Requires confirm=true."""
        view = await direction_view(direction_id)
        if not confirm:
            raise ToolError(f"not deleted: direction '{direction_id}' has {view['questions']} questions — "
                            "call again with confirm=true to delete it with its questions")
        result = await api("DELETE", f"/api/pools/{seg(direction_id)}")
        return {"deleted": direction_id, "questions_deleted": result.get("nodes_removed", view["questions"])}

    # ---------- вертикаль: колонки и под-колонки ----------

    @server.tool()
    async def add_column(direction_id: DirectionId, label: str, color: Optional[str] = None,
                         subcolumns: Optional[List[str]] = None, position: Position = None) -> dict:
        """Add a column (a vertical area of the topic), optionally with subcolumns."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        insert_at(blocks, {"label": label, "color": color or next_color(blocks),
                           "subblocks": [{"label": s} for s in subcolumns or []]}, position)
        updated = await put_structure(direction_id, blocks=blocks)
        cid = new_id(p["blocks"], updated["blocks"])
        column = next(b for b in updated["blocks"] if b["id"] == cid)
        return {"column": _column_out(column), "columns": [b["id"] for b in updated["blocks"]]}

    @server.tool()
    async def update_column(direction_id: DirectionId, column_id: ColumnId, label: Optional[str] = None,
                            color: Optional[str] = None, position: Position = None) -> dict:
        """Rename, recolour or move a column."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        i = lookup(blocks, column_id, "column")
        if label is not None:
            blocks[i]["label"] = label
        if color is not None:
            blocks[i]["color"] = color
        move_to(blocks, i, position)
        updated = await put_structure(direction_id, blocks=blocks)
        column = next(b for b in updated["blocks"] if b["id"] == column_id)
        return {"column": _column_out(column), "columns": [b["id"] for b in updated["blocks"]]}

    @server.tool()
    async def delete_column(direction_id: DirectionId, column_id: ColumnId, confirm: bool = False,
                            move_questions_to: Annotated[Optional[str], Field(description="Move this column's questions to that column first")] = None) -> dict:
        """Delete a column. Its questions are deleted too unless move_questions_to is given; deleting questions
        requires confirm=true."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        i = lookup(blocks, column_id, "column")
        nodes = await questions_of(direction_id, block=column_id, include_hidden=True)
        moved = 0
        if move_questions_to:
            lookup(blocks, move_questions_to, "target column")
            if move_questions_to == column_id:
                raise ToolError("move_questions_to must be another column")
            for n in nodes:
                await api("PUT", f"/api/nodes/{seg(n['id'])}", json={"block": move_questions_to})
                moved += 1
        elif nodes and not confirm:
            visible = sum(1 for n in nodes if not n.get("hidden"))
            raise ToolError(f"not deleted: column '{column_id}' has {visible} questions — pass confirm=true to delete "
                            "them with the column, or move_questions_to=<column_id>")
        blocks.pop(i)
        updated = await put_structure(direction_id, blocks=blocks)
        return {"deleted": column_id, "moved": moved, "questions_deleted": 0 if move_questions_to else len(nodes),
                "columns": [b["id"] for b in updated["blocks"]]}

    @server.tool()
    async def add_subcolumn(direction_id: DirectionId, column_id: ColumnId, label: str, position: Position = None) -> dict:
        """Add a subcolumn inside a column."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        i = lookup(blocks, column_id, "column")
        before = list(blocks[i]["subblocks"])
        insert_at(blocks[i]["subblocks"], {"label": label}, position)
        updated = await put_structure(direction_id, blocks=blocks)
        column = next(b for b in updated["blocks"] if b["id"] == column_id)
        sid = new_id(before, column["subblocks"])
        sub = next(s for s in column["subblocks"] if s["id"] == sid)
        return {"subcolumn": {"id": sub["id"], "label": sub["label"]}, "subcolumns": [s["id"] for s in column["subblocks"]]}

    @server.tool()
    async def update_subcolumn(direction_id: DirectionId, column_id: ColumnId, subcolumn_id: str,
                               label: Optional[str] = None, position: Position = None) -> dict:
        """Rename or move a subcolumn inside its column."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        i = lookup(blocks, column_id, "column")
        subs = blocks[i]["subblocks"]
        j = lookup(subs, subcolumn_id, "subcolumn")
        if label is not None:
            subs[j]["label"] = label
        move_to(subs, j, position)
        updated = await put_structure(direction_id, blocks=blocks)
        column = next(b for b in updated["blocks"] if b["id"] == column_id)
        sub = next(s for s in column["subblocks"] if s["id"] == subcolumn_id)
        return {"subcolumn": {"id": sub["id"], "label": sub["label"]}, "subcolumns": [s["id"] for s in column["subblocks"]]}

    @server.tool()
    async def delete_subcolumn(direction_id: DirectionId, column_id: ColumnId, subcolumn_id: str) -> dict:
        """Delete a subcolumn. Its questions stay in the column without a subcolumn."""
        p = await pool(direction_id)
        blocks = blocks_payload(p)
        i = lookup(blocks, column_id, "column")
        j = lookup(blocks[i]["subblocks"], subcolumn_id, "subcolumn")
        detached = len(await questions_of(direction_id, block=column_id, subblock=subcolumn_id, include_hidden=True))
        blocks[i]["subblocks"].pop(j)
        updated = await put_structure(direction_id, blocks=blocks)
        column = next(b for b in updated["blocks"] if b["id"] == column_id)
        return {"deleted": subcolumn_id, "questions_detached": detached, "subcolumns": [s["id"] for s in column["subblocks"]]}

    # ---------- горизонталь: уровни ----------

    @server.tool()
    async def add_level(direction_id: DirectionId, label: str, position: Position = None) -> dict:
        """Add a level (a horizontal row). Levels go from the easiest (position 0, top) to the hardest; 2–8 levels."""
        p = await pool(direction_id)
        levels = levels_payload(p)
        insert_at(levels, {"label": label}, position)
        updated = await put_structure(direction_id, levels=levels)
        lid = new_id(p["levels"], updated["levels"])
        level = next(lv for lv in updated["levels"] if lv["id"] == lid)
        return {"level": {"id": level["id"], "label": level["label"]}, "levels": [lv["id"] for lv in updated["levels"]]}

    @server.tool()
    async def update_level(direction_id: DirectionId, level_id: LevelId, label: Optional[str] = None,
                           position: Position = None) -> dict:
        """Rename or move a level (0 = top row, the easiest)."""
        p = await pool(direction_id)
        levels = levels_payload(p)
        i = lookup(levels, level_id, "level")
        if label is not None:
            levels[i]["label"] = label
        move_to(levels, i, position)
        updated = await put_structure(direction_id, levels=levels)
        level = next(lv for lv in updated["levels"] if lv["id"] == level_id)
        return {"level": {"id": level["id"], "label": level["label"]}, "levels": [lv["id"] for lv in updated["levels"]]}

    @server.tool()
    async def delete_level(direction_id: DirectionId, level_id: LevelId, confirm: bool = False,
                           move_questions_to: Annotated[Optional[str], Field(description="Move this level's questions to that level first")] = None) -> dict:
        """Delete a level. Its questions are deleted too unless move_questions_to is given; deleting questions
        requires confirm=true. A direction keeps at least 2 levels."""
        p = await pool(direction_id)
        levels = levels_payload(p)
        i = lookup(levels, level_id, "level")
        nodes = await questions_of(direction_id, difficulty=level_id, include_hidden=True)
        moved = 0
        if move_questions_to:
            lookup(levels, move_questions_to, "target level")
            if move_questions_to == level_id:
                raise ToolError("move_questions_to must be another level")
            for n in nodes:
                await api("PUT", f"/api/nodes/{seg(n['id'])}", json={"difficulty": move_questions_to})
                moved += 1
        elif nodes and not confirm:
            visible = sum(1 for n in nodes if not n.get("hidden"))
            raise ToolError(f"not deleted: level '{level_id}' has {visible} questions — pass confirm=true to delete "
                            "them with the level, or move_questions_to=<level_id>")
        levels.pop(i)
        updated = await put_structure(direction_id, levels=levels)
        return {"deleted": level_id, "moved": moved, "questions_deleted": 0 if move_questions_to else len(nodes),
                "levels": [lv["id"] for lv in updated["levels"]]}

    # ---------- топики ----------

    @server.tool()
    async def list_topics(direction_id: DirectionId, column_id: Optional[str] = None) -> dict:
        """List topics (subtopic slugs of cards) with the column they live in and the number of questions."""
        rows = await api("GET", f"/api/pools/{seg(direction_id)}/topics", block=column_id)
        return {"topics": [{"topic": r["topic"], "column": r["block"], "count": r["count"]} for r in rows]}

    @server.tool()
    async def rename_topic(direction_id: DirectionId, topic: str, new_topic: str, column_id: Optional[str] = None) -> dict:
        """Rename a topic on all its questions (optionally only inside one column)."""
        body: Dict[str, Any] = {"topic": new_topic}
        if column_id:
            body["block"] = column_id
        result = await api("PUT", f"/api/pools/{seg(direction_id)}/topics/{seg(topic)}", json=body)
        return {"renamed": result["renamed"], "topic": result["topic"]}

    @server.tool()
    async def delete_topic(direction_id: DirectionId, topic: str, confirm: bool = False, column_id: Optional[str] = None) -> dict:
        """Delete all questions of a topic (optionally only inside one column). Requires confirm=true."""
        rows = await api("GET", f"/api/pools/{seg(direction_id)}/topics", block=column_id)
        count = sum(r["count"] for r in rows if r["topic"] == topic)
        if not count:
            raise ToolError(f"no questions with topic '{topic}' in direction '{direction_id}'")
        if not confirm:
            raise ToolError(f"not deleted: topic '{topic}' has {count} questions — call again with confirm=true")
        result = await api("DELETE", f"/api/pools/{seg(direction_id)}/topics/{seg(topic)}", block=column_id)
        return {"deleted": result["deleted"], "count": result["count"]}

    # ---------- вопросы ----------

    @server.tool()
    async def list_questions(
        direction_id: DirectionId,
        column_id: Optional[str] = None,
        subcolumn_id: Optional[str] = None,
        level_id: Optional[str] = None,
        topic: Optional[str] = None,
        tag: Optional[str] = None,
        kind: Optional[Kind] = None,
        text: Annotated[Optional[str], Field(description="Case-insensitive substring of the title, question or answer")] = None,
        include_hidden: bool = False,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        """List questions of a direction with filters. Returns short items (question text trimmed to 200 chars);
        use get_question for the full card."""
        nodes = await questions_of(direction_id, block=column_id, subblock=subcolumn_id, difficulty=level_id,
                                   topic=topic, tag=tag, kind=kind, q=text, include_hidden=include_hidden or None)
        page = nodes[offset:offset + limit]
        return {"total": len(nodes), "offset": offset, "questions": [_question_brief(n) for n in page]}

    @server.tool()
    async def get_question(question_id: str) -> dict:
        """Get one question card with every field (question, answer, starterCode, rubric, tags, hidden…)."""
        return await api("GET", f"/api/nodes/{seg(question_id)}")

    @server.tool()
    async def create_question(
        direction_id: DirectionId,
        column_id: ColumnId,
        level_id: LevelId,
        question: str,
        answer: str = "",
        title: Annotated[Optional[str], Field(description="Short card title, 3–7 words")] = None,
        topic: Annotated[Optional[str], Field(description="Subtopic slug; omitted — derived from the title")] = None,
        subcolumn_id: Optional[str] = None,
        tags: Annotated[Optional[List[str]], Field(description="1–3 tags, see list_tags")] = None,
        kind: Kind = "question",
        starter_code: Optional[str] = None,
        rubric: Optional[List[str]] = None,
        question_id: Annotated[Optional[str], Field(description="Explicit card id (slug); omitted — generated")] = None,
        weight: int = 1,
    ) -> dict:
        """Create a question card in a cell (column × level) of a direction."""
        spec = QuestionSpec(
            column_id=column_id, level_id=level_id, question=question, answer=answer, title=title, topic=topic,
            subcolumn_id=subcolumn_id, tags=tags or [], kind=kind, starter_code=starter_code, rubric=rubric or [],
            question_id=question_id, weight=weight,
        )
        return await api("POST", "/api/nodes", json=_question_body(direction_id, spec))

    @server.tool()
    async def create_questions(direction_id: DirectionId, questions: List[QuestionSpec]) -> dict:
        """Create many question cards at once. Invalid items are reported in `errors` (by index), the rest are
        created."""
        created: List[str] = []
        errors: List[dict] = []
        for index, spec in enumerate(questions):
            try:
                node = await client.request("POST", "/api/nodes", json=_question_body(direction_id, spec))
            except LadderError as exc:
                errors.append({"index": index, "error": f"{exc.status}: {exc.detail}"})
                continue
            created.append(node["id"])
        return {"created": created, "errors": errors}

    @server.tool()
    async def update_question(
        question_id: str,
        direction_id: Annotated[Optional[str], Field(description="Move the card to another direction")] = None,
        column_id: Annotated[Optional[str], Field(description="Move to another column")] = None,
        subcolumn_id: Annotated[Optional[str], Field(description="Set a subcolumn; '' removes it")] = None,
        level_id: Annotated[Optional[str], Field(description="Move to another level")] = None,
        topic: Optional[str] = None,
        title: Annotated[Optional[str], Field(description="'' removes the title")] = None,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        tags: Optional[List[str]] = None,
        kind: Optional[Kind] = None,
        starter_code: Annotated[Optional[str], Field(description="'' removes the starter code")] = None,
        rubric: Optional[List[str]] = None,
        weight: Optional[int] = None,
    ) -> dict:
        """Edit any field of a question card or move it (direction, column, subcolumn, level). Only the passed
        fields change. Moving to another column drops a subcolumn that does not exist there."""
        mapping = (("pool", direction_id), ("block", column_id), ("subblock", subcolumn_id), ("difficulty", level_id),
                   ("topic", topic), ("title", title), ("question", question), ("answer", answer), ("tags", tags),
                   ("kind", kind), ("starterCode", starter_code), ("rubric", rubric), ("weight", weight))
        body = {key: value for key, value in mapping if value is not None}
        if not body:
            raise ToolError("nothing to update: pass at least one field")
        result = await api("PUT", f"/api/nodes/{seg(question_id)}", json=body)
        return result["node"]

    @server.tool()
    async def delete_question(question_id: str) -> dict:
        """Delete a question card. A card that came from content files is hidden instead (so a sync cannot bring
        it back)."""
        result = await api("DELETE", f"/api/nodes/{seg(question_id)}")
        return {"deleted": result["deleted"], "hidden_instead_of_deleted": result.get("tombstoned", False)}

    # ---------- теги ----------

    @server.tool()
    async def list_tags(direction_id: Optional[str] = None) -> dict:
        """The concept tag vocabulary (use 1–3 per card) and, for a direction, the tags already used there."""
        return await api("GET", "/api/tags", pool=direction_id)

    # ---------- пресеты из файлов (owner) ----------

    @server.tool()
    async def sync_from_files(
        direction_id: Annotated[Optional[str], Field(description="Only this preset direction (content/<id>/); omitted — all presets")] = None,
        update_existing: Annotated[bool, Field(description="false — only add what is missing (safe); true — rewrite the preset's columns/levels and untouched cards from files, hide cards whose files are gone")] = False,
        dry_run: Annotated[bool, Field(description="Report what would change without writing (default true)")] = True,
    ) -> dict:
        """Owner only. Pull preset directions (has_files=true in get_direction) from the server's content/ files.
        By default only adds missing directions and cards and never overwrites; update_existing=true is the
        explicit preset update — run it with dry_run=true first and read `config_changed` / `nodes_changed` /
        `hidden` before applying."""
        return await api("POST", "/api/pools/sync", pool=direction_id, update=update_existing or None, dry_run=dry_run or None)

    return server


def main() -> None:
    # httpx пишет каждый запрос на INFO в stderr — в логах MCP-клиента это шум.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    url = os.environ.get("LADDER_URL", "http://localhost:8000")
    email = os.environ.get("LADDER_EMAIL")
    password = os.environ.get("LADDER_PASSWORD")
    if not email or not password:
        raise SystemExit("set LADDER_EMAIL and LADDER_PASSWORD (and LADDER_URL, default http://localhost:8000)")
    build_server(LadderClient(url, email, password)).run("stdio")
