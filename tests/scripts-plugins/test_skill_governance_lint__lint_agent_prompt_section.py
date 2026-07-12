"""lint-agent-prompt-section.py の純関数 + main CLI 契約を network 無しで網羅する。

このスクリプトは SubAgent markdown が必須セクション (## Prompt Templates /
## Self-Evaluation) を宣言しているか、および strict-coverage 時に
brief.responsibilities[] と `<!-- responsibility: <id> -->` anchor 集合が
整合するかを検査する純 lint であり、実通信・実 keychain は一切叩かない。

本テストは:
  - find_section: heading 抽出 / 未存在 / 章境界 (^## で打ち切り)
  - extract_anchor_blocks: 0個 / 1個 / 複数 anchor の body スライス
  - load_brief_responsibilities: 正常 JSON / 不正 JSON / 欠落ファイル / kind
  - lint_file Tier1: 合格 / heading 欠落 / quote・round 欠如 /
    auto-agent marker による skip / Self-Evaluation 次元欠如 / read error
  - _lint_responsibility_coverage Tier2: 完全一致 / missing / extra /
    prompt_required 空 body / quote 行無し / placeholder のみ / kind=delegate skip /
    責務無し brief で skip
  - parse_args: --strict-coverage / --brief / --brief 引数欠落 /
    strict だが brief 無し
  - collect_targets: 位置 / --agents-dir / --plugins-root / 各欠落・非dir
  - main: 合格 OK / 違反 exit1 / 引数無し usage exit2 / Tier 表記

を tmp_path 上に合格 fixture と各違反 fixture を作り実入力で genuine に assert する。
main は subprocess(sys.executable) で exit code / stdout / stderr を assert する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-agent-prompt-section.py"

_SPEC = importlib.util.spec_from_file_location("lint_agent_prompt_section_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

VALID_AGENT = """---
name: sample-agent
---
# Sample Agent

## Prompt Templates

### Round 1

> 「あなたは何を達成したいですか？」

## Self-Evaluation

完全性: 全責務を被覆したか自己採点する。
"""

AUTO_AGENT = """# Auto Agent

## Prompt Templates

(対話なし: 自動実行 agent) なので発話例は不要。

## Self-Evaluation

一貫性 を確認する。
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# find_section
# --------------------------------------------------------------------------

def test_find_section_returns_body_until_next_h2():
    text = "## Prompt Templates\nbody line\n## Self-Evaluation\nother\n"
    body = MOD.find_section(text, "## Prompt Templates")
    assert body is not None
    assert "body line" in body
    # 次の ## で打ち切られる。
    assert "other" not in body


def test_find_section_to_end_of_document():
    text = "intro\n## Self-Evaluation\n完全性 tail\n"
    body = MOD.find_section(text, "## Self-Evaluation")
    assert "完全性 tail" in body


def test_find_section_absent_returns_none():
    assert MOD.find_section("no headings here", "## Prompt Templates") is None


# --------------------------------------------------------------------------
# extract_anchor_blocks
# --------------------------------------------------------------------------

def test_extract_anchor_blocks_none():
    assert MOD.extract_anchor_blocks("plain text without anchors") == []


def test_extract_anchor_blocks_single_captures_trailing_body():
    body = "<!-- responsibility: R1 -->\n> 「実発話」\nmore\n"
    blocks = MOD.extract_anchor_blocks(body)
    assert len(blocks) == 1
    rid, sub = blocks[0]
    assert rid == "R1"
    assert "実発話" in sub
    assert "more" in sub


def test_extract_anchor_blocks_multiple_slices_between_anchors():
    body = (
        "<!-- responsibility: R1 -->\nfirst body\n"
        "<!-- responsibility: R2 -->\nsecond body\n"
    )
    blocks = MOD.extract_anchor_blocks(body)
    assert [b[0] for b in blocks] == ["R1", "R2"]
    assert "first body" in blocks[0][1] and "second body" not in blocks[0][1]
    assert "second body" in blocks[1][1]


# --------------------------------------------------------------------------
# load_brief_responsibilities
# --------------------------------------------------------------------------

