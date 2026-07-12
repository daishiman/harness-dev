"""Genuine functional tests for
plugins/contract-generator/scripts/lint-plugin-manifest.py (scripts4 / _r4).

このスクリプトは plugin.json の宣言と実体 (skills/agents/hooks ディレクトリ +
SKILL.md frontmatter) の整合を機械検査する純粋な静的 lint。
network / Notion / keychain / subprocess は一切起動しない (純テキスト + FS I/O)。

importlib.util.spec_from_file_location で実ファイルパスからロードし、各純関数
(load_json / parse_frontmatter / lint) と main() を、tmp_path 配下に組んだ
「合格 fixture」と「各違反 fixture」で genuine に網羅する。main() は
in-process (monkeypatch sys.argv) と subprocess(sys.executable) の両経路で確認し、
exit code 0/2 の判定 (WARN のみ=0, FAIL あり=2) を assert する。
全 fixture は tmp_path 配下なので repo を汚さない。

ファイル名は scripts3 の同名テストとの pytest import-mode 衝突を避けるため
末尾に _r4 を付している (合成モジュール名も _r4 で分離)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "contract-generator" / "scripts" / "lint-plugin-manifest.py"

_SPEC = importlib.util.spec_from_file_location("lint_plugin_manifest_r4", SCRIPT)
LPM = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(LPM)


# ===================== fixture helpers =====================

def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _skill_md(name: str, rubric_refs: str = "block") -> str:
    """SKILL.md frontmatter を生成。rubric_refs の表現を可変にする。

    block       -> "rubric_refs:\\n  - a\\n  - b"  (継続行 list)
    inline       -> "rubric_refs: [a]"             (inline list)
    inline_empty -> "rubric_refs: []"              (空 inline list)
    empty_value  -> "rubric_refs:"                 (空値 -> None)
    missing      -> 行そのものを出さない
    """
    lines = ["---", f"name: {name}", "description: demo skill"]
    if rubric_refs == "block":
        lines += ["rubric_refs:", "  - rubric/quality.md", "  - rubric/safety.md"]
    elif rubric_refs == "inline":
        lines += ["rubric_refs: [rubric/quality.md]"]
    elif rubric_refs == "inline_empty":
        lines += ["rubric_refs: []"]
    elif rubric_refs == "empty_value":
        lines += ["rubric_refs:"]
    elif rubric_refs == "missing":
        pass
    lines += ["---", "", "# Body", "real content here"]
    return "\n".join(lines) + "\n"


def _good_tree(root: Path) -> dict:
    """違反ゼロになる最小の plugin ツリーを構築し manifest dict を返す。"""
    _write(root / "skills" / "demo-skill" / "SKILL.md", _skill_md("demo-skill"))
    _write(root / "agents" / "demo-agent.md", "# demo agent\nbody\n")
    _write(root / "hooks" / "guard.py", "print('hook')\n")
    manifest = {
        "name": "contract-generator",
        "description": "Short description within limit",
        "skills": [{"name": "demo-skill", "path": "skills/demo-skill"}],
        "agents": [
            {"name": "demo-agent", "path": "agents/demo-agent.md", "skill": "demo-skill"}
        ],
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py"}]}
            ]
        },
    }
    _save(root, manifest)
    return manifest


def _save(root: Path, manifest: dict) -> None:
    _write(root / ".claude-plugin" / "plugin.json",
           json.dumps(manifest, ensure_ascii=False))


# ===================== load_json =====================

def test_load_json_parses_nested_structure(tmp_path):
    p = tmp_path / "data.json"
    payload = {"name": "p", "skills": [{"name": "s", "path": "skills/s"}], "n": 3}
    _write(p, json.dumps(payload, ensure_ascii=False))
    assert LPM.load_json(p) == payload


def test_load_json_invalid_raises(tmp_path):
    p = tmp_path / "bad.json"
    _write(p, "{not valid json,,}")
    try:
        LPM.load_json(p)
        raise AssertionError("expected JSONDecodeError")
    except json.JSONDecodeError:
        pass


# ===================== parse_frontmatter =====================

def test_parse_frontmatter_absent_returns_empty(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "# heading only\nno frontmatter delimiters at all\n")
    assert LPM.parse_frontmatter(p) == {}


def test_parse_frontmatter_scalar_strips_quotes(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nname: 'single'\ndescription: \"double\"\nplain: bare\n---\nbody\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["name"] == "single"
    assert fm["description"] == "double"
    assert fm["plain"] == "bare"


def test_parse_frontmatter_block_list_continuation(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs:\n  - rubric/a.md\n  - rubric/b.md\n  - rubric/c.md\n---\nx\n")
    assert LPM.parse_frontmatter(p)["rubric_refs"] == [
        "rubric/a.md", "rubric/b.md", "rubric/c.md"
    ]


def test_parse_frontmatter_block_list_strips_item_quotes(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs:\n  - \"rubric/a.md\"\n  - 'rubric/b.md'\n---\nx\n")
    assert LPM.parse_frontmatter(p)["rubric_refs"] == ["rubric/a.md", "rubric/b.md"]


def test_parse_frontmatter_inline_list_with_items(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs: [rubric/a.md, rubric/b.md]\n---\nx\n")
    assert LPM.parse_frontmatter(p)["rubric_refs"] == ["rubric/a.md", "rubric/b.md"]


def test_parse_frontmatter_inline_empty_list(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs: []\n---\nx\n")
    assert LPM.parse_frontmatter(p)["rubric_refs"] == []


def test_parse_frontmatter_empty_value_becomes_none(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nrubric_refs:\n---\nx\n")
    assert LPM.parse_frontmatter(p)["rubric_refs"] is None


def test_parse_frontmatter_blank_lines_ignored(tmp_path):
    p = tmp_path / "SKILL.md"
    _write(p, "---\nname: foo\n\n   \ndescription: bar\n---\nx\n")
    assert LPM.parse_frontmatter(p) == {"name": "foo", "description": "bar"}


def test_parse_frontmatter_orphan_dash_falls_through(tmp_path):
    # current_key が None のまま "- orphan" -> list 継続にならず、":" も無いので無視
    p = tmp_path / "SKILL.md"
    _write(p, "---\n- orphan\nname: foo\n---\nx\n")
    assert LPM.parse_frontmatter(p) == {"name": "foo"}


def test_parse_frontmatter_value_then_list_resets_current_key(tmp_path):
    # scalar の後に block list -> current_key が正しく切替わることを確認
    p = tmp_path / "SKILL.md"
    _write(p, "---\nname: foo\nrubric_refs:\n  - rubric/a.md\n---\nx\n")
    fm = LPM.parse_frontmatter(p)
    assert fm["name"] == "foo"
    assert fm["rubric_refs"] == ["rubric/a.md"]


# ===================== lint: happy path =====================

def test_lint_good_tree_zero_violations(tmp_path):
    _good_tree(tmp_path)
    assert LPM.lint(tmp_path) == []


def test_lint_inline_rubric_refs_ok(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="inline"))
    assert LPM.lint(tmp_path) == []


def test_lint_no_optional_sections_ok(tmp_path):
    # skills/agents/hooks を一切宣言しなくても落ちない (空デフォルト経路)
    _save(tmp_path, {"name": "p", "description": "d"})
    assert LPM.lint(tmp_path) == []


def test_lint_agent_without_skill_link_ok(tmp_path):
    m = _good_tree(tmp_path)
    del m["agents"][0]["skill"]
    _save(tmp_path, m)
    assert LPM.lint(tmp_path) == []


def test_lint_hook_command_without_plugin_root_skipped(tmp_path):
    # $CLAUDE_PLUGIN_ROOT を含まない command は regex 不一致で対象外
    m = _good_tree(tmp_path)
    m["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "echo no-root-here"
    _save(tmp_path, m)
    assert LPM.lint(tmp_path) == []


# ===================== lint: violations =====================

def test_lint_manifest_missing(tmp_path):
    out = LPM.lint(tmp_path)
    assert len(out) == 1 and out[0].startswith("FAIL: plugin.json not found")


def test_lint_description_over_limit_warns(tmp_path):
    m = _good_tree(tmp_path)
    m["description"] = "z" * (LPM.DESC_LIMIT + 3)
    _save(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any(x.startswith("WARN: description") and f"exceeds {LPM.DESC_LIMIT}" in x
               for x in v)


def test_lint_description_at_limit_no_warn(tmp_path):
    # 境界値: ちょうど DESC_LIMIT 文字なら WARN を出さない (> 比較の確認)
    m = _good_tree(tmp_path)
    m["description"] = "z" * LPM.DESC_LIMIT
    _save(tmp_path, m)
    assert LPM.lint(tmp_path) == []


def test_lint_skill_path_missing_dir(tmp_path):
    m = _good_tree(tmp_path)
    m["skills"][0]["path"] = "skills/ghost-dir"
    _save(tmp_path, m)
    assert any("skill path missing" in x for x in LPM.lint(tmp_path))


def test_lint_skill_md_missing(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "skills" / "demo-skill" / "SKILL.md").unlink()
    _save(tmp_path, m)
    assert any("SKILL.md missing" in x for x in LPM.lint(tmp_path))


def test_lint_rubric_refs_missing_key(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="missing"))
    assert any("rubric_refs empty/missing" in x for x in LPM.lint(tmp_path))


def test_lint_rubric_refs_empty_list(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="inline_empty"))
    assert any("rubric_refs empty/missing" in x for x in LPM.lint(tmp_path))


def test_lint_rubric_refs_empty_value(tmp_path):
    _good_tree(tmp_path)
    _write(tmp_path / "skills" / "demo-skill" / "SKILL.md",
           _skill_md("demo-skill", rubric_refs="empty_value"))
    assert any("rubric_refs empty/missing" in x for x in LPM.lint(tmp_path))


def test_lint_agent_file_missing(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "agents" / "demo-agent.md").unlink()
    _save(tmp_path, m)
    assert any("agent file missing" in x for x in LPM.lint(tmp_path))


def test_lint_agent_references_unknown_skill(tmp_path):
    m = _good_tree(tmp_path)
    m["agents"][0]["skill"] = "phantom-skill"
    _save(tmp_path, m)
    assert any("references unknown skill 'phantom-skill'" in x
               for x in LPM.lint(tmp_path))


def test_lint_hook_target_missing_reports_event(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "hooks" / "guard.py").unlink()
    _save(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("hook command target missing" in x and "event=PreToolUse" in x
               for x in v)


def test_lint_aggregates_multiple_failures(tmp_path):
    m = _good_tree(tmp_path)
    m["skills"][0]["path"] = "skills/ghost-dir"
    m["agents"][0]["skill"] = "phantom"
    (tmp_path / "hooks" / "guard.py").unlink()
    _save(tmp_path, m)
    v = LPM.lint(tmp_path)
    assert any("skill path missing" in x for x in v)
    assert any("references unknown skill" in x for x in v)
    assert any("hook command target missing" in x for x in v)
    # 3 つ独立した FAIL が同時に集約される
    assert sum(1 for x in v if x.startswith("FAIL")) >= 3


# ===================== main() in-process =====================

def test_main_inprocess_pass_prints_ok(tmp_path, monkeypatch, capsys):
    _good_tree(tmp_path)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 0
    out = capsys.readouterr().out
    assert "manifest passes" in out and tmp_path.name in out


def test_main_inprocess_fail_returns_2(tmp_path, monkeypatch, capsys):
    m = _good_tree(tmp_path)
    (tmp_path / "agents" / "demo-agent.md").unlink()
    _save(tmp_path, m)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 2
    assert "agent file missing" in capsys.readouterr().out


def test_main_inprocess_warn_only_returns_0_but_prints(tmp_path, monkeypatch, capsys):
    m = _good_tree(tmp_path)
    m["description"] = "z" * (LPM.DESC_LIMIT + 8)
    _save(tmp_path, m)
    monkeypatch.setattr(sys, "argv",
                        ["lint-plugin-manifest.py", "--plugin-root", str(tmp_path)])
    assert LPM.main() == 0
    assert "WARN: description" in capsys.readouterr().out


def test_main_inprocess_default_root_completes(monkeypatch, capsys):
    # --plugin-root 省略 -> 実 plugin (contract-generator) を検査し 0/2 で完走
    monkeypatch.setattr(sys, "argv", ["lint-plugin-manifest.py"])
    rc = LPM.main()
    assert rc in (0, 2)
    assert capsys.readouterr().out


# ===================== main() via subprocess (__main__ + exit 経路) =====================

def _run(plugin_root: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--plugin-root", str(plugin_root)],
        capture_output=True, text=True)


def test_subprocess_pass_exit0(tmp_path):
    _good_tree(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "manifest passes" in r.stdout


def test_subprocess_fail_exit2(tmp_path):
    m = _good_tree(tmp_path)
    (tmp_path / "hooks" / "guard.py").unlink()
    _save(tmp_path, m)
    r = _run(tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "hook command target missing" in r.stdout


def test_subprocess_manifest_missing_exit2(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 2
    assert "plugin.json not found" in r.stdout
