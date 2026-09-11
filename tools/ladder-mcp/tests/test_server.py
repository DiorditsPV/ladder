"""MCP-сервер Ladder против настоящего API: полный цикл правки направления, структуры, топиков и вопросов."""

import json
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import Client

from app.main import OWNER_EMAIL, OWNER_PASSWORD, app
from ladder_mcp.client import LadderClient
from ladder_mcp.server import TOOL_NAMES, build_server

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def connect(password: str = OWNER_PASSWORD):
    api = LadderClient("http://ladder.test", OWNER_EMAIL, password, transport=httpx.ASGITransport(app=app))
    try:
        async with Client(build_server(api)) as client:
            yield client
    finally:
        await api.aclose()


async def call(client: Client, tool: str, **args):
    res = await client.call_tool(tool, args)
    text = "\n".join(getattr(c, "text", "") for c in res.content)
    if res.is_error:
        raise AssertionError(f"{tool} failed: {text}")
    if res.structured_content is not None:
        body = res.structured_content
        return body.get("result", body) if set(body) == {"result"} else body
    return json.loads(text)


async def fails(client: Client, tool: str, **args) -> str:
    res = await client.call_tool(tool, args)
    text = "\n".join(getattr(c, "text", "") for c in res.content)
    assert res.is_error, f"{tool} should fail, got: {text}"
    return text


async def test_every_tool_is_registered():
    async with connect() as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert names == set(TOOL_NAMES)
    assert len(names) >= 24


