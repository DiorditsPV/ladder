"""Скрипт скилла ladder-topic: JSON темы → content/<pool>/ (валидация, формат, покрытие, дополнение, --fresh)."""

import json
import subprocess
import sys
from pathlib import Path

import frontmatter
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "ladder-topic" / "write_topic.py"


def _spec(cards):
    return {
        "pool": {
            "id": "kafka", "label": "Kafka", "description": "d",
            "blocks": [{"id": "core", "label": "Ядро", "subblocks": [{"id": "log", "label": "Лог"}]},
                       {"id": "ops", "label": "Эксплуатация"}],
            "levels": [{"id": "concepts", "label": "Понятия"}, {"id": "design", "label": "Проектирование"}],
        },
        "cards": cards,
    }


def _card(i, block="ops", level="concepts", **extra):
    c = {"id": f"kafka-{block}-{i:02d}", "block": block, "difficulty": level, "title": f"Тема номер {i}", "topic": "t",
         "tags": ["streaming"], "question": f"Q{i}?", "answer": f"A{i} строка."}
    c.update(extra)
    return c


def _run(tmp_path, spec, *args):
    """Режим файлов (--files) по умолчанию — для пресетов; --check передаётся явно."""
    f = tmp_path / "topic.json"
    f.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    mode = [] if {"--check", "--upload"} & set(args) else ["--files"]
    return subprocess.run([sys.executable, str(SCRIPT), str(f), *mode, "--content", str(tmp_path / "content"), *args],
                          capture_output=True, text=True)


def _module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("write_topic", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _owner_client():
    from fastapi.testclient import TestClient

    from app.main import OWNER_EMAIL, OWNER_PASSWORD, app

    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}).status_code == 200
    return c


def _answer(i):
    return f"Ответ {i}: " + "механика и пример. " * 30


def test_upload_creates_direction_then_skips_and_overwrites():
    """--upload (spec content-in-db): направление с id из JSON, карточки с явными id; повтор — пропуск; --overwrite —
    обновление; ничего не пишется в content/."""
    import uuid

    wt = _module()
    pid = f"wt-{uuid.uuid4().hex[:6]}"
    spec = _spec([_card(1, block="core", subblock="log"), _card(2, level="design")])
    spec["pool"]["id"] = pid
    for c in spec["cards"]:
        c["id"] = c["id"].replace("kafka", pid)
        c["answer"] = _answer(c["id"])
    http = _owner_client()
    try:
        rep = wt.upload(spec, http)
        assert rep["pool_created"] and rep["created"] == 2 and rep["errors"] == []
        pool = http.get(f"/api/pools/{pid}").json()
        assert [b["id"] for b in pool["blocks"]] == ["core", "ops"] and pool["blocks"][0]["subblocks"][0]["id"] == "log"
        assert [lv["id"] for lv in pool["levels"]] == ["concepts", "design"]
        node = http.get(f"/api/nodes/{pid}-core-01").json()
        assert node["subblock"] == "log" and node["tags"] == ["streaming"]

        again = wt.upload(spec, http)
        assert not again["pool_created"] and again["skipped"] == 2 and again["created"] == 0

        spec["cards"][0]["title"] = "Новый заголовок карточки"
        over = wt.upload(spec, http, overwrite=True)
        assert over["updated"] == 2
        assert http.get(f"/api/nodes/{pid}-core-01").json()["title"] == "Новый заголовок карточки"
    finally:
        http.delete(f"/api/pools/{pid}")


def test_upload_extends_structure_of_existing_direction():
    import uuid

    wt = _module()
    pid = f"wt-{uuid.uuid4().hex[:6]}"
    spec = _spec([_card(1)])
    spec["pool"]["id"] = pid
    spec["cards"][0]["id"] = f"{pid}-ops-01"
    http = _owner_client()
    try:
        wt.upload(spec, http)
        spec["pool"]["blocks"].append({"id": "streams", "label": "Потоки"})
        spec["pool"]["blocks"][0]["subblocks"].append({"id": "segments", "label": "Сегменты"})
        spec["pool"]["levels"].insert(1, {"id": "config", "label": "Настройка"})
        spec["cards"].append({**_card(1, block="streams", level="config"), "id": f"{pid}-streams-01"})
        rep = wt.upload(spec, http)
        assert set(rep["structure_added"]) == {"колонка streams", "под-колонка core/segments", "уровень config"}
        assert rep["created"] == 1 and rep["skipped"] == 1
        pool = http.get(f"/api/pools/{pid}").json()
        assert [b["id"] for b in pool["blocks"]] == ["core", "ops", "streams"]
        assert [lv["id"] for lv in pool["levels"]] == ["concepts", "config", "design"]
    finally:
        http.delete(f"/api/pools/{pid}")


