"""MCP-тесты гоняют настоящий FastAPI-бэкенд в процессе (httpx.ASGITransport) на свежей БД и пустом content/.

Окружение выставляется до импорта app.main: приложение читает его при импорте (БД, owner, sync content/).
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]  # tests → ladder-mcp → tools → корень репозитория
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tools" / "ladder-mcp"))

_TMP = Path(tempfile.mkdtemp(prefix="ladder-mcp-tests-"))
(_TMP / "content").mkdir()
os.environ["INTERVIEW_DB_PATH"] = str(_TMP / "t.db")
os.environ["INTERVIEW_CONTENT_DIR"] = str(_TMP / "content")
os.environ["INTERVIEW_OWNER_PASSWORD"] = "interview-dev"


@pytest.fixture
def anyio_backend():
    return "asyncio"
