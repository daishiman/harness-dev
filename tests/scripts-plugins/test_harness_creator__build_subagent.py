"""Genuine functional tests for
plugins/harness-creator/skills/run-build-skill/scripts/build-subagent.py.

SKILL.md から Claude Code subagent markdown を生成する決定論スクリプト。
network / keychain は無し (純粋なファイル I/O とテキスト変換)。

スクリプトを実ファイルパスから importlib でロードし、

- parse_frontmatter: frontmatter 無し / 区切り不足 / scalar / クォート除去 /
  inline list ([] / 空) / "  - " 継続 list / コメント行 (#) スキップ / 空行スキップ
- extract_section: 見出し抽出 / 次の ## までで打ち切り / 末尾まで / 不在で ""
- map_tools: str 入力 / list 入力 / "Bash(python3 *)" の括弧除去 / 重複除去 / 空/None
- main: SKILL.md 不在 exit2 / 正常生成 (description / tools / model 行) /
  goal-seek 節優先 / legacy Steps フォールバック / steps 不在の placeholder /
  ### 見出しの抽出 / Purpose 節の role 反映 / 出力先 mkdir / stdout=生成パス /
  description フォールバック / tools 無しなら tools 行省略

を tmp_path 配下の fixture で実入力 assert + main を subprocess(sys.executable) と
in-process(monkeypatch sys.argv) の両経路で確認。repo は汚さない。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "build-subagent.py"
)

_SPEC = importlib.util.spec_from_file_location("build_subagent_s3", SCRIPT)
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

無視されるべき本文。
"""


# ===================== parse_frontmatter =====================

def test_parse_frontmatter_no_leading_marker():
    fm, body = BS.parse_frontmatter("no frontmatter\njust body\n")
    assert fm == {}
    assert body == "no frontmatter\njust body\n"


def test_parse_frontmatter_insufficient_markers():
    # "---" は一つだけ → split で parts < 3
    fm, body = BS.parse_frontmatter("---\nname: foo\n")
    assert fm == {}


def test_parse_frontmatter_scalar_and_quote_strip():
    fm, body = BS.parse_frontmatter('---\nname: foo\ndescription: "a b"\n---\nBODY\n')
    assert fm["name"] == "foo"
    assert fm["description"] == "a b"
    assert "BODY" in body


def test_parse_frontmatter_inline_list():
    fm, _ = BS.parse_frontmatter("---\nallowed-tools: [Read, Write]\n---\n")
    assert fm["allowed-tools"] == ["Read", "Write"]


def test_parse_frontmatter_empty_inline_list():
    fm, _ = BS.parse_frontmatter("---\nallowed-tools: []\n---\n")
    assert fm["allowed-tools"] == []


def test_parse_frontmatter_block_list():
    fm, _ = BS.parse_frontmatter(
        "---\nallowed-tools:\n  - Read\n  - Write\n---\n")
    assert fm["allowed-tools"] == ["Read", "Write"]


def test_parse_frontmatter_comment_and_blank_lines_skipped():
    fm, _ = BS.parse_frontmatter(
        "---\n# a comment\n\nname: foo\n---\n")
    assert fm == {"name": "foo"}


def test_parse_frontmatter_unmatched_line_ignored():
    # ": " も "  - " も無い行 (key 抽出失敗) は無視
    fm, _ = BS.parse_frontmatter("---\nname: foo\nthis line has no colon\n---\n")
    assert fm == {"name": "foo"}


def test_parse_frontmatter_list_item_without_active_key():
    # cur_list_key が無い状態の "  - " は list へ加えられず regex で skip される
    fm, _ = BS.parse_frontmatter("---\n  - orphan\nname: foo\n---\n")
    assert fm == {"name": "foo"}


# ===================== extract_section =====================

def test_extract_section_basic():
    body = "## A\nalpha\n## B\nbeta\n"
    assert BS.extract_section(body, "## A") == "alpha"
    assert BS.extract_section(body, "## B") == "beta"


def test_extract_section_to_end_when_no_next():
    body = "## Only\nline1\nline2\n"
    assert BS.extract_section(body, "## Only") == "line1\nline2"


def test_extract_section_missing_returns_empty():
    assert BS.extract_section("## A\nx\n", "## Missing") == ""


# ===================== map_tools =====================

def test_map_tools_str_input():
    assert BS.map_tools("Read") == "Read"


def test_map_tools_list_strips_parens():
    assert BS.map_tools(["Bash(python3 *)", "Read"]) == "Bash, Read"


def test_map_tools_dedup():
    assert BS.map_tools(["Read", "Read", "Write"]) == "Read, Write"


def test_map_tools_strips_space_args():
    # 空白区切りの引数も base のみ残す
    assert BS.map_tools(["Bash echo hi"]) == "Bash"


def test_map_tools_empty_list():
    assert BS.map_tools([]) == ""


def test_map_tools_none():
    assert BS.map_tools(None) == ""


