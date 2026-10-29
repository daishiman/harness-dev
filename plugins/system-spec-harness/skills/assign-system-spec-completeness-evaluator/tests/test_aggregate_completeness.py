# /// script
# name: test-aggregate-completeness
# purpose: 完成度レポートの集約・CLI・決定論ゲートを検証する
# inputs:
#   - pytest 実行 (argv なし)
# outputs:
#   - pytest 結果
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""`aggregate-completeness.py` の集約・CLI 回帰テスト。

- main --report --spec-dir: report の spec_dir が同じ dir に解決するか (一致 / ラベル / 欠落)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from completeness_test_support import AGGREGATE as MOD
from completeness_test_support import SKILL_DIR, golden_ledger, golden_report, write_ledger, write_matrix


def test_all_pass_no_high_is_pass():
    assert MOD.aggregate_verdict({aspect: "PASS" for aspect in MOD.ASPECTS}, 0) == "PASS"


def test_single_fail_is_fail():
    verdicts = {aspect: "PASS" for aspect in MOD.ASPECTS}
    verdicts["doc_freshness"] = "FAIL"
    assert MOD.aggregate_verdict(verdicts, 0) == "FAIL"


def test_indeterminate_is_fail_closed():
    verdicts = {aspect: "PASS" for aspect in MOD.ASPECTS}
    verdicts["matrix_coverage"] = "INDETERMINATE"
    assert MOD.aggregate_verdict(verdicts, 0) == "FAIL"


def test_missing_or_extra_aspect_is_fail():
    assert MOD.aggregate_verdict({"matrix_coverage": "PASS"}, 0) == "FAIL"
    verdicts = {aspect: "PASS" for aspect in MOD.ASPECTS}
    verdicts["bogus"] = "PASS"
    assert MOD.aggregate_verdict(verdicts, 0) == "FAIL"


def test_high_or_unknown_verdict_is_fail():
    assert MOD.aggregate_verdict({aspect: "PASS" for aspect in MOD.ASPECTS}, 1) == "FAIL"
    verdicts = {aspect: "PASS" for aspect in MOD.ASPECTS}
    verdicts["doc_freshness"] = "MAYBE"
    assert MOD.aggregate_verdict(verdicts, 0) == "FAIL"


def test_golden_pass_and_fail_report_validation():
    assert MOD.validate_report(golden_report(), golden_ledger()) == []
    assert MOD.validate_report(
        golden_report(verdict="FAIL", verdicts={"doc_freshness": "FAIL"}, gaps=["rerun C08"]),
        golden_ledger(verdicts={"doc_freshness": "FAIL"}),
    ) == []


def test_inconsistent_verdict_and_empty_fail_gaps_are_detected():
    report = golden_report(verdict="PASS", verdicts={"doc_freshness": "FAIL"})
    assert any("不一致" in item for item in MOD.validate_report(report, golden_ledger()))
    assert any("gaps" in item for item in MOD.validate_report(golden_report(verdict="FAIL"), golden_ledger()))


def test_report_shape_and_mapping_violations_are_detected():
    report = golden_report()
    del report["aspects"]["prompt_quality"]
    assert any("観点欠落" in item for item in MOD.validate_report(report, golden_ledger()))
    report = golden_report()
    report["aspects"]["doc_freshness"]["auditor"] = "wrong"
    assert any("auditor" in item for item in MOD.validate_report(report, golden_ledger()))
    report = golden_report(findings=[])
    assert any("findings" in item for item in MOD.validate_report(report, golden_ledger()))
    report = golden_report()
    report["evaluator"]["context"] = "same"
    assert any("context" in item for item in MOD.validate_report(report, golden_ledger()))
    assert MOD.validate_report(["not", "a", "dict"]) == ["report: オブジェクトでない"]