def test_load_brief_responsibilities_ok(tmp_path):
    bp = tmp_path / "brief.json"
    bp.write_text(json.dumps({
        "kind": "produce",
        "responsibilities": [{"id": "R1"}, {"id": "R2"}],
    }), encoding="utf-8")
    resp, kind = MOD.load_brief_responsibilities(bp)
    assert [r["id"] for r in resp] == ["R1", "R2"]
    assert kind == "produce"


def test_load_brief_responsibilities_missing_file(tmp_path):
    resp, err_or_kind = MOD.load_brief_responsibilities(tmp_path / "nope.json")
    assert resp == []
    assert "brief read error" in err_or_kind


def test_load_brief_responsibilities_invalid_json(tmp_path):
    bp = tmp_path / "bad.json"
    bp.write_text("{ not json", encoding="utf-8")
    resp, err = MOD.load_brief_responsibilities(bp)
    assert resp == []
    assert "brief read error" in err


def test_load_brief_responsibilities_null_list(tmp_path):
    bp = tmp_path / "brief.json"
    bp.write_text(json.dumps({"responsibilities": None}), encoding="utf-8")
    resp, kind = MOD.load_brief_responsibilities(bp)
    assert resp == []
    assert kind is None


# --------------------------------------------------------------------------
# lint_file Tier 1
# --------------------------------------------------------------------------

def test_lint_file_valid_no_findings(tmp_path):
    p = _write(tmp_path, "ok.md", VALID_AGENT)
    assert MOD.lint_file(p) == []


def test_lint_file_auto_agent_marker_skips_quote_requirement(tmp_path):
    p = _write(tmp_path, "auto.md", AUTO_AGENT)
    assert MOD.lint_file(p) == []


def test_lint_file_missing_both_headings(tmp_path):
    p = _write(tmp_path, "empty.md", "# Title only\n")
    findings = MOD.lint_file(p)
    assert any("## Prompt Templates" in f and "missing" in f for f in findings)
    assert any("## Self-Evaluation" in f and "missing" in f for f in findings)


def test_lint_file_prompt_section_without_quote_or_round(tmp_path):
    body = (
        "## Prompt Templates\n\nfree prose without quote or round heading\n\n"
        "## Self-Evaluation\n\n深度 を確認\n"
    )
    p = _write(tmp_path, "noquote.md", body)
    findings = MOD.lint_file(p)
    assert any("needs either a '> ' quote" in f for f in findings)


def test_lint_file_prompt_section_with_round_heading_ok(tmp_path):
    body = (
        "## Prompt Templates\n\n### Round 1\nsome guidance\n\n"
        "## Self-Evaluation\n\n検証可能性 を確認\n"
    )
    p = _write(tmp_path, "round.md", body)
    assert MOD.lint_file(p) == []


def test_lint_file_self_evaluation_without_dimension(tmp_path):
    body = (
        "## Prompt Templates\n\n> 「q」\n\n"
        "## Self-Evaluation\n\nno dimension keyword here\n"
    )
    p = _write(tmp_path, "nodim.md", body)
    findings = MOD.lint_file(p)
    assert any("Self-Evaluation must reference" in f for f in findings)


def test_lint_file_read_error(tmp_path):
    missing = tmp_path / "does-not-exist.md"
    findings = MOD.lint_file(missing)
    assert len(findings) == 1
    assert "read error" in findings[0]


# --------------------------------------------------------------------------
# _lint_responsibility_coverage (Tier 2)
# --------------------------------------------------------------------------

def _brief(tmp_path: Path, responsibilities, kind="produce") -> Path:
    bp = tmp_path / "skill-brief.json"
    bp.write_text(json.dumps({"kind": kind, "responsibilities": responsibilities}),
                  encoding="utf-8")
    return bp


def test_tier2_perfect_match_no_findings(tmp_path):
    prompt_body = (
        "### Round\n<!-- responsibility: R1 -->\n> 「具体発話R1」\n"
        "<!-- responsibility: R2 -->\n> 「具体発話R2」\n"
    )
    bp = _brief(tmp_path, [
        {"id": "R1", "prompt_required": True},
        {"id": "R2", "prompt_required": True},
    ])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert findings == []


