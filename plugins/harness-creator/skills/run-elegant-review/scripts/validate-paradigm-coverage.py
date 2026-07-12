#!/usr/bin/env python3
# /// script
# name: validate-paradigm-coverage
# purpose: Validate that elegant-review outputs cover all 30 paradigms with structured findings, and that run dirs follow Phase1->2->3 order.
# inputs:
#   - argv: review.md or findings.json, or --phase-order <run-dir-or-tree>
# outputs:
#   - stdout: OK message
#   - stderr: missing paradigm / schema / phase-order errors
#   - exit: 0=OK / 1=coverage or phase-order failure / 2=usage error
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""Check whether a review output covers all 30 paradigms.

Usage:
  validate-paradigm-coverage.py <review.md | findings.json>
  validate-paradigm-coverage.py --phase-order <run-dir | tree-root>

--phase-order は elegant-review run ディレクトリ
(eval-log/**/elegant-review/<run-id>/) の Phase1→2→3 成果物の存在+順序を検査する
(enforcement 名: run-elegant-review/scripts/validate-paradigm-coverage.py (phase order check))。
tolerant 契約: 3 phase の成果物 (shared_state.md / findings-phase2-*.json /
findings.json 等) が全て揃う run のみ順序検査し、どれかを欠く旧 run は skip する
(遡及 fail させない)。順序は mtime 比較で同時刻を許容する (fresh checkout 耐性)。

Exit codes:
  0 -> all 30 covered with structured findings or markdown mentions / phase order OK
  1 -> missing paradigms or phase-order violation detected
  2 -> usage error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Each paradigm: id -> list of acceptance tokens (ja + en, lowercased substring match)
PARADIGMS: dict[int, list[str]] = {
    1: ["批判的思考", "critical"],
    2: ["演繹思考", "演繹", "deductive"],
    3: ["帰納的思考", "帰納", "inductive"],
    4: ["アブダクション", "abductive", "abduction"],
    5: ["垂直思考", "vertical"],
    6: ["要素分解", "decomposition"],
    7: ["mece"],
    8: ["2軸思考", "二軸思考", "two-axis", "two axis"],
    9: ["プロセス思考", "process thinking"],
    10: ["メタ思考", "meta thinking"],
    11: ["抽象化思考", "抽象化", "abstraction"],
    12: ["ダブル・ループ", "ダブルループ", "double-loop", "double loop"],
    13: ["ブレインストーミング", "ブレスト", "brainstorm"],
    14: ["水平思考", "lateral"],
    15: ["逆説思考", "paradox"],
    16: ["類推思考", "類推", "analogy"],
    17: ["if思考", "what-if", "what if"],
    18: ["素人思考", "beginner"],
    19: ["システム思考", "systems thinking", "system thinking"],
    20: ["因果関係分析", "causal analysis"],
    21: ["因果ループ", "causal loop"],
    22: ["トレードオン", "trade-on", "trade on"],
    23: ["プラスサム", "positive-sum", "positive sum"],
    24: ["価値提案思考", "価値提案", "value proposition"],
    25: ["戦略的思考", "strategic"],
    26: ["why思考", "why thinking"],
    27: ["改善思考", "improvement"],
    28: ["仮説思考", "hypothesis"],
    29: ["論点思考", "issue thinking"],
    30: ["kj法", "kj method"],
}

