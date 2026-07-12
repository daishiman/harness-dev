#!/usr/bin/env python3
# /// script
# name: aggregate-completeness
# version: 0.1.0
# purpose: C05 完成度評価レポートの形状検証と全 6 観点スコア→総合 PASS/FAIL の決定論集約 (Goodhart 防止の fail-closed 集約器)
# inputs:
#   - argv: --report FILE / --matrix FILE [--require-complete]
# outputs:
#   - stdout: OK/violation 一覧 or gate 結果 JSON
#   - exit: 0=OK / 1=violation or gate fail / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""assign-system-spec-completeness-evaluator の決定論ヘルパ。

2 つの決定論部品を純関数として提供する (LLM の主観判定から機械層を切り出す)。

1. `validate_report(report)`  — 評価レポートの形状 (観点別スコア + 総合判定 + 不足事項一覧)
   と、総合判定が全観点 verdict + high finding 数から fail-closed に再導出した値と一致するか
   (Goodhart 防止の整合検査) を検証し、違反文字列のリストを返す。
2. `aggregate_verdict(aspect_verdicts, high_count)` — 全 6 観点 (ASPECTS の全キー: foundation_trace /
   decision_guidance / matrix_coverage / design_knowledge_reflection / doc_freshness / prompt_quality)
   の verdict と high severity finding 数から総合 PASS/FAIL を導出する。
   fail-closed: 全観点 PASS かつ high 0 のときだけ PASS。1 観点でも FAIL/INDETERMINATE、
   または high finding が 1 件でもあれば FAIL。観点の取りこぼし (観点未充足) も FAIL。

`run_coverage_gate(...)` は plugin-root の `validate-coverage-matrix.py` (C05 の
deterministic_check) を独立 context で実行し、マトリクス網羅性観点の一次根拠を回収する薄い wrapper。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EVALUATOR_NAME = "assign-system-spec-completeness-evaluator"

# 評価観点の正本。上位概念・意思決定・deep knowledge・鮮度までをfail-closedで扱う。
# matrix_coverage / doc_freshness は独立 context で fork する監査 sub-agent (component) に接地する。
# design_knowledge_reflection は独立 auditor を持たず C05 (R1-score) が自前評価する:
#   C06 (hearing-auditor) は設計知識 (system-spec/*.md) を読まずヒアリング品質のみを監査するため、
#   design_knowledge を C06 へ束縛するのは虚偽対応だった。C06 は matrix_coverage の sub-input
#   (聞き漏れ/誘導/早期停止/トレーサビリティ = 網羅性・トレース根拠) へ再配置する。
ASPECTS: dict[str, dict[str, str]] = {
    "foundation_trace": {
        "label": "上位概念トレーサビリティ",
        "auditor": "assign-system-spec-completeness-evaluator",
        "component": "C05",
    },
    "decision_guidance": {
        "label": "意思決定支援",
        "auditor": "assign-system-spec-completeness-evaluator",
        "component": "C05",
    },
    "matrix_coverage": {
        "label": "マトリクス網羅性",
        "auditor": "system-spec-matrix-auditor",
        "component": "C07",
    },
    "design_knowledge_reflection": {
        "label": "設計知識反映",
        "auditor": "assign-system-spec-completeness-evaluator",
        "component": "C05",
    },
    "doc_freshness": {
        "label": "最新ドキュメント出典",
        "auditor": "system-spec-doc-freshness-auditor",
        "component": "C08",
    },
    "prompt_quality": {
        "label": "prompt-creator準拠",
        "auditor": "assign-system-spec-completeness-evaluator",
        "component": "C05",
    },
}
ASPECT_VERDICTS = {"PASS", "FAIL", "INDETERMINATE"}
OVERALL_VERDICTS = {"PASS", "FAIL"}
SEVERITIES = {"high", "medium", "low", "info"}


def aggregate_verdict(aspect_verdicts: dict, high_count: int) -> str:
    """全観点 verdict + high finding 数から総合 verdict を fail-closed に導出する。

    - 全観点 (ASPECTS のキー) を過不足なく網羅していなければ FAIL (監査観点の取りこぼし防止)。
    - high severity finding が 1 件でもあれば FAIL。
    - 全観点が厳密に PASS のときだけ PASS。FAIL/INDETERMINATE が 1 つでもあれば FAIL。
    副作用なし = 単体テスト可能。
    """
    if set(aspect_verdicts) != set(ASPECTS):
        return "FAIL"
    if any(v not in ASPECT_VERDICTS for v in aspect_verdicts.values()):
        return "FAIL"
    if high_count > 0:
        return "FAIL"
    return "PASS" if all(v == "PASS" for v in aspect_verdicts.values()) else "FAIL"


