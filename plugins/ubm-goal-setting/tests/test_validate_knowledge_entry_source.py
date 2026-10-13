"""validate-knowledge-entry-source.py の決定論ゲート挙動テスト。

source が file と type を持つ単一の object で、type が schema.json の enum に入ることを検査し、
外れたら止まること (rc=1) を確かめる。あわせて、検知のラベル (detect-knowledge-updates.py) と
エントリのテンプレート (agent-knowledge-extractor-entry-format.md) が schema.json の enum とずれていないことを固定する。
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "skills/run-ubm-knowledge-sync/scripts"
VALIDATE = SCRIPTS / "validate-knowledge-entry-source.py"
DETECT = SCRIPTS / "detect-knowledge-updates.py"
KNOWLEDGE = PLUGIN_ROOT / "knowledge"
ENTRY_FORMAT = PLUGIN_ROOT / "references/agent-knowledge-extractor-entry-format.md"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATE), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def schema() -> dict:
    return json.loads((KNOWLEDGE / "schema.json").read_text(encoding="utf-8"))


def entry_type_enum() -> set[str]:
    source = schema()["knowledge_entry_schema"]["properties"]["entries"]["items"]["properties"]["source"]
    return set(source["properties"]["type"]["enum"])


MISSING = object()


def make_dir(tmp_path: Path, source: object) -> Path:
    """同梱の schema.json と、エントリ1件のカテゴリファイルを持つ knowledge_dir を作る (MISSING なら source を置かない)。"""
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    shutil.copy(KNOWLEDGE / "schema.json", kdir / "schema.json")
    (kdir / "router.json").write_text(json.dumps({"categories": {}}), encoding="utf-8")
    entry = {"id": "principles-test-001", "title": "t"}
    if source is not MISSING:
        entry["source"] = source
    (kdir / "principles-test.json").write_text(json.dumps({"entries": [entry]}, ensure_ascii=False), encoding="utf-8")
    return kdir


def test_bundled_knowledge_passes():
    r = run("--knowledge-dir", str(KNOWLEDGE))
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_valid_entry_passes(tmp_path: Path):
    kdir = make_dir(tmp_path, {"file": "YouTube/2025-05-25 - a.md", "type": "youtube"})
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stderr
    assert "1 エントリ" in r.stdout


def test_type_outside_enum_stops(tmp_path: Path):
    # 旧テンプレートの略称 (monthly-fb) は enum に無いので止まる
    kdir = make_dir(tmp_path, {"file": "月報フィードバック/a.md", "type": "monthly-fb"})
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "principles-test.json#entries[id=principles-test-001].source.type" in r.stderr
    assert "'monthly-fb'" in r.stderr


def test_source_list_stops(tmp_path: Path):
    # source は単一の object。重複時に配列へ追記した形は止まる
    kdir = make_dir(tmp_path, [{"file": "a.md", "type": "youtube"}, {"file": "b.md", "type": "camp"}])
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "単一の object でない (list)" in r.stderr


def test_missing_source_stops(tmp_path: Path):
    kdir = make_dir(tmp_path, MISSING)
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "principles-test.json#entries[id=principles-test-001]: source が無い" in r.stderr
    assert "NoneType" not in r.stderr


def test_missing_file_stops(tmp_path: Path):
    kdir = make_dir(tmp_path, {"type": "camp"})
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "source.file: 必須なのに無い" in r.stderr


def test_blank_file_stops(tmp_path: Path):
    kdir = make_dir(tmp_path, {"file": "  ", "type": "camp"})
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "source.file: 空でない文字列でない" in r.stderr


def test_broken_category_json_stops_with_file_name(tmp_path: Path):
    kdir = make_dir(tmp_path, {"file": "a.md", "type": "camp"})
    (kdir / "mindset-broken.json").write_text("{", encoding="utf-8")
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "mindset-broken.json" in r.stderr


def test_unreadable_file_is_counted_apart_from_violations(tmp_path: Path):
    # 読めないファイルは契約の外れと別の見出しで数える。外れが無ければ外れの見出しは出さない
    kdir = make_dir(tmp_path, {"file": "a.md", "type": "camp"})
    (kdir / "mindset-broken.json").write_text("{", encoding="utf-8")
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "NG: 読めないファイルが 1 件ある" in r.stderr
    assert "source の契約から外れた箇所" not in r.stderr

    (kdir / "principles-test.json").write_text(json.dumps(
        {"entries": [{"id": "principles-test-001", "source": {"file": "a.md", "type": "monthly-fb"}}]}), encoding="utf-8")
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "NG: 読めないファイルが 1 件ある" in r.stderr
    assert "NG: source の契約から外れた箇所が 1 件ある" in r.stderr


def test_no_category_file_stops(tmp_path: Path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    shutil.copy(KNOWLEDGE / "schema.json", kdir / "schema.json")
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "1つも無い" in r.stderr


def test_missing_schema_stops(tmp_path: Path):
    kdir = make_dir(tmp_path, {"file": "a.md", "type": "camp"})
    (kdir / "schema.json").unlink()
    r = run("--knowledge-dir", str(kdir))
    assert r.returncode == 1
    assert "schema.json" in r.stderr


def test_usage_errors():
    assert run().returncode == 2
    assert run("--knowledge-dir", "/nonexistent/knowledge").returncode == 2
    assert run("--help").returncode == 0


@pytest.mark.parametrize(
    ("value", "cwd", "reason"),
    [
        ("", KNOWLEDGE, "空文字"),
        ("  ", KNOWLEDGE, "空文字"),
        ("knowledge", PLUGIN_ROOT, "絶対パス"),
        (".", KNOWLEDGE, "絶対パス"),
    ],
    ids=["empty", "blank", "relative", "dot"],
)
def test_empty_or_relative_dir_is_usage_error(value: str, cwd: Path, reason: str):
    # KNOWLEDGE_DIR が未設定だと "" が渡る。cwd で解決すると一時コピーでなく同梱の knowledge/ を検査して通ってしまう
    r = run("--knowledge-dir", value, cwd=cwd)
    assert r.returncode == 2, r.stdout
    assert reason in r.stderr
    assert "OK" not in r.stdout


def test_detect_labels_match_schema_enums():
    # 検知のラベルは knowledge-extractor が source.type へそのまま書く値。entry の enum に入り、registry の enum と一致する
    spec = importlib.util.spec_from_file_location("detect_knowledge_updates", DETECT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    labels = {label for _, label in module.SOURCE_TYPE_RULES} | {"other"}
    registry_enum = set(schema()["registry_entry_schema"]["properties"]["source_type"]["enum"])
    assert labels <= entry_type_enum()
    assert labels == registry_enum


def test_entry_format_template_types_in_enum():
    # テンプレートの "type": の行に並ぶ値は enum の中にあり、検知のラベルを1つも落とさない
    text = ENTRY_FORMAT.read_text(encoding="utf-8")
    values: set[str] = set()
    for line in re.findall(r'^\s*"type":\s*"([^"]*)"', text, flags=re.MULTILINE):
        values |= {v.strip() for v in line.strip("{}").split("/") if v.strip()}
    assert values, "テンプレートに source.type の行が無い"
    assert values <= entry_type_enum(), values - entry_type_enum()
    assert {"youtube", "camp", "teaching-material", "monthly-feedback", "seminar", "event", "other"} <= values