EXPECTED_META: dict[int, tuple[str, str, str]] = {
    1: ("critical", "A-logical", "elegant-logical-structural-analyst"),
    2: ("deduction", "A-logical", "elegant-logical-structural-analyst"),
    3: ("induction", "A-logical", "elegant-logical-structural-analyst"),
    4: ("abduction", "A-logical", "elegant-logical-structural-analyst"),
    5: ("vertical", "A-logical", "elegant-logical-structural-analyst"),
    6: ("decomposition", "B-structural", "elegant-logical-structural-analyst"),
    7: ("mece", "B-structural", "elegant-logical-structural-analyst"),
    8: ("two-axis", "B-structural", "elegant-logical-structural-analyst"),
    9: ("process", "B-structural", "elegant-logical-structural-analyst"),
    10: ("meta", "C-meta", "elegant-meta-divergent-analyst"),
    11: ("abstraction", "C-meta", "elegant-meta-divergent-analyst"),
    12: ("double-loop", "C-meta", "elegant-meta-divergent-analyst"),
    13: ("brainstorming", "D-divergent", "elegant-meta-divergent-analyst"),
    14: ("lateral", "D-divergent", "elegant-meta-divergent-analyst"),
    15: ("paradox", "D-divergent", "elegant-meta-divergent-analyst"),
    16: ("analogy", "D-divergent", "elegant-meta-divergent-analyst"),
    17: ("if", "D-divergent", "elegant-meta-divergent-analyst"),
    18: ("naive", "D-divergent", "elegant-meta-divergent-analyst"),
    19: ("systems", "E-system", "elegant-system-strategic-analyst"),
    20: ("causal", "E-system", "elegant-system-strategic-analyst"),
    21: ("causal-loop", "E-system", "elegant-system-strategic-analyst"),
    22: ("trade-on", "F-strategic", "elegant-system-strategic-analyst"),
    23: ("plus-sum", "F-strategic", "elegant-system-strategic-analyst"),
    24: ("value-proposition", "F-strategic", "elegant-system-strategic-analyst"),
    25: ("strategic", "F-strategic", "elegant-system-strategic-analyst"),
    26: ("why", "A-logical", "elegant-logical-structural-analyst"),
    27: ("kaizen", "G-problem", "elegant-system-strategic-analyst"),
    28: ("hypothesis", "G-problem", "elegant-system-strategic-analyst"),
    29: ("issue", "G-problem", "elegant-system-strategic-analyst"),
    30: ("kj", "G-problem", "elegant-system-strategic-analyst"),
}