def _high_count(findings: list) -> int:
    return sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "high")


def validate_report(report: dict) -> list[str]:
    """評価レポートの形状 + 総合判定の整合を検証し違反文字列のリストを返す (空=OK)。"""
    v: list[str] = []
    if not isinstance(report, dict):
        return ["report: オブジェクトでない"]

    ev = report.get("evaluator")
    if not isinstance(ev, dict):
        v.append("evaluator: オブジェクトでない")
    else:
        if ev.get("name") != EVALUATOR_NAME:
            v.append(f"evaluator.name != {EVALUATOR_NAME!r}")
        if ev.get("context") != "fork":
            v.append("evaluator.context != 'fork' (独立 context 必須)")
        if not ev.get("version"):
            v.append("evaluator.version が空")

    verdict = report.get("verdict")
    if verdict not in OVERALL_VERDICTS:
        v.append(f"verdict={verdict!r} が {sorted(OVERALL_VERDICTS)} 外")

    # --- 観点別スコア (全観点を過不足なく) ---
    aspects = report.get("aspects")
    aspect_verdicts: dict[str, str] = {}
    if not isinstance(aspects, dict):
        v.append("aspects: オブジェクトでない")
    else:
        extra = set(aspects) - set(ASPECTS)
        missing = set(ASPECTS) - set(aspects)
        if extra:
            v.append(f"aspects: 未知の観点 {sorted(extra)}")
        if missing:
            v.append(f"aspects: 観点欠落 {sorted(missing)} (全観点を過不足なく)")
        for aid, spec in ASPECTS.items():
            a = aspects.get(aid)
            if not isinstance(a, dict):
                continue
            av = a.get("verdict")
            if av not in ASPECT_VERDICTS:
                v.append(f"aspects[{aid}].verdict={av!r} が {sorted(ASPECT_VERDICTS)} 外")
            else:
                aspect_verdicts[aid] = av
            if a.get("auditor") != spec["auditor"]:
                v.append(f"aspects[{aid}].auditor != {spec['auditor']!r} (観点↔監査 agent 対応)")
            if a.get("component") != spec["component"]:
                v.append(f"aspects[{aid}].component != {spec['component']!r}")
            if not a.get("summary"):
                v.append(f"aspects[{aid}].summary が空")

    # --- 不足事項一覧 ---
    gaps = report.get("gaps")
    if not isinstance(gaps, list):
        v.append("gaps: 配列でない (不足事項一覧)")
        gaps = []

    # --- findings (PASS 時も info 1 件以上) ---
    findings = report.get("findings")
    if not isinstance(findings, list) or not findings:
        v.append("findings: 非空配列でない (PASS 時も info を 1 件以上残す)")
        findings = []
    else:
        for i, f in enumerate(findings):
            if not isinstance(f, dict):
                v.append(f"findings[{i}]: オブジェクトでない")
                continue
            if f.get("severity") not in SEVERITIES:
                v.append(f"findings[{i}].severity={f.get('severity')!r} が {sorted(SEVERITIES)} 外")
            if not f.get("bucket"):
                v.append(f"findings[{i}].bucket が空")
            if not f.get("observation"):
                v.append(f"findings[{i}].observation が空")

    # --- 整合検査: verdict = 再導出値 (Goodhart 防止) ---
    if isinstance(aspects, dict) and verdict in OVERALL_VERDICTS:
        derived = aggregate_verdict(aspect_verdicts, _high_count(findings))
        if derived != verdict:
            v.append(
                f"verdict={verdict!r} が 全観点 + high finding 数からの fail-closed 再導出 "
                f"{derived!r} と不一致 (総合判定が観点スコアに接地していない)"
            )
    # FAIL のとき不足事項が空なら差し戻し材料が欠落
    if verdict == "FAIL" and not gaps:
        v.append("verdict=FAIL だが gaps (不足事項一覧) が空 (差し戻し材料が無い)")
    return v


def _plugin_root() -> Path:
    """.../skills/<skill>/scripts/aggregate-completeness.py -> plugin root (parents[3])。"""
    return Path(__file__).resolve().parents[3]


