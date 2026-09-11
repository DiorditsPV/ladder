"""Проверка MCP-сервера по настоящему транспорту: запускает `python -m ladder_mcp` по stdio против живого API
и проходит короткий цикл — список направлений, временное направление, вопрос, правка, удаление.

    LADDER_URL=http://localhost:8000 LADDER_EMAIL=admin LADDER_PASSWORD=admin \
        python tools/ladder-mcp/scripts/stdio_smoke.py

Временное направление `mcp-smoke-<rand>` удаляется в конце; существующие не трогаются.
"""

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

PKG_DIR = Path(__file__).resolve().parents[1]


async def call(client: Client, tool: str, **args):
    res = await client.call_tool(tool, args)
    text = "\n".join(getattr(c, "text", "") for c in res.content)
    if res.is_error:
        raise SystemExit(f"✗ {tool}: {text}")
    body = res.structured_content if res.structured_content is not None else json.loads(text)
    return body


async def main() -> None:
    env = {**os.environ, "PYTHONPATH": str(PKG_DIR)}
    for key in ("LADDER_URL", "LADDER_EMAIL", "LADDER_PASSWORD"):
        if key not in env:
            raise SystemExit(f"set {key}")
    params = StdioServerParameters(command=sys.executable, args=["-m", "ladder_mcp"], env=env)
    pid = f"mcp-smoke-{secrets.token_hex(3)}"
    async with Client(params) as client:
        tools = (await client.list_tools()).tools
        print(f"✓ {len(tools)} tools over stdio")
        directions = (await call(client, "list_directions"))["directions"]
        print(f"✓ list_directions: {', '.join(d['id'] for d in directions) or '—'}")
        await call(client, "create_direction", label=f"MCP smoke {pid}", direction_id=pid,
                   columns=[{"label": "Core", "subcolumns": ["Basics"]}], levels=["Low", "High"])
        try:
            node = await call(client, "create_question", direction_id=pid, column_id="core", subcolumn_id="basics",
                              level_id="low", title="Проверочный вопрос", topic="smoke",
                              question="Что проверяет этот вопрос?", answer="Что MCP работает по stdio.",
                              tags=["quality"])
            await call(client, "update_question", question_id=node["id"], level_id="high")
            view = await call(client, "get_direction", direction_id=pid)
            assert view["coverage"]["core"] == {"low": 0, "high": 1}, view["coverage"]
            print(f"✓ create/update question in {pid}: coverage {view['coverage']}")
        finally:
            await call(client, "delete_direction", direction_id=pid, confirm=True)
            print(f"✓ temporary direction {pid} deleted")


if __name__ == "__main__":
    asyncio.run(main())