def test_design_knowledge_not_bound_to_hearing_auditor():
    # C06 (hearing-auditor) は system-spec/*.md を読まずヒアリング品質のみを監査するため、
    # design_knowledge_reflection へ束縛しない。C05 R1-score が自前評価する。
    dk = MOD.ASPECTS["design_knowledge_reflection"]
    assert dk["auditor"] == "assign-system-spec-completeness-evaluator"
    assert dk["component"] == "C05"
    # matrix_coverage は C07 primary のまま (C06 は sub-input で machine 層の primary auditor ではない)。
    assert MOD.ASPECTS["matrix_coverage"]["auditor"] == "system-spec-matrix-auditor"
    report = golden_report()
    report["aspects"]["design_knowledge_reflection"]["auditor"] = "system-spec-hearing-auditor"
    assert any("auditor" in item for item in MOD.validate_report(report, golden_ledger()))


def test_schema_unknown_top_level_field_is_rejected():
    report = golden_report()
    report["unexpected_green_field"] = True

    violations = MOD.validate_report(report, golden_ledger())

    assert any("schema" in item and "unexpected_green_field" in item for item in violations)


def test_schema_definition_unknown_keyword_is_rejected_fail_closed(tmp_path, monkeypatch):
    schema = tmp_path / "unknown-keyword.schema.json"
    schema.write_text(
        json.dumps({"$schema": "https://json-schema.org/draft-07/schema#", "type": "object", "unknownGate": True}),
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "COMPLETENESS_SCHEMA", schema)

    violations = MOD.validate_schema({})

    assert any("unknownGate" in item and "schema" in item for item in violations)


def test_report_validation_is_stdlib_only_under_clean_python_s(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(golden_report(), ensure_ascii=False), encoding="utf-8")
    ledger_path = tmp_path / "audit-fork-ledger.jsonl"
    write_ledger(ledger_path)
    script = SKILL_DIR / "scripts" / "aggregate-completeness.py"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    process = subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "--report",
            str(report_path),
            "--fork-ledger",
            str(ledger_path),
            "--session",
            "sess-1",
        ],
        cwd=SKILL_DIR.parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr or process.stdout


