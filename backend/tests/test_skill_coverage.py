"""Матрица помощника учитывает таксономию, а не предполагает четыре уровня."""

import importlib.util
import io
import json
from pathlib import Path


def test_custom_levels_and_empty_declared_subblocks(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[2] / ".claude/skills/interview-balance/coverage.py"
    spec = importlib.util.spec_from_file_location("ladder_coverage", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pool = {
        "id": module.POOL,
        "levels": [{"id": "concepts"}, {"id": "design"}],
        "blocks": [{"id": "core", "weight": 100, "subblocks": [
            {"id": "log"}, {"id": "replication"}]}],
    }
    graph = {"nodes": [{"block": "core", "subblock": "log", "difficulty": "concepts"}]}

    def open_json(url):
        return io.BytesIO(json.dumps([pool] if url.endswith("/pools") else graph).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", open_json)
    module.main()
    output = capsys.readouterr().out
    assert "concepts" in output and "design" in output
    assert "replicatio" in output  # пустая объявленная под-колонка тоже входит в матрицу
    assert "нет вопроса уровня base" not in output
    assert "нет вопроса уровня senior" not in output
    assert "Пробелы (" not in output  # нулевое количество ещё не означает содержательный пробел
