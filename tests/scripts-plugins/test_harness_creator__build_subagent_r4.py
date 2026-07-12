"""Genuine functional tests for
plugins/harness-creator/skills/run-build-skill/scripts/build-subagent.py
(scripts4 / _r4).

SKILL.md から Claude Code subagent markdown を生成する決定論スクリプト。
network / keychain / secret は無し (純テキスト変換 + ファイル I/O のみ)。

importlib.util.spec_from_file_location で実ファイルパスからロードして純関数
(parse_frontmatter / extract_section / map_tools) を直接呼び、main() は
in-process (monkeypatch sys.argv + capsys) と subprocess(sys.executable) の
両経路で実行して生成 markdown を実際に read-back し assert する。
全 fixture は tmp_path 配下なので repo を汚さない。

ファイル名は scripts3 の同名テストとの pytest import-mode 衝突を避けるため
末尾に _r4 を付している (合成モジュール名も _r4 で分離)。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
    / "scripts" / "build-subagent.py"
)

_SPEC = importlib.util.spec_from_file_location("build_subagent_r4", SCRIPT)
BS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BS)


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


GOAL_SEEK_SKILL = """---
name: run-build-skill
description: Build a skill from a brief
allowed-tools:
  - Bash(python3 *)
  - Read
  - Write
---

## Purpose & Output Contract

Generate artifacts from a SKILL brief and emit a build trace.

## ゴールシーク実行

### Step 1: 要件を読む

最初に要件を把握する。

### Step 2: 生成する

成果物を生成する。

## 次の節