def validate_structured_json(path: Path) -> tuple[bool, list[str]]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, ["invalid json"]
    findings = data.get("paradigm_findings")
    if not isinstance(findings, list):
        return False, ["missing paradigm_findings"]

    by_id: dict[int, dict] = {}
    errors: list[str] = []
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            errors.append(f"paradigm_findings[{idx}] is not an object")
            continue
        pid = item.get("paradigm_id")
        if not isinstance(pid, int):
            errors.append(f"paradigm_findings[{idx}].paradigm_id is not int")
            continue
        by_id[pid] = item

    coverage = data.get("thought_method_coverage")
    skipped_by_method: dict[str, str] = {}
    used_methods: set[str] = set()
    if coverage is None:
        errors.append("missing thought_method_coverage")
    elif not isinstance(coverage, dict):
        errors.append("thought_method_coverage must be an object")
    else:
        if coverage.get("total") != 30:
            errors.append("thought_method_coverage.total must be 30")
        used = coverage.get("used", [])
        if not isinstance(used, list):
            errors.append("thought_method_coverage.used must be a list")
        else:
            used_methods = {str(item).strip() for item in used if str(item).strip()}
        skipped = coverage.get("skipped_with_reason", [])
        if not isinstance(skipped, list):
            errors.append("thought_method_coverage.skipped_with_reason must be a list")
        else:
            for idx, item in enumerate(skipped):
                if not isinstance(item, dict):
                    errors.append(f"skipped_with_reason[{idx}] must be object")
                    continue
                method = str(item.get("method", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if not method or not reason:
                    errors.append(f"skipped_with_reason[{idx}] requires method and reason")
                    continue
                skipped_by_method[method] = reason
        covered_count = len(used_methods) + len(skipped_by_method)
        if covered_count != 30:
            errors.append(
                "thought_method_coverage.used + skipped_with_reason must cover 30 distinct methods"
            )
        overlap = used_methods & set(skipped_by_method)
        if overlap:
            errors.append(f"thought_method_coverage used/skipped overlap: {sorted(overlap)}")

    missing = []
    for pid in PARADIGMS:
        expected_name = EXPECTED_META[pid][0]
        if pid not in by_id and expected_name not in skipped_by_method:
            missing.append(pid)
        if pid in by_id and coverage is not None and expected_name not in used_methods:
            errors.append(f"paradigm {pid}: finding exists but method missing from coverage.used")
    if missing:
        errors.append(f"missing paradigm_findings ids without skip_reason: {missing}")

    valid_conditions = {"C1", "C2", "C3", "C4"}
    valid_severities = {"critical", "high", "medium", "low"}
    for pid in sorted(set(PARADIGMS) & set(by_id)):
        item = by_id[pid]
        expected_name, expected_category, expected_agent = EXPECTED_META[pid]
        if item.get("paradigm_name") != expected_name:
            errors.append(f"paradigm {pid}: expected paradigm_name={expected_name}")
        if item.get("category") != expected_category:
            errors.append(f"paradigm {pid}: expected category={expected_category}")
        if item.get("agent") != expected_agent:
            errors.append(f"paradigm {pid}: expected agent={expected_agent}")
        observations = item.get("observations")
        issues = item.get("issues")
        if not isinstance(observations, list) or not any(str(x).strip() for x in observations):
            errors.append(f"paradigm {pid}: observations must contain non-empty text")
        matrix = item.get("condition_matrix")
        if not isinstance(matrix, dict):
            errors.append(f"paradigm {pid}: condition_matrix must cover C1-C4")
        else:
            for cond in ("C1", "C2", "C3", "C4"):
                verdict = matrix.get(cond)
                if not isinstance(verdict, dict):
                    errors.append(f"paradigm {pid}: condition_matrix.{cond} must be object")
                    continue
                status = verdict.get("verdict")
                if status not in {"PASS", "FAIL", "PARTIAL"}:
                    errors.append(f"paradigm {pid}: condition_matrix.{cond}.verdict invalid")
                evidence = verdict.get("evidence")
                if not isinstance(evidence, list) or not any(str(x).strip() for x in evidence):
                    errors.append(f"paradigm {pid}: condition_matrix.{cond}.evidence must contain non-empty text")
        if not isinstance(issues, list):
            errors.append(f"paradigm {pid}: issues must be a list")
            continue
        for i, issue in enumerate(issues):
            if not isinstance(issue, dict):
                errors.append(f"paradigm {pid} issue {i}: not an object")
                continue
            if issue.get("condition") not in valid_conditions:
                errors.append(f"paradigm {pid} issue {i}: invalid condition")
            if issue.get("severity") not in valid_severities:
                errors.append(f"paradigm {pid} issue {i}: invalid severity")
            signal = issue.get("condition_signal")
            valid_signals = {"contradiction", "omission", "inconsistency", "dependency_break", "smell"}
            if signal is not None and signal not in valid_signals:
                errors.append(f"paradigm {pid} issue {i}: invalid condition_signal")
            if not str(issue.get("description", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing description")
            if not str(issue.get("recommended_intervention", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing recommended_intervention")

    variable_abstraction = data.get("variable_abstraction")
    if not isinstance(variable_abstraction, list):
        errors.append("variable_abstraction must be a list")
    for idx, var in enumerate(variable_abstraction or []):
        if not isinstance(var, dict):
            errors.append(f"variable_abstraction[{idx}] must be object")
            continue
        for key in ("concrete_value", "variable_name", "source_trace"):
            if key not in var:
                errors.append(f"variable_abstraction[{idx}] missing {key}")
        if not str(var.get("variable_name", "")).startswith("{{"):
            errors.append(f"variable_abstraction[{idx}].variable_name must be template variable")

    return not errors, errors


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


# --- Phase 順序検査 (enforcement: phase order check) ---

_PHASE1_NAME = "shared_state.md"
_PHASE2_GLOB = "findings-phase2-*.json"
# Phase3 成果物は findings.json (集約) または phase3-*.json (batch 実行結果)。
_PHASE3_NAME = "findings.json"
_PHASE3_GLOB = "phase3-*.json"


def check_phase_order(run_dir: Path) -> tuple[str, list[str]]:
    """1 つの run dir の Phase1→2→3 成果物の存在+順序を検査する。

    returns (status, errors)  status: "ok" | "skipped" | "violation"
    3 phase の成果物が全て揃う run のみ順序検査する (揃わない旧 run は skipped)。
    順序は mtime で判定し、同時刻 (checkout で mtime が揃う) は許容する。

    Phase1 (shared_state.md) は存在のみ検査する: shared_state.md は Phase3 以降も
    申し送りとして更新される living document であり、mtime は run 終端を指すのが
    正常のため順序判定に使えない (実 run 4 件で実測)。mtime 順序が機械的に意味を
    持つのは「Phase2 findings → Phase3 成果物」の一辺のみ。
    """
    phase1 = run_dir / _PHASE1_NAME
    phase2 = sorted(run_dir.glob(_PHASE2_GLOB))
    phase3 = [p for p in [run_dir / _PHASE3_NAME] if p.is_file()]
    phase3 += sorted(run_dir.glob(_PHASE3_GLOB))
    if not (phase1.is_file() and phase2 and phase3):
        return "skipped", []
    try:
        t2_max = max(p.stat().st_mtime for p in phase2)
        t3 = max(p.stat().st_mtime for p in phase3)
    except OSError as exc:
        return "skipped", [f"{run_dir}: stat failed, skipped: {exc}"]
    errors: list[str] = []
    if t2_max > t3:
        errors.append(
            f"{run_dir}: phase order violation: {_PHASE2_GLOB} (Phase2) is newer "
            "than Phase3 artifacts (findings.json / phase3-*.json)"
        )
    return ("violation", errors) if errors else ("ok", [])


def iter_run_dirs(base: Path):
    """base が run dir ならそれ自身、tree なら **/elegant-review/<run-id>/ を列挙する。"""
    if (base / _PHASE1_NAME).is_file() or any(base.glob(_PHASE2_GLOB)):
        yield base
        return
    for child in sorted(base.glob("**/elegant-review/*")):
        if child.is_dir():
            yield child


def check_phase_order_tree(base: Path) -> int:
    ok = skipped = 0
    all_errors: list[str] = []
    for run_dir in iter_run_dirs(base):
        status, errors = check_phase_order(run_dir)
        if status == "skipped":
            skipped += 1
        elif status == "ok":
            ok += 1
        else:
            all_errors.extend(errors)
    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        return 1
    print(f"OK: phase order verified for {ok} run(s), skipped {skipped} incomplete run(s)")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: validate-paradigm-coverage.py <file> | --phase-order <dir>",
            file=sys.stderr,
        )
        return 2
    if argv[1] == "--phase-order":
        if len(argv) < 3:
            print("usage: validate-paradigm-coverage.py --phase-order <dir>", file=sys.stderr)
            return 2
        base = Path(argv[2])
        if not base.is_dir():
            print(f"not a directory: {base}", file=sys.stderr)
            return 2
        return check_phase_order_tree(base)
    path = Path(argv[1])
    if path.suffix == ".json":
        ok, errors = validate_structured_json(path)
        if not ok:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print("OK: all 30 paradigms covered with structured findings")
        return 0

    text = extract_text(path)
    missing = []
    for pid, tokens in PARADIGMS.items():
        if not any(tok.lower() in text for tok in tokens):
            missing.append(pid)
    if missing:
        print(f"MISSING paradigms ({len(missing)}/30): {missing}", file=sys.stderr)
        return 1
    print("OK: all 30 paradigms covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