def test_mode_is_required(tmp_path):
    f = tmp_path / "topic.json"
    f.write_text(json.dumps(_spec([_card(1)]), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
    assert r.returncode == 2 and "--check" in r.stderr


def test_writes_normalized_files_and_pool_yaml(tmp_path):
    cards = [_card(1, "core", "concepts", subblock="log"), _card(2, "core", "design", subblock="log"),
             _card(3, "ops", "concepts"), _card(4, "ops", "design")]
    r = _run(tmp_path, _spec(cards), "--per-cell", "1")
    assert r.returncode == 0, r.stderr + r.stdout
    pool = yaml.safe_load((tmp_path / "content/kafka/pool.yaml").read_text(encoding="utf-8"))
    assert [l["id"] for l in pool["levels"]] == ["concepts", "design"]
    assert pool["blocks"][0]["subblocks"] == [{"id": "log", "label": "Лог"}] and "subblocks" not in pool["blocks"][1]
    assert pool["blocks"][0]["weight"] == 50 and pool["blocks"][1]["weight"] == 50
    md = (tmp_path / "content/kafka/core/kafka-core-01.md").read_text(encoding="utf-8")
    assert md.startswith("---\nblock: core\ndifficulty: concepts\nid: kafka-core-01\nkind: question\nsubblock: log\ntags:\n- streaming\n")
    post = frontmatter.load(str(tmp_path / "content/kafka/core/kafka-core-01.md"))
    assert "## Вопрос" in post.content and "## Ответ" in post.content
    assert "ячеек тоньше 1: 0" in r.stdout


def test_pool_tags_extend_vocabulary_and_check_mode(tmp_path):
    spec = _spec([_card(1, tags=["elicitation"])])
    r = _run(tmp_path, spec, "--per-cell", "0")
    assert r.returncode == 1 and "pool.tags" in r.stderr
    spec["pool"]["tags"] = ["elicitation"]
    r = _run(tmp_path, spec, "--per-cell", "0", "--check")
    assert r.returncode == 0 and not (tmp_path / "content").exists()  # --check ничего не пишет
    assert "ответ" in r.stdout and "знаков" in r.stdout  # короткий ответ → предупреждение
    r = _run(tmp_path, spec, "--per-cell", "0")
    assert r.returncode == 0
    assert yaml.safe_load((tmp_path / "content/kafka/pool.yaml").read_text(encoding="utf-8"))["tags"] == ["elicitation"]


def test_thin_cells_exit_2(tmp_path):
    r = _run(tmp_path, _spec([_card(1)]), "--per-cell", "2")
    assert r.returncode == 2 and "ячеек тоньше 2: 4" in r.stdout


def test_rejects_bad_tag_level_prefix_and_subblock(tmp_path):
    for bad, msg in [
        (_card(1, tags=["kafka"]), "tags"),
        (_card(1, level="senior"), "difficulty"),
        ({**_card(1), "id": "kafka-core-01"}, "<block>-NN"),  # блок в id не совпадает с block=ops
        (_card(1, "core", "concepts"), "subblock"),  # у core есть под-колонки — нужен subblock
    ]:
        r = _run(tmp_path, _spec([bad]), "--per-cell", "1")
        assert r.returncode == 1 and msg in r.stderr, (bad, r.stderr)


def test_append_keeps_existing_and_fresh_wipes(tmp_path):
    assert _run(tmp_path, _spec([_card(1)]), "--per-cell", "0").returncode == 0
    (tmp_path / "content/kafka/ops/kafka-ops-01.md").write_text("---\nblock: ops\ndifficulty: concepts\nid: kafka-ops-01\nkind: question\ntags:\n- streaming\ntitle: РУЧНАЯ\ntopic: t\nweight: 1\n---\n\n## Вопрос\nx\n\n## Ответ\ny\n", encoding="utf-8")
    r = _run(tmp_path, _spec([_card(1), _card(2)]), "--per-cell", "0")
    assert r.returncode == 0 and "пропущено (id занят) 1" in r.stdout
    assert "РУЧНАЯ" in (tmp_path / "content/kafka/ops/kafka-ops-01.md").read_text(encoding="utf-8")
    assert (tmp_path / "content/kafka/ops/kafka-ops-02.md").exists()
    r = _run(tmp_path, _spec([_card(3)]), "--per-cell", "0", "--fresh")
    assert r.returncode == 0
    assert not (tmp_path / "content/kafka/ops/kafka-ops-01.md").exists() and (tmp_path / "content/kafka/ops/kafka-ops-03.md").exists()