これは subagent には混入してはならない後続本文。
"""


# ===================== parse_frontmatter =====================

def test_pf_no_leading_marker_returns_text_unchanged():
    fm, body = BS.parse_frontmatter("plain body\nline2\n")
    assert fm == {}
    assert body == "plain body\nline2\n"


def test_pf_single_marker_insufficient_parts():
    # "---" が一つ -> split("---", 2) で parts < 3 -> ({}, text)
    fm, body = BS.parse_frontmatter("---\nname: foo\n")
    assert fm == {}
    assert body == "---\nname: foo\n"


def test_pf_scalar_and_quote_strip():
    fm, body = BS.parse_frontmatter(
        "---\nname: foo\ndescription: \"a b\"\nplain: 'q'\n---\nBODY TEXT\n")
    assert fm["name"] == "foo"
    assert fm["description"] == "a b"
    assert fm["plain"] == "q"
    assert "BODY TEXT" in body


def test_pf_inline_list_with_items():
    fm, _ = BS.parse_frontmatter("---\nallowed-tools: [Read, Write, Bash]\n---\n")
    assert fm["allowed-tools"] == ["Read", "Write", "Bash"]


def test_pf_inline_empty_list():
    fm, _ = BS.parse_frontmatter("---\nallowed-tools: []\n---\n")
    assert fm["allowed-tools"] == []


def test_pf_block_list_continuation():
    fm, _ = BS.parse_frontmatter(
        "---\nallowed-tools:\n  - Read\n  - Write\n---\n")
    assert fm["allowed-tools"] == ["Read", "Write"]


def test_pf_comment_and_blank_lines_skipped():
    fm, _ = BS.parse_frontmatter("---\n# a comment line\n\nname: foo\n---\n")
    assert fm == {"name": "foo"}


def test_pf_unmatched_line_ignored():
    # ":" 無し & "  - " 無し -> regex 不一致で無視
    fm, _ = BS.parse_frontmatter("---\nname: foo\nthis has no colon\n---\n")
    assert fm == {"name": "foo"}


def test_pf_block_item_without_active_key_skipped():
    # cur_list_key が None の状態の "  - orphan" は append されず regex で無視
    fm, _ = BS.parse_frontmatter("---\n  - orphan\nname: foo\n---\n")
    assert fm == {"name": "foo"}


def test_pf_scalar_after_list_resets_list_key():
    # block list の後に scalar -> cur_list_key が None に戻ること
    fm, _ = BS.parse_frontmatter(
        "---\nallowed-tools:\n  - Read\nname: foo\n---\n")
    assert fm["allowed-tools"] == ["Read"]
    assert fm["name"] == "foo"


# ===================== extract_section =====================

def test_extract_section_basic_two_headings():
    body = "## A\nalpha line\n## B\nbeta line\n"
    assert BS.extract_section(body, "## A") == "alpha line"
    assert BS.extract_section(body, "## B") == "beta line"


def test_extract_section_runs_to_end_when_no_next():
    body = "## Only\nline1\nline2\n"
    assert BS.extract_section(body, "## Only") == "line1\nline2"


def test_extract_section_missing_returns_empty():
    assert BS.extract_section("## A\nx\n", "## Nonexistent") == ""


def test_extract_section_heading_with_regex_chars():
    # re.escape が効くこと (括弧やドットを含む見出し)
    body = "## Purpose (v1.0)\ncontent\n## Next\nx\n"
    assert BS.extract_section(body, "## Purpose (v1.0)") == "content"


# ===================== map_tools =====================

def test_map_tools_str_single():
    assert BS.map_tools("Read") == "Read"


def test_map_tools_list_strips_paren_args():
    assert BS.map_tools(["Bash(python3 *)", "Read"]) == "Bash, Read"


def test_map_tools_dedup_preserves_order():
    assert BS.map_tools(["Write", "Read", "Read", "Write"]) == "Write, Read"


def test_map_tools_strips_space_separated_args():
    assert BS.map_tools(["Bash echo hi"]) == "Bash"


def test_map_tools_empty_list():
    assert BS.map_tools([]) == ""


def test_map_tools_none():
    assert BS.map_tools(None) == ""


def test_map_tools_str_with_paren():
    # str 入力でも括弧除去される
    assert BS.map_tools("Bash(git *)") == "Bash"


# ===================== main() in-process =====================

def _run_main(monkeypatch, capsys, **kwargs):
    argv = ["build-subagent.py"]
    for k, v in kwargs.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = BS.main()
    return rc, capsys.readouterr().out


def test_main_skill_md_not_found_exit2(tmp_path, monkeypatch, capsys):
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="x", skill_md=str(tmp_path / "absent.md"),
        output_dir=str(tmp_path / "out"))
    assert rc == 2


def test_main_full_goal_seek_generation(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, GOAL_SEEK_SKILL)
    out_dir = tmp_path / "agents"
    rc, stdout = _run_main(
        monkeypatch, capsys,
        skill_name="run-build-skill", skill_md=str(skill),
        output_dir=str(out_dir), model="opus")
    assert rc == 0
    out_path = out_dir / "run-build-skill-subagent.md"
    assert out_path.exists()
    assert str(out_path) in stdout
    content = out_path.read_text(encoding="utf-8")
    assert "name: run-build-skill-subagent" in content
    assert "description: Build a skill from a brief" in content
    assert "tools: Bash, Read, Write" in content
    assert "model: opus" in content
    # role 節は Purpose 節を反映
    assert "Generate artifacts from a SKILL brief" in content
    # goal-seek の ### Step 見出しが箇条書きに変換される
    assert "- Step 1: 要件を読む" in content
    assert "- Step 2: 生成する" in content
    # 後続節の本文は混入しない
    assert "混入してはならない" not in content


def test_main_legacy_steps_fallback(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill,
           "---\nname: legacy\ndescription: legacy skill\n---\n"
           "## Steps\n\n### S1: do this\nbody\n\n## End\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="legacy", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "legacy-subagent.md").read_text(encoding="utf-8")
    assert "- S1: do this" in content


def test_main_steps_without_subheadings_keeps_raw(tmp_path, monkeypatch, capsys):
    # Steps 節はあるが ### 見出しが無い -> 生テキスト保持 (lines 空 -> steps 出力)
    skill = tmp_path / "SKILL.md"
    _write(skill,
           "---\nname: raw\ndescription: raw skill\n---\n"
           "## Steps\nplain step text only\n## End\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="raw", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "raw-subagent.md").read_text(encoding="utf-8")
    assert "plain step text only" in content


def test_main_no_steps_section_placeholder(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nosteps\ndescription: d\n---\n## Other\nx\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="nosteps", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "nosteps-subagent.md").read_text(encoding="utf-8")
    assert "(Steps section not found in SKILL.md)" in content


def test_main_no_purpose_uses_description_and_placeholder(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: np\ndescription: just a desc\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="np", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "np-subagent.md").read_text(encoding="utf-8")
    # purpose 不在 -> role 節は description を採用
    assert "# 役割\n\njust a desc" in content
    # 出力節も purpose 不在の placeholder
    assert "(Output contract not specified)" in content


def test_main_no_description_fallback(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nodesc\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="nodesc", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "nodesc-subagent.md").read_text(encoding="utf-8")
    assert "description: Subagent derived from nodesc" in content


def test_main_empty_tools_omits_tools_line(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: notools\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="notools", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "notools-subagent.md").read_text(encoding="utf-8")
    assert "tools:" not in content
    assert "model: opus" in content  # model 行は常にある


def test_main_creates_nested_output_dir(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nest\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "deep" / "nested" / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="nest", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    assert (out_dir / "nest-subagent.md").exists()


def test_main_custom_model_flag(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: cm\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main(
        monkeypatch, capsys,
        skill_name="cm", skill_md=str(skill), output_dir=str(out_dir),
        model="sonnet")
    assert rc == 0
    content = (out_dir / "cm-subagent.md").read_text(encoding="utf-8")
    assert "model: sonnet" in content


def test_main_default_output_dir(tmp_path, monkeypatch, capsys):
    # --output-dir 省略 -> 既定 ".claude/agents/" (tmp cwd 配下に作られる)
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: defdir\ndescription: d\n---\n## Steps\n### A: x\n")
    monkeypatch.chdir(tmp_path)
    rc, stdout = _run_main(
        monkeypatch, capsys,
        skill_name="defdir", skill_md=str(skill))
    assert rc == 0
    assert (tmp_path / ".claude" / "agents" / "defdir-subagent.md").exists()


# ===================== main() via subprocess (__main__ + SystemExit 経路) =====================

def test_subprocess_full_generation(tmp_path):
    skill = tmp_path / "SKILL.md"
    _write(skill, GOAL_SEEK_SKILL)
    out_dir = tmp_path / "agents"
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--skill-name", "run-build-skill",
         "--skill-md", str(skill),
         "--output-dir", str(out_dir)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    out_path = out_dir / "run-build-skill-subagent.md"
    assert out_path.exists()
    assert r.stdout.strip() == str(out_path)


def test_subprocess_skill_md_not_found_exit2(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--skill-name", "x",
         "--skill-md", str(tmp_path / "ghost.md"),
         "--output-dir", str(tmp_path / "out")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "SKILL.md not found" in r.stderr


def test_subprocess_missing_required_arg_exit2(tmp_path):
    # --skill-name は required -> argparse が exit 2
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--skill-md", str(tmp_path / "x.md")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "required" in r.stderr.lower() or "usage" in r.stderr.lower()