def test_report_validation_ignores_a_poisoned_jsonschema_module(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(golden_report(), ensure_ascii=False), encoding="utf-8")
    ledger_path = tmp_path / "audit-fork-ledger.jsonl"
    write_ledger(ledger_path)
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "jsonschema.py").write_text(
        "raise RuntimeError('external jsonschema must not be imported')\n",
        encoding="utf-8",
    )
    script = SKILL_DIR / "scripts" / "aggregate-completeness.py"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(poison)

    process = subprocess.run(
        [
            sys.executable,
            "-S",
            str(script),
            "--report",
            str(report_path),
            "--fork-ledger",
            str(ledger_path),
            "--session",
            "sess-1",
        ],
        cwd=SKILL_DIR.parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr or process.stdout


def test_coverage_gate_passes_and_fails_on_fixture_matrix(tmp_path):
    matrix = tmp_path / "spec-state.json"
    write_matrix(matrix, complete=True)
    assert MOD.run_coverage_gate(matrix, require_complete=True)["exit_code"] == 0
    write_matrix(matrix, complete=False)
    assert MOD.run_coverage_gate(matrix, require_complete=True)["exit_code"] == 1


def test_source_citation_gate_passes_and_fails_and_fits_the_report_schema(tmp_path, capsys):
    state = tmp_path / "spec-state.json"
    write_matrix(state)
    references = tmp_path / "fetched-references.json"
    references.write_text(json.dumps({"references": []}), encoding="utf-8")
    result = MOD.run_source_citation_gate(state, references, tmp_path)
    assert result["id"] == "G-source-citation"
    assert result["exit_code"] == 0, result["stderr"]
    # 収集した gate 結果をそのまま PASS report の gate_results へ入れても schema を通る
    report = golden_report()
    report["gate_results"] = [item for item in report["gate_results"] if item["id"] != "G-source-citation"]
    report["gate_results"].append(result)
    assert MOD.validate_schema(report) == []
    assert MOD.main(["--source-citation", str(references), "--state", str(state), "--repo-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "G-source-citation"
    # 取得対象に無い孤児 reference は violation になり、gate は exit 1 を返す
    references.write_text(json.dumps({"references": [{"target_id": "orphan"}]}), encoding="utf-8")
    assert MOD.run_source_citation_gate(state, references, tmp_path)["exit_code"] == 1
    with pytest.raises(SystemExit):
        MOD.main(["--source-citation", str(references)])
    with pytest.raises(SystemExit):
        MOD.main(["--matrix", str(state), "--state", str(state)])


def test_knowledge_graph_gate_passes_on_shipped_assets_and_cli_outputs_json(capsys):
    result = MOD.run_knowledge_graph_gate()
    assert result["id"] == "G-knowledge-graph"
    assert result["exit_code"] == 0, result["subgates"]
    assert {item["profile"] for item in result["subgates"]} == {"knowledge", "doctrine", "required-info", "cross"}
    assert result["conditions"] == ["design_knowledge_reflection", "matrix_coverage"]
    assert MOD.main(["--knowledge-graph"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "G-knowledge-graph"


def test_knowledge_graph_gate_output_is_valid_report_schema():
    report = golden_report()
    report["gate_results"].append(MOD.run_knowledge_graph_gate())

    assert MOD.validate_schema(report) == []


def test_knowledge_graph_schema_rejects_duplicate_profile_projection():
    report = golden_report()
    knowledge = next(
        item for item in report["gate_results"] if item["id"] == "G-knowledge-graph"
    )
    knowledge["subgates"][1]["profile"] = "knowledge"

    assert any("gate_results" in item and "profile" in item for item in MOD.validate_schema(report))


def test_knowledge_graph_signal_termination_is_fail_closed(monkeypatch):
    completed = iter(
        [
            __import__("subprocess").CompletedProcess([], -9, "", "killed"),
            *[
                __import__("subprocess").CompletedProcess([], 0, "", "")
                for _ in range(3)
            ],
        ]
    )
    monkeypatch.setattr(MOD.subprocess, "run", lambda *args, **kwargs: next(completed))

    result = MOD.run_knowledge_graph_gate()

    assert result["subgates"][0]["exit_code"] == -9
    assert result["exit_code"] != 0


def test_schema_and_rubric_match_the_aggregate_contract():
    schema = json.loads((SKILL_DIR / "schemas" / "completeness-findings.schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["aspects"]["required"]) == set(MOD.ASPECTS)
    assert schema["properties"]["verdict"]["enum"] == ["PASS", "FAIL"]
    delegation = schema["definitions"]["audit_delegation"]
    assert "audit_delegations" in schema["required"]
    assert set(delegation["properties"]["dispatch"]["required"]) == {
        "tool", "subagent_type", "session_id", "response_sha256",
    }
    assert "tool_use_id" in delegation["properties"]["dispatch"]["properties"]
    rubric = json.loads((SKILL_DIR / "references" / "scoring-rubric.json").read_text(encoding="utf-8"))
    assert rubric["aspect_to_auditor"] == {key: value["auditor"] for key, value in MOD.ASPECTS.items()}


def test_hearing_auditor_scope_excludes_decision_guidance():
    """C06 dispatch が C05 の decisions 責務を横取りして false FAIL にしない。"""
    r2 = (SKILL_DIR / "prompts" / "R2-delegate.md").read_text(encoding="utf-8")
    r6 = (
        SKILL_DIR.parent / "run-system-spec-elicit" / "prompts" / "R6-audit-hearing.md"
    ).read_text(encoding="utf-8")
    agent = (SKILL_DIR.parents[1] / "agents" / "system-spec-hearing-auditor.md").read_text(
        encoding="utf-8"
    )
    for contract in (r2, r6, agent):
        assert "decisions[]" in contract
        assert "decision_guidance" in contract
        assert "担当外" in contract
    assert "起動 prompt に decisions の遡及監査を追加してはならない" in r2


def test_main_report_and_matrix_paths(tmp_path):
    with pytest.raises(SystemExit):
        MOD.main([])
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(golden_report(), ensure_ascii=False), encoding="utf-8")
    ledger_path = tmp_path / "audit-fork-ledger.jsonl"
    write_ledger(ledger_path)
    assert MOD.main(["--report", str(report_path), "--fork-ledger", str(ledger_path), "--session", "sess-1"]) == 0
    assert MOD.main(["--report", str(report_path), "--fork-ledger", str(ledger_path), "--session", "sess-2"]) == 1
    assert MOD.main(["--report", str(tmp_path / "nope.json")]) == 2
    matrix = tmp_path / "spec-state.json"
    write_matrix(matrix)
    assert MOD.main(["--matrix", str(matrix), "--require-complete"]) == 0


# ---------- main --report --spec-dir (report の spec_dir の照合) ----------

def _write_report(path: Path, **extra) -> Path:
    report = golden_report()
    report.update(extra)
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return path


def _report_args(report_path: Path, tmp_path: Path) -> list[str]:
    ledger_path = tmp_path / "audit-fork-ledger.jsonl"
    write_ledger(ledger_path)
    return ["--report", str(report_path), "--fork-ledger", str(ledger_path), "--session", "sess-1"]


def test_main_report_spec_dir_resolving_to_the_same_dir_passes(tmp_path, monkeypatch):
    (tmp_path / "system-spec").mkdir()
    monkeypatch.chdir(tmp_path)
    args = _report_args(_write_report(tmp_path / "report.json", spec_dir="system-spec"), tmp_path)
    # 相対は cwd から解決する。書き方が違っても同じ dir に解決すれば一致
    assert MOD.main([*args, "--spec-dir", str(tmp_path / "system-spec")]) == 0
    assert MOD.main([*args, "--spec-dir", "./system-spec/"]) == 0


def test_main_report_spec_dir_with_a_label_is_a_mismatch(tmp_path, monkeypatch, capsys):
    # live trial で fork が書いたラベル。C02 はこれを invalid_confirmation_evidence で拒む
    (tmp_path / "system-spec").mkdir()
    monkeypatch.chdir(tmp_path)
    args = _report_args(
        _write_report(tmp_path / "report.json", spec_dir="system-spec (read-only evaluated)"), tmp_path
    )
    assert MOD.main([*args, "--spec-dir", "system-spec"]) == 1
    err = capsys.readouterr().err
    assert "VIOLATION: spec_dir_mismatch" in err
    assert "FAIL: 1 件のレポート整合違反" in err
    # --spec-dir を渡さなければ、spec_dir は今までどおり照合しない
    assert MOD.main(args) == 0


def test_main_report_without_spec_dir_is_a_mismatch(tmp_path, capsys):
    (tmp_path / "system-spec").mkdir()
    report_path = _write_report(tmp_path / "report.json")
    assert "spec_dir" not in json.loads(report_path.read_text(encoding="utf-8"))
    args = _report_args(report_path, tmp_path)
    assert MOD.main([*args, "--spec-dir", str(tmp_path / "system-spec")]) == 1
    assert "VIOLATION: spec_dir_mismatch" in capsys.readouterr().err


def test_main_spec_dir_needs_an_existing_dir_and_report(tmp_path):
    args = _report_args(_write_report(tmp_path / "report.json", spec_dir=str(tmp_path / "nope")), tmp_path)
    assert MOD.main([*args, "--spec-dir", str(tmp_path / "nope")]) == 2
    with pytest.raises(SystemExit):
        MOD.main(["--knowledge-graph", "--spec-dir", str(tmp_path)])
