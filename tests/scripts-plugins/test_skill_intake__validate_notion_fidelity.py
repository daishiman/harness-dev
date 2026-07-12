"""validate-notion-fidelity.py の genuine な機能テスト。

対象:
  plugins/skill-intake/skills/assign-notion-fidelity-evaluator/scripts/validate-notion-fidelity.py

このスクリプトは network/keychain を一切持たない純 JSON IO(intake-final-context.json と
canonical-page-snapshot.json を突合しスコア化する)。したがって:
- 純関数 (section_text_length / _char_score / _collect_field_keys / _field_score /
  _viz_score / evaluate / _decide_verdict / _render_markdown) を実ファイルから importlib で
  ロードし、実入力で全分岐(範囲内/下振れ/上振れ・required 有無・warn-fallback・
  viz mandatory 有無・list/dict 形状・substring マッチ・section absent block/warn・
  pass/warn/fail verdict)を assert。
- main は tmp_path に context/snapshot を書き、in-process で呼んで exit code・生成された
  fidelity-report.json/.md・stdout/stderr を assert(repo を汚さない)。
- threshold 不正/欠落ファイル等の usage error(64)も網羅。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins/skill-intake/skills/assign-notion-fidelity-evaluator/scripts/validate-notion-fidelity.py"
)

_SPEC = importlib.util.spec_from_file_location("validate_notion_fidelity", SCRIPT)
VNF = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VNF)


# ============================================================================
# section_text_length
# ============================================================================

def test_section_text_length_string():
    # 空白除去後の文字数
    assert VNF.section_text_length("ab cd ef") == 6


def test_section_text_length_nested():
    val = {"a": "xx", "b": ["yy", {"c": "zz"}], "n": 5, "f": 1.0, "t": True, "z": None}
    # int/float/bool/None は対象外 -> xxyyzz = 6
    assert VNF.section_text_length(val) == 6


def test_section_text_length_empty():
    assert VNF.section_text_length({}) == 0
    assert VNF.section_text_length([]) == 0
    assert VNF.section_text_length(123) == 0


# ============================================================================
# _char_score
# ============================================================================

def test_char_score_in_range():
    assert VNF._char_score(150, {"min": 100, "max": 200}) == 1.0


def test_char_score_below_min():
    # length < lo -> length/lo
    assert VNF._char_score(50, {"min": 100, "max": 200}) == 0.5


def test_char_score_below_min_zero_lo():
    # lo==0 でも 0除算しない
    assert VNF._char_score(0, {"min": 0, "max": 0}) == 1.0


def test_char_score_above_max():
    # length > hi -> 1 - (length-hi)/hi
    assert VNF._char_score(300, {"min": 100, "max": 200}) == pytest.approx(0.5)


def test_char_score_far_above_max_clamps_zero():
    assert VNF._char_score(1000, {"min": 100, "max": 200}) == 0.0


def test_char_score_missing_bounds_defaults():
    # min/max 欠落 -> lo=0, hi=0 -> length<=0 のみ 1.0、それ以外 above-max hi=0 -> 0.0
    assert VNF._char_score(0, {}) == 1.0
    assert VNF._char_score(5, {}) == 0.0


# ============================================================================
# _collect_field_keys
# ============================================================================

def test_collect_field_keys_nested():
    val = {"a": 1, "b": {"c": 2, "d": [{"e": 3}]}}
    assert VNF._collect_field_keys(val) == {"a", "b", "c", "d", "e"}


def test_collect_field_keys_list_root():
    assert VNF._collect_field_keys([{"x": 1}, {"y": 2}]) == {"x", "y"}


def test_collect_field_keys_scalar():
    assert VNF._collect_field_keys("string") == set()


# ============================================================================
# _field_score
# ============================================================================

def test_field_score_no_required_fields():
    score, missing = VNF._field_score({}, {"anything": 1})
    assert score == 1.0
    assert missing == []


def test_field_score_all_present():
    canonical = {"required_fields": [{"key": "a"}, {"key": "b"}]}
    score, missing = VNF._field_score(canonical, {"a": 1, "b": 2})
    assert score == 1.0
    assert missing == []


def test_field_score_missing_block():
    canonical = {"required_fields": [{"key": "a"}, {"key": "b"}]}
    score, missing = VNF._field_score(canonical, {"a": 1})
    assert score == 0.5
    assert missing == ["b"]


def test_field_score_warn_fallback_half_credit():
    canonical = {"required_fields": [
        {"key": "a"},
        {"key": "b", "absence_behavior": "warn-fallback"},
    ]}
    score, missing = VNF._field_score(canonical, {"a": 1})
    # a=1.0 + b=0.5 -> 1.5/2 = 0.75
    assert score == 0.75
    assert missing == ["b (warn-fallback)"]


# ============================================================================
# _viz_score
# ============================================================================

def test_viz_score_no_mandatory():
    canonical = {"viz_slots": [{"asset_id": "opt1", "mandatory": False}]}
    score, missing, optional = VNF._viz_score(canonical, None)
    assert score == 1.0
    assert missing == []
    assert optional == ["opt1"]


def test_viz_score_mandatory_present_list():
    canonical = {"viz_slots": [{"asset_id": "card-x", "mandatory": True}]}
    val = [{"asset_id": "card-x"}]
    score, missing, optional = VNF._viz_score(canonical, val)
    assert score == 1.0
    assert missing == []


def test_viz_score_mandatory_substring_match():
    # substring 互換マッチ: present "prefix-card-x-suffix" contains "card-x"... actually aid in p
    canonical = {"viz_slots": [{"asset_id": "card", "mandatory": True}]}
    val = [{"kind": "card-detail"}]  # "card" in "card-detail"
    score, missing, optional = VNF._viz_score(canonical, val)
    assert score == 1.0


def test_viz_score_mandatory_missing():
    canonical = {"viz_slots": [{"asset_id": "card-x", "mandatory": True}]}
    val = [{"asset_id": "other"}]
    score, missing, optional = VNF._viz_score(canonical, val)
    assert score == 0.0
    assert missing == ["card-x"]


def test_viz_score_dict_section_value():
    canonical = {"viz_slots": [{"asset_id": "card-x", "mandatory": True}]}
    val = {"primary": "card-x"}
    score, missing, optional = VNF._viz_score(canonical, val)
    assert score == 1.0


def test_viz_score_partial_mandatory():
    canonical = {"viz_slots": [
        {"asset_id": "a", "mandatory": True},
        {"asset_id": "b", "mandatory": True},
    ]}
    val = [{"asset_id": "a"}]
    score, missing, optional = VNF._viz_score(canonical, val)
    assert score == 0.5
    assert missing == ["b"]


# ============================================================================
# evaluate — section present / absent / block / warn-fallback
# ============================================================================

def _snapshot(sections):
    return {"sections": sections}


def _section(skey, **over):
    base = {
        "section_key": skey,
        "required_fields": [],
        "char_bounds": {"min": 0, "max": 0},
        "viz_slots": [],
        "absence_behavior": "block",
    }
    base.update(over)
    return base


def test_evaluate_present_perfect():
    snap = _snapshot([
        _section("0_executive_summary", char_bounds={"min": 1, "max": 100}),
    ])
    ctx = {"executive_summary": "x" * 50}
    rep = VNF.evaluate(ctx, snap)
    assert rep["sections"][0]["present"] is True
    assert rep["forced_fail"] is False
    assert rep["overall_score_ratio"] == 1.0


def test_evaluate_absent_block_forces_fail():
    snap = _snapshot([_section("0_executive_summary", absence_behavior="block")])
    rep = VNF.evaluate({}, snap)
    assert rep["forced_fail"] is True
    assert rep["sections"][0]["present"] is False
    assert rep["sections"][0]["warnings"] == ["section absent"]


def test_evaluate_absent_warn_fallback_no_force():
    snap = _snapshot([_section("9_handoff_contract", absence_behavior="warn-fallback")])
    rep = VNF.evaluate({}, snap)
    assert rep["forced_fail"] is False
    # weight 0.5 -> overall ratio 0
    assert rep["overall_score_ratio"] == 0.0


def test_evaluate_char_score_warning_emitted():
    snap = _snapshot([
        _section("0_executive_summary", char_bounds={"min": 100, "max": 200}),
    ])
    ctx = {"executive_summary": "short"}  # len 5 < 100
    rep = VNF.evaluate(ctx, snap)
    sec = rep["sections"][0]
    assert any("char_bounds out of range" in w for w in sec["warnings"])
    assert sec["char_score"] < 1.0


def test_evaluate_missing_fields_reported():
    snap = _snapshot([
        _section(
            "2_user_profile",
            char_bounds={"min": 1, "max": 100},
            required_fields=[{"key": "role"}, {"key": "level"}],
        ),
    ])
    ctx = {"profile": {"role": "engineer", "detail": "x" * 30}}
    rep = VNF.evaluate(ctx, snap)
    sec = rep["sections"][0]
    assert "level" in sec["missing_fields"]
    assert sec["field_score"] == 0.5


def test_evaluate_weight_total_zero_returns_zero():
    # 空 sections -> weight_total 0 -> overall 0
    rep = VNF.evaluate({}, _snapshot([]))
    assert rep["overall_score_ratio"] == 0.0
    assert rep["sections"] == []


def test_evaluate_mixed_block_and_present():
    snap = _snapshot([
        _section("0_executive_summary", char_bounds={"min": 1, "max": 100}),
        _section("8_open_questions", absence_behavior="block",
                 viz_slots=[{"asset_id": "q", "mandatory": True}],
                 required_fields=[{"key": "q1"}]),
    ])
    ctx = {"executive_summary": "x" * 50}  # open_questions absent
    rep = VNF.evaluate(ctx, snap)
    assert rep["forced_fail"] is True
    absent = [s for s in rep["sections"] if not s["present"]][0]
    assert absent["missing_slots"] == ["q"]
    assert absent["missing_fields"] == ["q1"]


# ============================================================================
# _decide_verdict
# ============================================================================

def test_decide_verdict_forced_fail():
    assert VNF._decide_verdict(0.99, True, 0.85, 0.70) == ("fail", 2)


def test_decide_verdict_pass():
    assert VNF._decide_verdict(0.90, False, 0.85, 0.70) == ("pass", 0)


def test_decide_verdict_warn():
    assert VNF._decide_verdict(0.75, False, 0.85, 0.70) == ("warn", 1)


def test_decide_verdict_fail_below_warn():
    assert VNF._decide_verdict(0.50, False, 0.85, 0.70) == ("fail", 2)


# ============================================================================
# _render_markdown
# ============================================================================

def _report(verdict, sections=None):
    return {
        "overall_score": 88.5,
        "forced_fail": verdict == "fail",
        "sections": sections or [
            {
                "section_key": "0_executive_summary",
                "present": True,
                "granularity_score": 90,
                "missing_fields": [],
                "missing_slots": [],
            }
        ],
    }


def test_render_markdown_pass():
    md = VNF._render_markdown(_report("pass"), "pass", {"pass": 0.85, "warn": 0.70})
    assert "verdict=pass" in md
    assert "Notion 公開を続行" in md
    assert "0_executive_summary" in md
    assert md.endswith("\n")


def test_render_markdown_warn():
    md = VNF._render_markdown(_report("warn"), "warn", {"pass": 0.85, "warn": 0.70})
    assert "canonical 再生成を検討" in md


def test_render_markdown_fail_with_missing():
    sections = [{
        "section_key": "1_x", "present": False, "granularity_score": 0,
        "missing_fields": ["a", "b"], "missing_slots": ["viz1"],
    }]
    md = VNF._render_markdown(_report("fail", sections), "fail", {"pass": 0.85, "warn": 0.70})
    assert "差し戻して" in md
    assert "a, b" in md
    assert "viz1" in md


# ============================================================================
# main — end to end (in-process, tmp_path)
# ============================================================================

def _write_inputs(tmp_path, context, sections):
    ctx = tmp_path / "intake-final-context.json"
    snap = tmp_path / "snapshot.json"
    ctx.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    snap.write_text(json.dumps(_snapshot(sections), ensure_ascii=False), encoding="utf-8")
    return ctx, snap


def test_main_pass(tmp_path, capsys):
    ctx, snap = _write_inputs(
        tmp_path,
        {"executive_summary": "x" * 50},
        [_section("0_executive_summary", char_bounds={"min": 1, "max": 100})],
    )
    out_dir = tmp_path / "out"
    rc = VNF.main([str(ctx), "--snapshot", str(snap), "--out-dir", str(out_dir)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "verdict=pass" in captured.out
    # 成果物が生成される
    report = json.loads((out_dir / "fidelity-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "pass"
    assert (out_dir / "fidelity-report.md").exists()


def test_main_fail_block_section_absent(tmp_path, capsys):
    ctx, snap = _write_inputs(
        tmp_path,
        {},  # block section absent
        [_section("0_executive_summary", absence_behavior="block")],
    )
    rc = VNF.main([str(ctx), "--snapshot", str(snap)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "verdict=fail" in err
    # out-dir 既定 = context.parent
    assert (tmp_path / "fidelity-report.json").exists()


def test_main_warn(tmp_path, capsys):
    # overall を warn 帯 (0.70-0.85) に落とす: char_bounds 下振れで field/viz満点
    ctx, snap = _write_inputs(
        tmp_path,
        {"executive_summary": "x" * 60},
        [_section("0_executive_summary", char_bounds={"min": 100, "max": 200})],
    )
    # c_score = 60/100 = 0.6 -> section = 0.3*0.6 + 0.4*1 + 0.3*1 = 0.88 -> pass帯
    # warn 帯に入れるため pass-threshold を上げる
    rc = VNF.main([str(ctx), "--snapshot", str(snap),
                   "--pass-threshold", "0.90", "--warn-threshold", "0.80"])
    assert rc == 1
    assert "verdict=warn" in capsys.readouterr().err


def test_main_threshold_order_invalid(tmp_path, capsys):
    ctx, snap = _write_inputs(tmp_path, {}, [_section("0_executive_summary")])
    rc = VNF.main([str(ctx), "--snapshot", str(snap),
                   "--pass-threshold", "0.50", "--warn-threshold", "0.70"])
    assert rc == 64
    assert "threshold order invalid" in capsys.readouterr().err


def test_main_context_not_found(tmp_path, capsys):
    snap = tmp_path / "snapshot.json"
    snap.write_text(json.dumps(_snapshot([])), encoding="utf-8")
    rc = VNF.main([str(tmp_path / "nope.json"), "--snapshot", str(snap)])
    assert rc == 64
    assert "context not found" in capsys.readouterr().err


def test_main_snapshot_not_found(tmp_path, capsys):
    ctx = tmp_path / "ctx.json"
    ctx.write_text(json.dumps({}), encoding="utf-8")
    rc = VNF.main([str(ctx), "--snapshot", str(tmp_path / "missing.json")])
    assert rc == 64
    assert "snapshot not found" in capsys.readouterr().err


def test_main_creates_nested_out_dir(tmp_path):
    ctx, snap = _write_inputs(
        tmp_path,
        {"executive_summary": "x" * 50},
        [_section("0_executive_summary", char_bounds={"min": 1, "max": 100})],
    )
    nested = tmp_path / "a" / "b" / "c"
    rc = VNF.main([str(ctx), "--snapshot", str(snap), "--out-dir", str(nested)])
    assert rc == 0
    assert (nested / "fidelity-report.json").is_file()


def test_main_default_snapshot_used(tmp_path, capsys, monkeypatch):
    # --snapshot 省略 -> DEFAULT_SNAPSHOT(実 references) を使う。
    # 実ファイルが存在することを前提に in-process 実行(network なし・読み取りのみ)。
    assert VNF.DEFAULT_SNAPSHOT.is_file()
    ctx = tmp_path / "ctx.json"
    ctx.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "out"
    rc = VNF.main([str(ctx), "--out-dir", str(out_dir)])
    # 空 context + 実 snapshot は block section absent -> fail(2)
    assert rc == 2
    report = json.loads((out_dir / "fidelity-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "fail"


# ============================================================================
# main — argparse usage error via subprocess (no positional)
# ============================================================================

def test_main_missing_positional_argparse_error():
    import subprocess
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert r.returncode == 2
    assert "context" in r.stderr or "required" in r.stderr