def run_coverage_gate(matrix_path, require_complete: bool = False) -> dict:
    """plugin-root の validate-coverage-matrix.py (C05 deterministic_check) を実行し結果を返す。"""
    gate = _plugin_root() / "scripts" / "validate-coverage-matrix.py"
    cmd = [sys.executable or "python3", str(gate), "--matrix", str(matrix_path)]
    if require_complete:
        cmd.append("--require-complete")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "id": "G-matrix",
        "name": "validate-coverage-matrix",
        "conditions": ["matrix_coverage"],
        "command": [str(x) for x in cmd],
        "exit_code": int(proc.returncode),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def run_knowledge_graph_gate() -> dict:
    """plugin-root の validate-knowledge-graph.py を 4 profile 実行し C13-C16 の機械層根拠を集約する。

    C05 (評価者) は生成時ゲート (C01/C03) の緑を LLM 裁量で信頼せず、出荷済み 3 カタログを
    validator へ独立再実行する (proposer≠approver・保証要件は機械層)。knowledge/doctrine/
    required-info の各 profile と語彙横断 cross の 4 本が全て exit0 で PASS。design_knowledge_reflection
    (C13/C14/C15) と matrix_coverage (C16) の機械層根拠となる。
    """
    root = _plugin_root()
    gate = root / "scripts" / "validate-knowledge-graph.py"
    ref = root / "skills" / "ref-system-design-knowledge" / "references"
    elicit_ref = root / "skills" / "run-system-spec-elicit" / "references"
    knowledge_catalog = ref / "knowledge-catalog.json"
    doctrine = ref / "doctrine-anchor-registry.json"
    taxonomy = ref / "system-category-taxonomy.json"
    required_info = elicit_ref / "required-info-catalog.json"
    py = sys.executable or "python3"
    runs = (
        ("knowledge", [py, str(gate), "--profile", "knowledge", "--input", str(knowledge_catalog)]),
        ("doctrine", [py, str(gate), "--profile", "doctrine", "--input", str(doctrine)]),
        ("required-info", [py, str(gate), "--profile", "required-info", "--input", str(required_info)]),
        ("cross", [py, str(gate), "--profile", "cross", "--taxonomy", str(taxonomy),
                   "--doctrine", str(doctrine), "--required-info", str(required_info)]),
    )
    subgates = []
    worst = 0
    for name, cmd in runs:
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subgates.append({
            "profile": name,
            "command": [str(x) for x in cmd],
            "exit_code": int(proc.returncode),
            "stderr": proc.stderr.strip(),
        })
        worst = max(worst, int(proc.returncode))
    return {
        "id": "G-knowledge-graph",
        "name": "validate-knowledge-graph",
        "conditions": ["design_knowledge_reflection", "matrix_coverage"],
        "exit_code": worst,
        "subgates": subgates,
    }


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="C05 完成度評価レポートの形状検証 / マトリクス網羅性 + 知識グラフ機械ゲート実行"
    )
    ap.add_argument("--report", help="評価レポート JSON のパス (形状 + 総合判定整合を検証)")
    ap.add_argument("--matrix", help="spec-state.json のパス (マトリクス網羅性ゲートを実行)")
    ap.add_argument("--require-complete", action="store_true", help="ゲートを未収集 0 必須モードで実行")
    ap.add_argument("--knowledge-graph", action="store_true",
                    help="出荷 3 カタログを validate-knowledge-graph.py 4 profile で独立再実行 (C13-C16 機械層)")
    args = ap.parse_args(argv)

    if not args.report and not args.matrix and not args.knowledge_graph:
        ap.error("--report / --matrix / --knowledge-graph のいずれかが必要")

    rc = 0
    if args.matrix:
        result = run_coverage_gate(args.matrix, require_complete=args.require_complete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["exit_code"] != 0:
            rc = 1
    if args.knowledge_graph:
        kg_result = run_knowledge_graph_gate()
        print(json.dumps(kg_result, ensure_ascii=False, indent=2))
        if kg_result["exit_code"] != 0:
            rc = 1
    if args.report:
        path = Path(args.report)
        if not path.is_file():
            print(f"report ファイルが存在しない: {args.report}", file=sys.stderr)
            return 2
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"report の JSON parse 失敗: {exc}", file=sys.stderr)
            return 2
        violations = validate_report(report)
        if violations:
            for msg in violations:
                print(f"VIOLATION: {msg}", file=sys.stderr)
            print(f"FAIL: {len(violations)} 件のレポート整合違反", file=sys.stderr)
            rc = 1
        else:
            print(f"OK: レポート形状と総合判定整合を満たす (verdict={report.get('verdict')})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
