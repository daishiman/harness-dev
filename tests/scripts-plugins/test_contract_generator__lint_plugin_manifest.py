"""Genuine functional tests for
plugins/contract-generator/scripts/lint-plugin-manifest.py.

このスクリプトは plugin.json 宣言と実体ディレクトリ (skills/agents/hooks) の整合を
機械検査する純粋な静的 lint。network / Notion / keychain は一切叩かない。

スクリプトを実ファイルパスから importlib でロードし、

- load_json: 正常 JSON のパース
- parse_frontmatter: frontmatter 無し / key:value / list ([] inline / "  - " 継続) /
  空値 (None) / 空配列 ([]) / クォート除去
- lint: plugin.json 不在 / description 超過 WARN / skill path 欠落 /
  SKILL.md 欠落 / rubric_refs 空・欠落・充足 / agent file 欠落 /
  agent の未知 skill 参照 / hook command target 欠落・存在 / 全 PASS
- main: 全 PASS で exit 0 / FAIL ありで exit 2 / WARN のみで exit 0

を tmp_path 配下の合格 fixture と各違反 fixture で実入力 assert + main を
subprocess(sys.executable) と in-process(monkeypatch sys.argv) の両経路で確認。
全 fixture は tmp_path 配下なので repo を汚さない。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "contract-generator" / "scripts" / "lint-plugin-manifest.py"

_SPEC = importlib.util.spec_from_file_location("lint_plugin_manifest_s3", SCRIPT)
LPM = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LPM)


# ===================== fixture helpers =====================

def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _skill_md(name: str, rubric_refs="present") -> str:
    """SKILL.md frontmatter を生成。rubric_refs はテスト用に可変。"""
    lines = ["---", f"name: {name}", "description: A demo skill"]
    if rubric_refs == "present":
        lines += ["rubric_refs:", "  - rubric/quality.md", "  - rubric/safety.md"]
    elif rubric_refs == "inline":
        lines += ["rubric_refs: [rubric/quality.md]"]
    elif rubric_refs == "empty_list":
        lines += ["rubric_refs: []"]
    elif rubric_refs == "empty_value":
        lines += ["rubric_refs:"]
    elif rubric_refs == "missing":
        pass
    lines += ["---", "", "# Body", "content"]
    return "\n".join(lines) + "\n"


def _good_tree(root: Path) -> dict:
    """lint が違反ゼロになる最小 plugin ツリーを作り manifest dict を返す。"""
    # skill
    _write(root / "skills" / "demo-skill" / "SKILL.md", _skill_md("demo-skill"))
    # agent (skill にリンク)
    _write(root / "agents" / "demo-agent.md", "# demo agent\n")
    # hook target
    _write(root / "hooks" / "guard.py", "print('hook')\n")
    manifest = {
        "name": "contract-generator",
        "description": "Short desc",
        "skills": [{"name": "demo-skill", "path": "skills/demo-skill"}],
        "agents": [{"name": "demo-agent", "path": "agents/demo-agent.md",
                    "skill": "demo-skill"}],
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py"}]}
            ]
        },
    }
    _write(root / ".claude-plugin" / "plugin.json",
           json.dumps(manifest, ensure_ascii=False))
    return manifest


def _write_manifest(root: Path, manifest: dict) -> None:
    _write(root / ".claude-plugin" / "plugin.json",
           json.dumps(manifest, ensure_ascii=False))


# ===================== load_json =====================

def test_load_json_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    _write(p, json.dumps({"a": 1, "b": ["x"]}, ensure_ascii=False))
    assert LPM.load_json(p) == {"a": 1, "b": ["x"]}


# ===================== parse_frontmatter =====================

def test_parse_frontmatter_no_frontmatter(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "# just a body\nno frontmatter here\n")
    assert LPM.parse_frontmatter(p) == {}


def test_parse_frontmatter_scalar_and_quotes(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, '---\nname: foo\ndescription: "quoted val"\n---\nbody\n')
    fm = LPM.parse_frontmatter(p)
    assert fm["name"] == "foo"
    assert fm["description"] == "quoted val"


def test_parse_frontmatter_list_continuation(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs:\n  - rubric/a.md\n  - rubric/b.md\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["rubric_refs"] == ["rubric/a.md", "rubric/b.md"]


def test_parse_frontmatter_inline_list(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs: [rubric/a.md, rubric/b.md]\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["rubric_refs"] == ["rubric/a.md", "rubric/b.md"]


def test_parse_frontmatter_empty_inline_list(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs: []\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["rubric_refs"] == []


def test_parse_frontmatter_empty_value_is_none(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs:\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["rubric_refs"] is None


def test_parse_frontmatter_blank_lines_skipped(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nname: foo\n\ndescription: bar\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm == {"name": "foo", "description": "bar"}


def test_parse_frontmatter_dash_without_key_ignored(tmp_path):
    # current_key が None のまま "- " が来る → list 継続にならない (key 探索 fall-through)
    p = tmp_path / "SKILL.md"
    _write(p, "---\n- orphan\nname: foo\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm == {"name": "foo"}


# ===================== lint =====================

def test_lint_good_tree_no_violations(tmp_path):
    _good_tree(tmp_path)
    assert LPM.lint(tmp_path) == []


def test_lint_manifest_not_found(tmp_path):
    out = LPM.lint(tmp_path)
    assert len(out) == 1
    assert out[0].startswith("FAIL: plugin.json not found")


def test_lint_description_over_limit_is_warn(tmp_path):
    m = _good_tree(tmp_path)
    m["description"] = "x" * (LPM.DESC_LIMIT + 5)
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any(x.startswith("WARN: description") for x in v)
    assert f"exceeds {LPM.DESC_LIMIT}" in v[0]


def test_lint_skill_path_missing(tmp_path):
    m = _good_tree(tmp_path)
    m["skills"][0]["path"] = "skills/ghost"
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("skill path missing" in x for x in v)


def test_lint_skill_md_missing(tmp_path):
    m = _good_tree(tmp_path)
    # ディレクトリは作るが SKILL.md を消す
    (tmp_path / "skills" / "demo-skill" / "SKILL.md").unlink()
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("SKILL.md missing" in x for x in v)


def test_lint_rubric_refs_empty_list(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="empty_list"))
    v = LPM.lint(tmp_path)
    assert any("rubric_refs empty/missing" in x for x in v)


def test_lint_rubric_refs_missing(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="missing"))
    v = LPM.lint(tmp_path)
    assert any("rubric_refs empty/missing" in x for x in v)


def test_lint_rubric_refs_empty_value(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="empty_value"))
    v = LPM.lint(tmp_path)
    assert any("rubric_refs empty/missing" in x for x in v)


def test_lint_rubric_refs_inline_ok(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="inline"))
    assert LPM.lint(tmp_path) == []


def test_lint_agent_file_missing(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "agents" / "demo-agent.md").unlink()
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("agent file missing" in x for x in v)


def test_lint_agent_unknown_skill_reference(tmp_path):
    m = _good_tree(tmp_path)
    m["agents"][0]["skill"] = "does-not-exist"
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("references unknown skill 'does-not-exist'" in x for x in v)


def test_lint_agent_without_skill_link_ok(tmp_path):
    m = _good_tree(tmp_path)
    del m["agents"][0]["skill"]
    _write_manifest(tmp_path, m)
    assert LPM.lint(tmp_path) == []


def test_lint_hook_command_target_missing(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "hooks" / "guard.py").unlink()
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("hook command target missing" in x and "event=PreToolUse" in x
               for x in v)


def test_lint_hook_command_without_plugin_root_ignored(tmp_path):
    # $CLAUDE_PLUGIN_ROOT を含まない command は対象外 (m is None → skip)
    m = _good_tree(tmp_path)
    m["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "echo hello"
    _write_manifest(tmp_path, m)
    assert LPM.lint(tmp_path) == []


def test_lint_no_optional_sections(tmp_path):
    # skills/agents/hooks が全く宣言されていなくても落ちない (空デフォルト)
    _write_manifest(tmp_path, {"name": "p", "description": "d"})
    assert LPM.lint(tmp_path) == []


def test_lint_multiple_failures(tmp_path):
    m = _good_tree(tmp_path)
    m["skills"][0]["path"] = "skills/ghost"  # skill path missing
    m["agents"][0]["skill"] = "nope"  # unknown skill
    (tmp_path / "hooks" / "guard.py").unlink()  # hook target missing
    _write_manifest(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("skill path missing" in x for x in v)
    assert any("references unknown skill" in x for x in v)
    assert any("hook command target missing" in x for x in v)


# ===================== main() in-process =====================

def test_main_inprocess_all_pass(tmp_path, monkeypatch, capsys):
    _good_tree(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 0
    out = capsys.readouterr().out
    assert "manifest passes" in out
    assert tmp_path.name in out


def test_main_inprocess_fail_exit2(tmp_path, monkeypatch, capsys):
    m = _good_tree(tmp_path)
    m["skills"][0]["path"] = "skills/ghost"
    _write_manifest(tmp_path, m)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 2
    out = capsys.readouterr().out
    assert "skill path missing" in out


def test_main_inprocess_warn_only_exit0(tmp_path, monkeypatch, capsys):
    # WARN のみ (FAIL なし) なら exit 0 だが WARN 行は出力される
    m = _good_tree(tmp_path)
    m["description"] = "x" * (LPM.DESC_LIMIT + 10)
    _write_manifest(tmp_path, m)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 0
    out = capsys.readouterr().out
    assert "WARN: description" in out


def test_main_inprocess_default_root(monkeypatch, capsys):
    # --plugin-root 省略時は実 plugin (contract-generator) を検査して完走する
    monkeypatch.setattr(sys, "argv", ["lint-plugin-manifest.py"])
    rc = LPM.main()
    assert rc in (0, 2)
    assert capsys.readouterr().out  # 何かしら出力される


# ===================== main() via subprocess (__main__ 経路) =====================

def _run_main(plugin_root: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--plugin-root", str(plugin_root)],
        capture_output=True, text=True)


def test_subprocess_all_pass(tmp_path):
    _good_tree(tmp_path)
    r = _run_main(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "manifest passes" in r.stdout


def test_subprocess_fail_exit2(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "hooks" / "guard.py").unlink()
    _write_manifest(tmp_path, m)
    r = _run_main(tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "hook command target missing" in r.stdout


def test_subprocess_manifest_not_found(tmp_path):
    r = _run_main(tmp_path)
    assert r.returncode == 2
    assert "plugin.json not found" in r.stdout