# ===================== main() in-process =====================

def _run_main_inproc(monkeypatch, capsys, **kwargs):
    argv = ["build-subagent.py"]
    for k, v in kwargs.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    monkeypatch.setattr(sys, "argv", argv)
    rc = BS.main()
    out = capsys.readouterr().out
    return rc, out


def test_main_skill_md_not_found(tmp_path, monkeypatch, capsys):
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="x", skill_md=str(tmp_path / "nope.md"),
        output_dir=str(tmp_path / "out"))
    assert rc == 2


def test_main_full_goal_seek_generation(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, GOAL_SEEK_SKILL)
    out_dir = tmp_path / "agents"
    rc, stdout = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="run-build-skill", skill_md=str(skill),
        output_dir=str(out_dir), model="opus")
    assert rc == 0
    out_path = out_dir / "run-build-skill-subagent.md"
    assert out_path.exists()
    assert str(out_path) in stdout
    content = out_path.read_text(encoding="utf-8")
    # frontmatter
    assert "name: run-build-skill-subagent" in content
    assert "description: Build a skill from a brief" in content
    assert "tools: Bash, Read, Write" in content
    assert "model: opus" in content
    # role 節は Purpose を反映
    assert "Generate artifacts from a SKILL brief" in content
    # goal-seek の ### Step 見出しが箇条書きに変換される
    assert "- Step 1: 要件を読む" in content
    assert "- Step 2: 生成する" in content
    # 次の節の本文は混入しない
    assert "無視されるべき本文" not in content


def test_main_legacy_steps_fallback(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill,
           "---\nname: legacy\ndescription: legacy skill\n---\n"
           "## Steps\n\n### S1: do this\nbody\n\n## End\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="legacy", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "legacy-subagent.md").read_text(encoding="utf-8")
    assert "- S1: do this" in content


def test_main_steps_without_subheadings_keeps_raw(tmp_path, monkeypatch, capsys):
    # Steps 節はあるが ### が一つも無い → 生テキストが残る (lines 空分岐)
    skill = tmp_path / "SKILL.md"
    _write(skill,
           "---\nname: raw\ndescription: raw skill\n---\n"
           "## Steps\nplain step text only\n## End\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="raw", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "raw-subagent.md").read_text(encoding="utf-8")
    assert "plain step text only" in content


def test_main_no_steps_section_placeholder(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nosteps\ndescription: d\n---\n## Other\nx\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="nosteps", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "nosteps-subagent.md").read_text(encoding="utf-8")
    assert "(Steps section not found in SKILL.md)" in content


def test_main_no_purpose_uses_description_and_placeholder(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: np\ndescription: just a desc\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="np", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "np-subagent.md").read_text(encoding="utf-8")
    # role 節は purpose が無いので description を採用
    assert "# 役割\n\njust a desc" in content
    # 出力節は purpose 不在の placeholder
    assert "(Output contract not specified)" in content


def test_main_no_description_fallback(tmp_path, monkeypatch, capsys):
    # description が空 → fallback "Subagent derived from <name>"
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nodesc\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="nodesc", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "nodesc-subagent.md").read_text(encoding="utf-8")
    assert "description: Subagent derived from nodesc" in content


def test_main_no_tools_omits_tools_line(tmp_path, monkeypatch, capsys):
    # allowed-tools 無し → tools 行は出力しない
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: notools\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="notools", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    content = (out_dir / "notools-subagent.md").read_text(encoding="utf-8")
    assert "tools:" not in content
    # model 行は常にある
    assert "model: opus" in content


def test_main_creates_nested_output_dir(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: nest\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "deep" / "nested" / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="nest", skill_md=str(skill), output_dir=str(out_dir))
    assert rc == 0
    assert (out_dir / "nest-subagent.md").exists()


def test_main_custom_model(tmp_path, monkeypatch, capsys):
    skill = tmp_path / "SKILL.md"
    _write(skill, "---\nname: cm\ndescription: d\n---\n## Steps\n### A: x\n")
    out_dir = tmp_path / "agents"
    rc, _ = _run_main_inproc(
        monkeypatch, capsys,
        skill_name="cm", skill_md=str(skill), output_dir=str(out_dir),
        model="sonnet")
    assert rc == 0
    content = (out_dir / "cm-subagent.md").read_text(encoding="utf-8")
    assert "model: sonnet" in content


# ===================== main() via subprocess (__main__ 経路) =====================

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


def test_subprocess_skill_md_not_found(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--skill-name", "x",
         "--skill-md", str(tmp_path / "ghost.md"),
         "--output-dir", str(tmp_path / "out")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "SKILL.md not found" in r.stderr


def test_subprocess_missing_required_arg(tmp_path):
    # --skill-name 必須 → argparse が exit 2
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--skill-md", str(tmp_path / "x.md")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "required" in r.stderr.lower() or "usage" in r.stderr.lower()