async def test_full_authoring_cycle():
    async with connect() as c:
        created = await call(
            c, "create_direction", label="Kafka (MCP)", direction_id="mcp-kafka", description="Тестовое направление",
            columns=[{"label": "Core", "subcolumns": ["Log", "Brokers"]}, {"label": "Clients"}],
            levels=["Basics", "Practice", "Advanced"],
        )
        assert created["id"] == "mcp-kafka"
        assert [col["id"] for col in created["columns"]] == ["core", "clients"]
        assert [s["id"] for s in created["columns"][0]["subcolumns"]] == ["log", "brokers"]
        assert [lv["id"] for lv in created["levels"]] == ["basics", "practice", "advanced"]
        assert created["columns"][0]["color"] != created["columns"][1]["color"]

        # вертикаль: колонки и под-колонки
        ops = await call(c, "add_column", direction_id="mcp-kafka", label="Ops", position=1)
        assert ops["column"]["id"] == "ops" and ops["columns"] == ["core", "ops", "clients"]
        moved = await call(c, "update_column", direction_id="mcp-kafka", column_id="ops", label="Operations", position=2)
        assert moved["columns"] == ["core", "clients", "ops"] and moved["column"]["label"] == "Operations"
        sub = await call(c, "add_subcolumn", direction_id="mcp-kafka", column_id="core", label="Storage", position=0)
        assert sub["subcolumn"]["id"] == "storage" and sub["subcolumns"] == ["storage", "log", "brokers"]
        ren = await call(c, "update_subcolumn", direction_id="mcp-kafka", column_id="core", subcolumn_id="storage",
                         label="Disk storage", position=2)
        assert ren["subcolumns"] == ["log", "brokers", "storage"] and ren["subcolumn"]["label"] == "Disk storage"

        # горизонталь: уровни
        exp = await call(c, "add_level", direction_id="mcp-kafka", label="Expert")
        assert exp["level"]["id"] == "expert" and exp["levels"] == ["basics", "practice", "advanced", "expert"]
        up = await call(c, "update_level", direction_id="mcp-kafka", level_id="expert", label="Эксперт", position=0)
        assert up["levels"][0] == "expert" and up["level"]["label"] == "Эксперт"
        back = await call(c, "update_level", direction_id="mcp-kafka", level_id="expert", position=3)
        assert back["levels"] == ["basics", "practice", "advanced", "expert"]

        # вопросы
        q1 = await call(c, "create_question", direction_id="mcp-kafka", column_id="core", subcolumn_id="log",
                        level_id="basics", title="Топик и партиция", topic="log-basics", tags=["streaming"],
                        question="Что такое топик и партиция?", answer="Топик — именованный лог…")
        assert q1["id"] and q1["subblock"] == "log" and q1["difficulty"] == "basics"
        q2 = await call(c, "create_question", direction_id="mcp-kafka", column_id="core", level_id="practice",
                        question_id="mcp-kafka-core-02", title="Выбор числа партиций", topic="partition-count",
                        question="Как выбрать число партиций топика?", answer="Исходя из пропускной способности…",
                        kind="task", starter_code="kafka-topics --create", rubric=["учёл консьюмеров"])
        assert q2["id"] == "mcp-kafka-core-02" and q2["starterCode"] == "kafka-topics --create"
        batch = await call(c, "create_questions", direction_id="mcp-kafka", questions=[
            {"column_id": "clients", "level_id": "basics", "title": "Что делает продюсер", "topic": "producer",
             "question": "Что делает продюсер?", "answer": "Пишет записи в топик…", "tags": ["streaming"]},
            {"column_id": "clients", "level_id": "advanced", "title": "Идемпотентный продюсер", "topic": "producer",
             "question": "Зачем идемпотентный продюсер?", "answer": "Чтобы ретраи не дублировали записи…"},
            {"column_id": "nope", "level_id": "basics", "question": "Сломанный вопрос?"},
            {"column_id": "ops", "level_id": "expert", "title": "Ребалансировка", "topic": "rebalance",
             "question": "Как пережить ребалансировку?", "answer": "…"},
        ])
        assert len(batch["created"]) == 3 and [e["index"] for e in batch["errors"]] == [2]
        assert "nope" in batch["errors"][0]["error"]

        listed = await call(c, "list_questions", direction_id="mcp-kafka")
        assert listed["total"] == 5
        assert {q["id"] for q in (await call(c, "list_questions", direction_id="mcp-kafka", column_id="clients"))["questions"]} \
            == set(batch["created"][:2])
        found = await call(c, "list_questions", direction_id="mcp-kafka", text="ИДЕМПОТЕНТ")
        assert [q["title"] for q in found["questions"]] == ["Идемпотентный продюсер"]
        assert (await call(c, "list_questions", direction_id="mcp-kafka", level_id="practice"))["total"] == 1
        assert (await call(c, "list_questions", direction_id="mcp-kafka", limit=2, offset=4))["questions"] != []

        full = await call(c, "get_question", question_id="mcp-kafka-core-02")
        assert full["rubric"] == ["учёл консьюмеров"] and full["kind"] == "task"

        upd = await call(c, "update_question", question_id=q1["id"], column_id="clients", level_id="practice",
                         tags=["streaming", "partitioning"], answer="Новый ответ")
        assert (upd["block"], upd["subblock"], upd["difficulty"]) == ("clients", None, "practice")
        assert upd["tags"] == ["streaming", "partitioning"] and upd["answer"] == "Новый ответ"
        back_to_log = await call(c, "update_question", question_id=q1["id"], column_id="core", subcolumn_id="log")
        assert (back_to_log["block"], back_to_log["subblock"]) == ("core", "log")
        assert "nothing to update" in await fails(c, "update_question", question_id=q1["id"])

        # топики
        topics = await call(c, "list_topics", direction_id="mcp-kafka")
        assert {(t["column"], t["topic"]): t["count"] for t in topics["topics"]}[("clients", "producer")] == 2
        renamed = await call(c, "rename_topic", direction_id="mcp-kafka", topic="producer", new_topic="producer-basics")
        assert renamed["renamed"] == 2
        assert "confirm" in await fails(c, "delete_topic", direction_id="mcp-kafka", topic="rebalance")

        # теги и покрытие
        tags = await call(c, "list_tags", direction_id="mcp-kafka")
        assert "streaming" in tags["concepts"] and tags["used"][0]["tag"] == "streaming"
        direction = await call(c, "get_direction", direction_id="mcp-kafka")
        assert direction["questions"] == 5
        assert direction["coverage"]["clients"] == {"basics": 1, "practice": 0, "advanced": 1, "expert": 0}
        assert direction["coverage"]["ops"]["expert"] == 1

        # удаление структуры: без confirm — отказ, с переносом вопросов — вопросы живы
        assert "confirm" in await fails(c, "delete_column", direction_id="mcp-kafka", column_id="ops")
        gone = await call(c, "delete_column", direction_id="mcp-kafka", column_id="ops", move_questions_to="clients")
        assert gone["moved"] == 1 and gone["columns"] == ["core", "clients"]
        assert "confirm" in await fails(c, "delete_level", direction_id="mcp-kafka", level_id="expert")
        lvl = await call(c, "delete_level", direction_id="mcp-kafka", level_id="expert", move_questions_to="advanced")
        assert lvl["moved"] == 1 and lvl["levels"] == ["basics", "practice", "advanced"]
        subgone = await call(c, "delete_subcolumn", direction_id="mcp-kafka", column_id="core", subcolumn_id="log")
        assert subgone["subcolumns"] == ["brokers", "storage"] and subgone["questions_detached"] == 1
        assert (await call(c, "get_question", question_id=q1["id"]))["subblock"] is None
        assert (await call(c, "get_direction", direction_id="mcp-kafka"))["questions"] == 5

        # удаление топика, вопроса, направления
        deleted_topic = await call(c, "delete_topic", direction_id="mcp-kafka", topic="rebalance", confirm=True)
        assert deleted_topic["count"] == 1
        dq = await call(c, "delete_question", question_id="mcp-kafka-core-02")
        assert dq["deleted"] == "mcp-kafka-core-02"
        assert (await call(c, "get_direction", direction_id="mcp-kafka"))["questions"] == 3

        meta = await call(c, "update_direction", direction_id="mcp-kafka", label="Kafka MCP", description="Обновлено")
        assert (meta["label"], meta["description"]) == ("Kafka MCP", "Обновлено")
        assert "confirm" in await fails(c, "delete_direction", direction_id="mcp-kafka")
        await call(c, "delete_direction", direction_id="mcp-kafka", confirm=True)
        ids = {d["id"] for d in (await call(c, "list_directions"))["directions"]}
        assert "mcp-kafka" not in ids


