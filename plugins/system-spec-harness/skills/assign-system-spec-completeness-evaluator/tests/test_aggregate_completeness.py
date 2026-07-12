# /// script
# name: test-aggregate-completeness
# purpose: assign-system-spec-completeness-evaluator の集約器 (レポート形状検証 + fail-closed 集約 + coverage gate) の受入テスト
# inputs:
#   - pytest 実行 (argv なし)
# outputs:
#   - pytest 結果
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""aggregate-completeness.py の受入テスト。

- aggregate_verdict: 全観点 PASS→PASS / 1 観点 FAIL→FAIL / INDETERMINATE→FAIL / 観点欠落→FAIL / high→FAIL
- validate_report: golden PASS レポートの形状 + 総合判定整合、各種違反検出
- run_coverage_gate: validate-coverage-matrix.py 連携 (完全マトリクス exit0 / 未収集残存 exit1)
- schema: 評価レポートスキーマが有効 JSON で全 6 観点を持つ
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]


def _load():
    path = SKILL_DIR / "scripts" / "aggregate-completeness.py"
    spec = importlib.util.spec_from_file_location("aggregate_completeness", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


# ---------- fixtures ----------

def _golden_aspects(verdicts=None):
    verdicts = verdicts or {}
    out = {}
    for aid, spec in MOD.ASPECTS.items():
        out[aid] = {
            "verdict": verdicts.get(aid, "PASS"),
            "auditor": spec["auditor"],
            "component": spec["component"],
            "summary": f"{spec['label']}: 監査 PASS",
            "evidence": ["exit=0"],
        }
    return out


def _golden_report(verdict="PASS", verdicts=None, findings=None, gaps=None):
    return {
        "evaluator": {
            "name": MOD.EVALUATOR_NAME,
            "version": "0.1.0",
            "context": "fork",
        },
        "verdict": verdict,
        "aspects": _golden_aspects(verdicts),
        "gate_results": [
            {"id": "G-matrix", "name": "validate-coverage-matrix", "exit_code": 0}
        ],
        "findings": findings
        if findings is not None
        else [{"severity": "info", "bucket": "matrix_coverage", "observation": "全観点 PASS"}],
        "gaps": gaps if gaps is not None else [],
    }


def _write_matrix(path: Path, complete: bool = True):
    cats = [
        "database", "auth", "ui-ux", "security",
        "infrastructure", "backend", "frontend", "maintenance-ops",
    ]
    platforms = ["web", "mobile", "tablet", "desktop-windows", "desktop-linux", "desktop-macos"]
    matrix = {}
    for c in cats:
        matrix[c] = {p: {"state": "確定", "qa_ref": "qa-1"} for p in platforms}
    if not complete:
        matrix["database"]["web"] = {"state": "未収集"}
    data = {
        "categories": [{"id": c, "label": c} for c in cats],
        "platforms": platforms,
        "matrix": matrix,
        "qa_log": [{"id": "qa-1"}],
        "approval_log": [],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------- aggregate_verdict ----------

def test_all_pass_no_high_is_pass():
    assert MOD.aggregate_verdict({a: "PASS" for a in MOD.ASPECTS}, 0) == "PASS"


def test_single_fail_is_fail():
    v = {a: "PASS" for a in MOD.ASPECTS}
    v["doc_freshness"] = "FAIL"
    assert MOD.aggregate_verdict(v, 0) == "FAIL"


def test_indeterminate_is_fail_closed():
    v = {a: "PASS" for a in MOD.ASPECTS}
    v["matrix_coverage"] = "INDETERMINATE"
    assert MOD.aggregate_verdict(v, 0) == "FAIL"


def test_missing_aspect_is_fail():
    v = {"matrix_coverage": "PASS", "doc_freshness": "PASS"}  # design_knowledge_reflection 欠落
    assert MOD.aggregate_verdict(v, 0) == "FAIL"


def test_extra_aspect_is_fail():
    v = {a: "PASS" for a in MOD.ASPECTS}
    v["bogus"] = "PASS"
    assert MOD.aggregate_verdict(v, 0) == "FAIL"


def test_high_finding_forces_fail_even_if_all_pass():
    assert MOD.aggregate_verdict({a: "PASS" for a in MOD.ASPECTS}, 1) == "FAIL"


def test_unknown_verdict_value_is_fail():
    v = {a: "PASS" for a in MOD.ASPECTS}
    v["doc_freshness"] = "MAYBE"
    assert MOD.aggregate_verdict(v, 0) == "FAIL"


# ---------- validate_report ----------

def test_golden_pass_report_is_valid():
    assert MOD.validate_report(_golden_report()) == []


def test_golden_fail_report_with_gaps_is_valid():
    report = _golden_report(
        verdict="FAIL",
        verdicts={"doc_freshness": "FAIL"},
        findings=[{
            "severity": "high",
            "bucket": "doc_freshness",
            "observation": "非公式 host",
            "suggested_fix": "doc-fetch へ差し戻す",
        }],
        gaps=["doc_freshness: 非公式 host を公式へ差し替え"],
    )
    assert MOD.validate_report(report) == []


def test_inconsistent_verdict_detected():
    # aspects は全 PASS・high 0 なのに verdict=FAIL → 再導出 PASS と不一致
    report = _golden_report(verdict="FAIL", gaps=["dummy"])
    violations = MOD.validate_report(report)
    assert any("再導出" in v for v in violations)


def test_fail_verdict_without_gaps_detected():
    report = _golden_report(
        verdict="FAIL",
        verdicts={"matrix_coverage": "FAIL"},
        findings=[{"severity": "high", "bucket": "matrix_coverage", "observation": "未収集残存"}],
        gaps=[],
    )
    violations = MOD.validate_report(report)
    assert any("gaps" in v for v in violations)


def test_missing_aspect_in_report_detected():
    report = _golden_report()
    del report["aspects"]["design_knowledge_reflection"]
    violations = MOD.validate_report(report)
    assert any("観点欠落" in v for v in violations)


def test_wrong_auditor_mapping_detected():
    report = _golden_report()
    report["aspects"]["matrix_coverage"]["auditor"] = "system-spec-hearing-auditor"
    violations = MOD.validate_report(report)
    assert any("auditor" in v for v in violations)


def test_design_knowledge_not_bound_to_hearing_auditor():
    # F4/M-3: C06 (hearing-auditor) は system-spec/*.md を読まずヒアリング品質のみを監査するため、
    # design_knowledge_reflection へ束縛しない (虚偽対応の撤去)。C05 R1-score が自前評価する。
    dk = MOD.ASPECTS["design_knowledge_reflection"]
    assert dk["auditor"] != "system-spec-hearing-auditor"
    assert dk["auditor"] == "assign-system-spec-completeness-evaluator"
    assert dk["component"] == "C05"
    # matrix_coverage は C07 primary のまま (C06 は sub-input で machine 層の primary auditor ではない)。
    assert MOD.ASPECTS["matrix_coverage"]["auditor"] == "system-spec-matrix-auditor"
    # design_knowledge を hearing-auditor へ束縛した虚偽レポートは machine 層で違反検出される。
    report = _golden_report()
    report["aspects"]["design_knowledge_reflection"]["auditor"] = "system-spec-hearing-auditor"
    assert any("auditor" in v for v in MOD.validate_report(report))


def test_empty_findings_detected():
    report = _golden_report(findings=[])
    violations = MOD.validate_report(report)
    assert any("findings" in v for v in violations)


def test_bad_context_detected():
    report = _golden_report()
    report["evaluator"]["context"] = "main"
    violations = MOD.validate_report(report)
    assert any("context" in v for v in violations)


def test_non_dict_report_detected():
    assert MOD.validate_report(["not", "a", "dict"]) == ["report: オブジェクトでない"]


# ---------- run_coverage_gate (validate-coverage-matrix.py 連携) ----------

def test_coverage_gate_pass_on_complete_matrix(tmp_path):
    m = tmp_path / "spec-state.json"
    _write_matrix(m, complete=True)
    result = MOD.run_coverage_gate(m, require_complete=True)
    assert result["exit_code"] == 0
    assert result["name"] == "validate-coverage-matrix"


def test_coverage_gate_fail_on_incomplete_matrix(tmp_path):
    m = tmp_path / "spec-state.json"
    _write_matrix(m, complete=False)
    result = MOD.run_coverage_gate(m, require_complete=True)
    assert result["exit_code"] == 1


# ---------- run_knowledge_graph_gate (validate-knowledge-graph.py 独立再実行) ----------

def test_knowledge_graph_gate_pass_on_shipped_assets():
    # 評価者が出荷 3 カタログを validate-knowledge-graph.py 4 profile で独立再実行 (F-SYS-01)
    result = MOD.run_knowledge_graph_gate()
    assert result["id"] == "G-knowledge-graph"
    assert result["exit_code"] == 0, f"出荷資産が知識グラフゲートを通らない: {result['subgates']}"
    profiles = {sg["profile"] for sg in result["subgates"]}
    assert profiles == {"knowledge", "doctrine", "required-info", "cross"}
    assert result["conditions"] == ["design_knowledge_reflection", "matrix_coverage"]


def test_main_knowledge_graph_gate(capsys):
    rc = MOD.main(["--knowledge-graph"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["id"] == "G-knowledge-graph"


# ---------- schema ----------

def test_schema_valid_json_and_covers_three_aspects():
    schema = json.loads(
        (SKILL_DIR / "schemas" / "completeness-findings.schema.json").read_text(encoding="utf-8")
    )
    aspects_required = schema["properties"]["aspects"]["required"]
    assert set(aspects_required) == set(MOD.ASPECTS)
    assert schema["properties"]["verdict"]["enum"] == ["PASS", "FAIL"]


def test_rubric_aspect_to_auditor_matches_module():
    rubric = json.loads(
        (SKILL_DIR / "references" / "scoring-rubric.json").read_text(encoding="utf-8")
    )
    for aid, spec in MOD.ASPECTS.items():
        assert rubric["aspect_to_auditor"][aid] == spec["auditor"]


# ---------- main() ----------

def test_main_requires_a_flag():
    with pytest.raises(SystemExit):
        MOD.main([])


def test_main_report_ok(tmp_path):
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps(_golden_report(), ensure_ascii=False), encoding="utf-8")
    assert MOD.main(["--report", str(rp)]) == 0


def test_main_report_violation(tmp_path):
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps(_golden_report(verdict="FAIL", gaps=["x"]), ensure_ascii=False), encoding="utf-8")
    assert MOD.main(["--report", str(rp)]) == 1


def test_main_report_missing_file(tmp_path):
    assert MOD.main(["--report", str(tmp_path / "nope.json")]) == 2


def test_main_matrix_gate(tmp_path):
    m = tmp_path / "spec-state.json"
    _write_matrix(m, complete=True)
    assert MOD.main(["--matrix", str(m), "--require-complete"]) == 0
