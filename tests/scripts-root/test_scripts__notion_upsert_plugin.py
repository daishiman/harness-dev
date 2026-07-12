"""Genuine functional tests for scripts/notion-upsert-plugin.py.

Pure functions (frontmatter parse / plugin scan / property + page-block
builders / label mapper / feedback-protocol loader) are exercised with real
inputs and asserted against real outputs. The CLI main() is driven via
subprocess only on the network-free paths (--dry-run / arg errors); all Notion
HTTP and Keychain access is avoided (curl()/find_existing()/main publish branch
are never invoked) so no external I/O happens.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "notion-upsert-plugin.py"


def _load():
    spec = importlib.util.spec_from_file_location("notion_upsert_plugin", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ── _kind_label ──────────────────────────────────────────────────────────
def test_kind_label_known_values():
    assert mod._kind_label("run") == "実行系(コマンド)"
    assert mod._kind_label("ref") == "参照系(資料)"
    assert mod._kind_label("assign") == "評価系"
    assert mod._kind_label("wrap") == "ラップ系(既存に追加)"
    assert mod._kind_label("delegate") == "委譲系(外部実行)"


def test_kind_label_unknown_falls_back_to_input():
    assert mod._kind_label("totally-new") == "totally-new"


def test_kind_label_empty_uses_default_label():
    assert mod._kind_label("") == "未設定"


# ── _parse_frontmatter ───────────────────────────────────────────────────
def test_parse_frontmatter_block_triggers_and_purpose(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "description: My test skill\n"
        "argument-hint: <arg>\n"
        "kind: run\n"
        "version: 1.2.3  # trailing comment\n"
        "triggers:\n"
        "  - first trigger\n"
        "  - second trigger\n"
        "---\n"
        "## Purpose\n"
        "This is the purpose paragraph.\n"
        "\n"
        "Ignored later body.\n",
        encoding="utf-8",
    )
    fm = mod._parse_frontmatter(skill)
    assert fm["description"] == "My test skill"
    assert fm["argument_hint"] == "<arg>"
    assert fm["kind"] == "run"
    # version must strip the trailing "# comment"
    assert fm["version"] == "1.2.3"
    assert fm["triggers"] == ["first trigger", "second trigger"]
    assert fm["purpose"] == "This is the purpose paragraph."


def test_parse_frontmatter_inline_bracket_list_on_next_line(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\ndescription: x\ntriggers:\n  [a, b, c]\n---\nbody\n",
        encoding="utf-8",
    )
    assert mod._parse_frontmatter(skill)["triggers"] == ["a", "b", "c"]


def test_parse_frontmatter_quoted_scalar_triggers(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\ndescription: x\ntriggers:\n  'solo one'\n  'solo two'\n---\nbody\n",
        encoding="utf-8",
    )
    assert mod._parse_frontmatter(skill)["triggers"] == ["solo one", "solo two"]


def test_parse_frontmatter_triggers_terminated_by_next_key(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\ndescription: x\ntriggers:\n  - aa\nkind: run\n---\nbody\n",
        encoding="utf-8",
    )
    fm = mod._parse_frontmatter(skill)
    assert fm["triggers"] == ["aa"]
    assert fm["kind"] == "run"


def test_parse_frontmatter_missing_file_returns_empty_template():
    fm = mod._parse_frontmatter(Path("/no/such/SKILL.md"))
    assert fm == {
        "description": "",
        "triggers": [],
        "argument_hint": "",
        "kind": "",
        "version": "",
        "purpose": "",
    }


def test_parse_frontmatter_without_frontmatter_returns_empty(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("no frontmatter here\nplain body\n", encoding="utf-8")
    fm = mod._parse_frontmatter(skill)
    assert fm["description"] == ""
    assert fm["triggers"] == []


# ── scan_plugin ──────────────────────────────────────────────────────────
def test_scan_plugin_reads_version_desc_and_skills(tmp_path):
    plugin = tmp_path / "myplugin"
    (plugin / "skills" / "run-a").mkdir(parents=True)
    (plugin / "skills" / "run-a" / "SKILL.md").write_text(
        "---\ndescription: A skill\nkind: run\n---\n## Purpose\nPurp A\n",
        encoding="utf-8",
    )
    (plugin / ".claude-plugin").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "9.9", "description": "plug desc"}), encoding="utf-8"
    )
    info = mod.scan_plugin(plugin)
    assert info["version"] == "9.9"
    assert info["plugin_desc"] == "plug desc"
    assert info["install_cmd"] == "/plugin install myplugin"
    assert [s["name"] for s in info["skills"]] == ["run-a"]
    assert info["skills"][0]["desc"] == "A skill"
    assert info["skills"][0]["purpose"] == "Purp A"


def test_scan_plugin_no_plugin_json_keeps_empty_version(tmp_path):
    plugin = tmp_path / "bare"
    (plugin / "skills").mkdir(parents=True)
    info = mod.scan_plugin(plugin)
    assert info["version"] == ""
    assert info["plugin_desc"] == ""
    assert info["skills"] == []


def test_scan_plugin_distributable_false_uses_clone_only_instruction(tmp_path):
    plugin = tmp_path / "internal"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({
            "version": "1.0",
            "description": "internal plugin",
            "distributable": False,
        }),
        encoding="utf-8",
    )
    info = mod.scan_plugin(plugin)
    assert info["distributable"] is False
    assert info["install_cmd"] == "非配布: repo clone 環境で make sync を実行して利用"


def test_scan_plugin_ignores_non_directory_entries(tmp_path):
    plugin = tmp_path / "p"
    (plugin / "skills").mkdir(parents=True)
    (plugin / "skills" / "loose-file.txt").write_text("noise", encoding="utf-8")
    (plugin / "skills" / "run-b").mkdir()
    (plugin / "skills" / "run-b" / "SKILL.md").write_text(
        "---\ndescription: B\nkind: run\n---\nbody\n", encoding="utf-8"
    )
    info = mod.scan_plugin(plugin)
    assert [s["name"] for s in info["skills"]] == ["run-b"]


# ── build_properties ─────────────────────────────────────────────────────
def test_build_properties_shape_and_counts():
    info = {
        "version": "2.0",
        "skills": [{"name": "a"}, {"name": "b"}],
        "install_cmd": "/plugin install foo",
    }
    props = mod.build_properties("foo", info)
    assert props["プラグイン名"]["title"][0]["text"]["content"] == "foo"
    assert props["バージョン"]["rich_text"][0]["text"]["content"] == "2.0"
    assert props["概要"]["rich_text"][0]["text"]["content"] == "2 skill(s)"
    assert props["インストールコマンド"]["rich_text"][0]["text"]["content"] == "/plugin install foo"
    assert props["リポジトリパス"]["url"] == "plugins/foo"
    # without hearing sheet id there is no relation property
    assert "紐づくヒアリングシート" not in props


def test_build_properties_with_hearing_sheet_adds_relation():
    info = {"version": "1.0", "skills": [], "install_cmd": "/plugin install foo"}
    props = mod.build_properties("foo", info, "page-123")
    assert props["紐づくヒアリングシート"]["relation"][0]["id"] == "page-123"


# ── _load_feedback_protocol ──────────────────────────────────────────────
def test_load_feedback_protocol_returns_contract_fields():
    fb = mod._load_feedback_protocol()
    for key in (
        "callout_summary",
        "command",
        "firing_conditions",
        "intake_fields",
        "promise_to_reporter",
        "status_lifecycle",
    ):
        assert key in fb, f"feedback_protocol missing {key}"
    assert isinstance(fb["firing_conditions"], list)
    assert isinstance(fb["intake_fields"], list)


# ── build_page_children ──────────────────────────────────────────────────
def test_build_page_children_structure():
    info = {
        "version": "1.0",
        "plugin_desc": "desc",
        "distributable": True,
        "install_cmd": "/plugin install foo",
        "skills": [
            {
                "name": "run-x",
                "desc": "does x",
                "triggers": ["t1", "t2"],
                "argument_hint": "<a>",
                "kind": "run",
                "purpose": "purpose x",
            }
        ],
    }
    blocks = mod.build_page_children("foo", info)
    assert blocks, "expected non-empty block list"
    # First block is the overview callout.
    assert blocks[0]["type"] == "callout"
    types = {b["type"] for b in blocks}
    # Section headings, install code block and per-skill toggle are present.
    assert "heading_2" in types
    assert "code" in types
    assert "toggle" in types
    # The install command appears verbatim in some code block rich text.
    code_texts = [
        rt["text"]["content"]
        for b in blocks
        if b["type"] == "code"
        for rt in b["code"]["rich_text"]
    ]
    assert "/plugin install foo" in code_texts
    # A toggle exists describing the run-x skill.
    toggle_titles = [
        rt["text"]["content"]
        for b in blocks
        if b["type"] == "toggle"
        for rt in b["toggle"]["rich_text"]
    ]
    assert any("run-x" in t for t in toggle_titles)


def test_build_page_children_handles_empty_skill_list():
    info = {
        "version": "",
        "plugin_desc": "",
        "distributable": True,
        "install_cmd": "/plugin install empty",
        "skills": [],
    }
    blocks = mod.build_page_children("empty", info)
    assert blocks[0]["type"] == "callout"
    # No toggle blocks when there are no skills.
    assert all(b["type"] != "toggle" for b in blocks)


# ── CLI (subprocess, network-free paths only) ────────────────────────────
def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_cli_dry_run_emits_json_without_network():
    proc = _run("--plugin", "harness-creator", "--dry-run")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["plugin"] == "harness-creator"
    assert "プラグイン名" in payload["properties_keys"]
    assert payload["children_count"] > 0
    assert isinstance(payload["info"]["skills"], list)


def test_cli_missing_plugin_dir_exits_2():
    proc = _run("--plugin", "__definitely_not_a_plugin__", "--dry-run")
    assert proc.returncode == 2
    assert "plugin dir not found" in proc.stdout


def test_cli_requires_plugin_arg():
    proc = _run()
    assert proc.returncode == 2
    assert "--plugin" in proc.stderr