def test_tier2_missing_anchor(tmp_path):
    prompt_body = "<!-- responsibility: R1 -->\n> 「x」\n"
    bp = _brief(tmp_path, [{"id": "R1"}, {"id": "R2"}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("missing responsibility anchors" in f and "R2" in f for f in findings)


def test_tier2_extra_anchor(tmp_path):
    prompt_body = (
        "<!-- responsibility: R1 -->\n> 「x」\n"
        "<!-- responsibility: R9 -->\n> 「extra」\n"
    )
    bp = _brief(tmp_path, [{"id": "R1"}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("extra responsibility anchors" in f and "R9" in f for f in findings)


def test_tier2_empty_body_for_required(tmp_path):
    # R1 anchor の直後に R2 anchor が来るので R1 の body は空。
    prompt_body = (
        "<!-- responsibility: R1 --><!-- responsibility: R2 -->\n> 「x」\n"
    )
    bp = _brief(tmp_path, [
        {"id": "R1", "prompt_required": True},
        {"id": "R2", "prompt_required": True},
    ])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("anchor body for R1 is empty" in f for f in findings)


def test_tier2_no_quote_line_for_required(tmp_path):
    prompt_body = "<!-- responsibility: R1 -->\nprose but no quote line\n"
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": True}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("has no '>' quote line" in f for f in findings)


def test_tier2_placeholder_only_quote_for_required(tmp_path):
    prompt_body = "<!-- responsibility: R1 -->\n> 「<実発話例>」\n"
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": True}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("contains only placeholders/TODO" in f for f in findings)


def test_tier2_todo_placeholder_detected(tmp_path):
    prompt_body = "<!-- responsibility: R1 -->\n> TODO まだ書いてない\n"
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": True}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert any("contains only placeholders/TODO" in f for f in findings)


def test_tier2_not_required_anchor_only_ok(tmp_path):
    # prompt_required=false の責務は anchor 行のみで合格 (body 検査 skip)。
    prompt_body = "<!-- responsibility: R1 -->\n"
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": False}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert findings == []


def test_tier2_kind_delegate_skips(tmp_path):
    prompt_body = "no anchors at all"
    bp = _brief(tmp_path, [{"id": "R1"}], kind="delegate")
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    assert findings == []


def test_tier2_no_responsibilities_skips(tmp_path):
    bp = _brief(tmp_path, [])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), "anything", bp)
    assert findings == []


def test_tier2_anchor_not_in_brief_skips_body_check(tmp_path):
    # anchor R9 は brief に無い -> extra で報告されるが body 検査 (required_by_id) は skip。
    prompt_body = "<!-- responsibility: R9 -->\nprose no quote\n"
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": True}])
    findings = MOD._lint_responsibility_coverage(Path("a.md"), prompt_body, bp)
    # R9 の body に対する "has no quote" は出ない (rid not in required_by_id で continue)。
    assert not any("anchor body for R9" in f for f in findings)


# --------------------------------------------------------------------------
# lint_file Tier 2 統合 (strict_coverage 経由)
# --------------------------------------------------------------------------

def test_lint_file_tier2_integration_flags_missing(tmp_path):
    body = (
        "## Prompt Templates\n\n<!-- responsibility: R1 -->\n> 「具体」\n\n"
        "## Self-Evaluation\n\n完全性 を確認\n"
    )
    p = _write(tmp_path, "agent.md", body)
    bp = _brief(tmp_path, [{"id": "R1"}, {"id": "R2"}])
    findings = MOD.lint_file(p, strict_coverage=True, brief_path=bp)
    assert any("missing responsibility anchors" in f for f in findings)


# --------------------------------------------------------------------------
# parse_args
# --------------------------------------------------------------------------

def test_parse_args_plain_positional(tmp_path):
    p = _write(tmp_path, "x.md", VALID_AGENT)
    targets, strict, brief, err = MOD.parse_args([str(p)])
    assert err is None
    assert targets == [p]
    assert strict is False and brief is None


def test_parse_args_strict_and_brief(tmp_path):
    p = _write(tmp_path, "x.md", VALID_AGENT)
    bp = tmp_path / "b.json"
    targets, strict, brief, err = MOD.parse_args(
        ["--strict-coverage", "--brief", str(bp), str(p)]
    )
    assert err is None
    assert strict is True
    assert brief == bp
    assert targets == [p]


def test_parse_args_brief_without_value_is_usage_error():
    _, _, _, err = MOD.parse_args(["--brief"])
    assert err == 2


def test_parse_args_strict_without_brief_is_usage_error(tmp_path):
    p = _write(tmp_path, "x.md", VALID_AGENT)
    _, _, _, err = MOD.parse_args(["--strict-coverage", str(p)])
    assert err == 2


# --------------------------------------------------------------------------
# collect_targets
# --------------------------------------------------------------------------

def test_collect_targets_empty():
    assert MOD.collect_targets([]) == []


def test_collect_targets_positional_paths():
    out = MOD.collect_targets(["a.md", "b.md"])
    assert out == [Path("a.md"), Path("b.md")]


def test_collect_targets_agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    (d / "z.md").write_text("x", encoding="utf-8")
    (d / "a.md").write_text("x", encoding="utf-8")
    (d / "ignore.txt").write_text("x", encoding="utf-8")
    out = MOD.collect_targets(["--agents-dir", str(d)])
    assert [p.name for p in out] == ["a.md", "z.md"]  # sorted, .md only


def test_collect_targets_agents_dir_missing_arg():
    assert MOD.collect_targets(["--agents-dir"]) == []


def test_collect_targets_agents_dir_not_a_dir(tmp_path):
    assert MOD.collect_targets(["--agents-dir", str(tmp_path / "nope")]) == []


def test_collect_targets_plugins_root(tmp_path):
    (tmp_path / "p1" / "agents").mkdir(parents=True)
    (tmp_path / "p1" / "agents" / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "p2" / "agents").mkdir(parents=True)
    (tmp_path / "p2" / "agents" / "b.md").write_text("x", encoding="utf-8")
    out = MOD.collect_targets(["--plugins-root", str(tmp_path)])
    assert {p.name for p in out} == {"a.md", "b.md"}


def test_collect_targets_plugins_root_missing_arg():
    assert MOD.collect_targets(["--plugins-root"]) == []


def test_collect_targets_plugins_root_not_a_dir(tmp_path):
    assert MOD.collect_targets(["--plugins-root", str(tmp_path / "nope")]) == []


# --------------------------------------------------------------------------
# main via subprocess (exit code + stdout/stderr)
# --------------------------------------------------------------------------

def _run(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
    )


def test_cli_no_args_usage_exit2(tmp_path):
    proc = _run([], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_valid_agent_ok_exit0(tmp_path):
    p = _write(tmp_path, "ok.md", VALID_AGENT)
    proc = _run([str(p)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "OK:" in proc.stdout
    assert "Tier 1" in proc.stdout and "Tier 1+2" not in proc.stdout


def test_cli_violation_exit1(tmp_path):
    p = _write(tmp_path, "bad.md", "# nothing\n")
    proc = _run([str(p)], cwd=str(tmp_path))
    assert proc.returncode == 1
    assert "missing required heading" in proc.stderr


def test_cli_strict_coverage_tier_label(tmp_path):
    body = (
        "## Prompt Templates\n\n<!-- responsibility: R1 -->\n> 「具体発話」\n\n"
        "## Self-Evaluation\n\n完全性 を確認\n"
    )
    p = _write(tmp_path, "agent.md", body)
    bp = _brief(tmp_path, [{"id": "R1", "prompt_required": True}])
    proc = _run(["--strict-coverage", "--brief", str(bp), str(p)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "Tier 1+2" in proc.stdout


def test_cli_brief_without_value_exit2(tmp_path):
    proc = _run(["--brief"], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--brief requires a path" in proc.stderr


def test_cli_strict_without_brief_exit2(tmp_path):
    p = _write(tmp_path, "ok.md", VALID_AGENT)
    proc = _run(["--strict-coverage", str(p)], cwd=str(tmp_path))
    assert proc.returncode == 2
    assert "--strict-coverage requires --brief" in proc.stderr


def test_cli_agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    _write(d, "a.md", VALID_AGENT)
    proc = _run(["--agents-dir", str(d)], cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "1 agent file(s) passed" in proc.stdout