async def test_copy_direction_from_existing():
    async with connect() as c:
        await call(c, "create_direction", label="Source", direction_id="mcp-src",
                   columns=[{"label": "Only"}], levels=["Low", "High"])
        await call(c, "create_question", direction_id="mcp-src", column_id="only", level_id="low",
                   title="Один вопрос", topic="t", question="Вопрос?", answer="Ответ")
        copy = await call(c, "create_direction", label="Copy", direction_id="mcp-copy", copy_from="mcp-src")
        assert copy["questions"] == 1 and [lv["id"] for lv in copy["levels"]] == ["low", "high"]
        for pid in ("mcp-copy", "mcp-src"):
            await call(c, "delete_direction", direction_id=pid, confirm=True)


async def test_api_errors_reach_the_model():
    async with connect() as c:
        text = await fails(c, "get_direction", direction_id="no-such-direction")
        assert "404" in text and "no-such-direction" in text
        text = await fails(c, "create_direction", label="Bad", columns=[])
        assert "column" in text


async def test_sync_from_files_defaults_to_safe_dry_run():
    async with connect() as c:
        rep = await call(c, "sync_from_files")
        assert rep["mode"] == "seed" and rep["dry_run"] is True and rep["hidden"] == []
        upd = await call(c, "sync_from_files", update_existing=True)
        assert upd["mode"] == "update" and upd["dry_run"] is True
        assert "404" in await fails(c, "sync_from_files", direction_id="no-such-preset")


async def test_wrong_password_is_explained():
    async with connect(password="wrong") as c:
        text = await fails(c, "list_directions")
        assert "login failed" in text and "LADDER_PASSWORD" in text
