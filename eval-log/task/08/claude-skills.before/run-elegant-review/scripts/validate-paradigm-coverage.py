#!/usr/bin/env python3
# /// script
# name: validate-paradigm-coverage
# purpose: Validate that elegant-review outputs cover all 30 paradigms with structured findings.
# inputs:
#   - argv: review.md or findings.json
# outputs:
#   - stdout: OK message
#   - stderr: missing paradigm or schema errors
#   - exit: 0=OK / 1=coverage failure / 2=usage error
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""Check whether a review output covers all 30 paradigms.

Usage:
  validate-paradigm-coverage.py <review.md | findings.json>

Exit codes:
  0 -> all 30 covered with structured findings or markdown mentions
  1 -> missing paradigms detected
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
    2: ("deductive", "A-logical", "elegant-logical-structural-analyst"),
    3: ("inductive", "A-logical", "elegant-logical-structural-analyst"),
    4: ("abductive", "A-logical", "elegant-logical-structural-analyst"),
    5: ("vertical", "A-logical", "elegant-logical-structural-analyst"),
    6: ("decomposition", "B-structural", "elegant-logical-structural-analyst"),
    7: ("mece", "B-structural", "elegant-logical-structural-analyst"),
    8: ("two-axis", "B-structural", "elegant-logical-structural-analyst"),
    9: ("process-thinking", "B-structural", "elegant-logical-structural-analyst"),
    10: ("meta-thinking", "C-meta", "elegant-meta-divergent-analyst"),
    11: ("abstraction", "C-meta", "elegant-meta-divergent-analyst"),
    12: ("double-loop", "C-meta", "elegant-meta-divergent-analyst"),
    13: ("brainstorming", "D-divergent", "elegant-meta-divergent-analyst"),
    14: ("lateral", "D-divergent", "elegant-meta-divergent-analyst"),
    15: ("paradox", "D-divergent", "elegant-meta-divergent-analyst"),
    16: ("analogy", "D-divergent", "elegant-meta-divergent-analyst"),
    17: ("what-if", "D-divergent", "elegant-meta-divergent-analyst"),
    18: ("beginner-mind", "D-divergent", "elegant-meta-divergent-analyst"),
    19: ("systems-thinking", "E-system", "elegant-system-strategic-analyst"),
    20: ("causal-analysis", "E-system", "elegant-system-strategic-analyst"),
    21: ("causal-loop", "E-system", "elegant-system-strategic-analyst"),
    22: ("trade-on", "F-strategic", "elegant-system-strategic-analyst"),
    23: ("positive-sum", "F-strategic", "elegant-system-strategic-analyst"),
    24: ("value-proposition", "F-strategic", "elegant-system-strategic-analyst"),
    25: ("strategic", "F-strategic", "elegant-system-strategic-analyst"),
    26: ("why-thinking", "G-problem", "elegant-system-strategic-analyst"),
    27: ("improvement", "G-problem", "elegant-system-strategic-analyst"),
    28: ("hypothesis", "G-problem", "elegant-system-strategic-analyst"),
    29: ("issue-thinking", "G-problem", "elegant-system-strategic-analyst"),
    30: ("kj-method", "G-problem", "elegant-system-strategic-analyst"),
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

    missing = [pid for pid in PARADIGMS if pid not in by_id]
    if missing:
        errors.append(f"missing paradigm_findings ids: {missing}")

    valid_conditions = {"C1", "C2", "C3", "C4"}
    valid_severities = {"critical", "high", "medium", "low"}
    valid_scopes = {"target-specific", "reusable-pattern", "governance-rule", "lint-candidate", "template-candidate"}
    valid_reuse_surfaces = {"template", "rubric", "lint", "hook", "reference", "manifest", "runbook", "none"}
    valid_source_tiers = {
        "article-text",
        "image-derived",
        "code-unavailable",
        "code-verified",
        "internal",
        "external-spec",
    }
    valid_migration_buckets = {
        "always-on",
        "ref",
        "run",
        "wrap",
        "assign",
        "delegate",
        "hook",
        "docs",
        "mcp",
        "none",
    }
    valid_runtime_variants = {"mac", "linux", "windows", "unknown", "any", "none"}
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
            if not str(issue.get("description", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing description")
            if not str(issue.get("suggested_fix", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing suggested_fix")
            if issue.get("source_tier") not in valid_source_tiers:
                errors.append(f"paradigm {pid} issue {i}: invalid source_tier")
            if not str(issue.get("trace_evidence", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing trace_evidence")
            if issue.get("migration_bucket") not in valid_migration_buckets:
                errors.append(f"paradigm {pid} issue {i}: invalid migration_bucket")
            if issue.get("runtime_variant") not in valid_runtime_variants:
                errors.append(f"paradigm {pid} issue {i}: invalid runtime_variant")
            if not str(issue.get("dependency_assumption", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing dependency_assumption")
            if not str(issue.get("negative_case", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing negative_case")
            if not str(issue.get("re_audit_trigger", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing re_audit_trigger")
            if "finding_scope" in issue and issue.get("finding_scope") not in valid_scopes:
                errors.append(f"paradigm {pid} issue {i}: invalid finding_scope")
            if "reuse_surface" in issue and issue.get("reuse_surface") not in valid_reuse_surfaces:
                errors.append(f"paradigm {pid} issue {i}: invalid reuse_surface")

    variable_abstraction = data.get("variable_abstraction")
    if not isinstance(variable_abstraction, dict):
        errors.append("missing variable_abstraction")
    else:
        variables = variable_abstraction.get("variables")
        if not isinstance(variables, list) or not variables:
            errors.append("variable_abstraction.variables must be non-empty")
        else:
            for idx, var in enumerate(variables):
                if not isinstance(var, dict):
                    errors.append(f"variable_abstraction.variables[{idx}] must be object")
                    continue
                for key in ("name", "meaning", "default", "required", "not_applicable_when"):
                    if key not in var:
                        errors.append(f"variable_abstraction.variables[{idx}] missing {key}")
                if not str(var.get("name", "")).startswith("{{"):
                    errors.append(f"variable_abstraction.variables[{idx}].name must be template variable")
        source_trace = variable_abstraction.get("source_trace")
        if not isinstance(source_trace, list):
            errors.append("variable_abstraction.source_trace must be a list")

    return not errors, errors


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: validate-paradigm-coverage.py <file>", file=sys.stderr)
        return 2
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
