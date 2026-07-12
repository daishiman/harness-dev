#!/usr/bin/env python3
# /// script
# name: evaluate-plan
# purpose: Run plugin-dev-planner deterministic gates and emit plan-findings.json for assign-plugin-plan-evaluator.
# inputs:
#   - argv: --plan-dir DIR [--output FILE]
# outputs:
#   - plan-findings.json
#   - exit: 0=PASS / 1=FAIL / 2=usage or unreadable input
# contexts: [C, E]
# network: false
# write-scope: output findings file only
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Deterministic runner for assign-plugin-plan-evaluator.

The skill prompt remains the orchestration contract; this script is the mechanical
path used by tests and by agents that need reproducible findings.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


CONDITION_IDS = {
    "C1": "no_contradiction",
    "C2": "no_missing",
    "C3": "consistent",
    "C4": "dependency_integrity",
}
CONDITION_LABELS = {
    "C1": "矛盾なし",
    "C2": "漏れなし",
    "C3": "整合性あり",
    "C4": "依存関係整合",
}
REQUIRED_PLUGIN_SURFACES = (
    "manifest",
    "composition",
    "harness_eval",
    "references_config_assets",
    "schemas",
    "vendor",
    "mcp_app_connector",
    "notion_config",
)


def _paths() -> tuple[Path, Path, Path]:
    script = Path(__file__).resolve()
    evaluator_skill = script.parents[1]
    plugin_root = script.parents[3]
    repo_root = script.parents[5]
    run_skill = plugin_root / "skills" / "run-plugin-dev-plan"
    return evaluator_skill, run_skill, repo_root


def _load_thresholds(evaluator_skill: Path) -> dict:
    """plan-rubric.json の global_thresholds を SSOT として読む。

    閾値をハードコードせず rubric 正本から読むことで宣言↔実装の drift を防ぐ
    (rubric が medium_max を宣言しても runner が見なければ宣言が空文化する穴を封鎖。
    parity は test_gate_parity.py の thresholds テストで機械担保)。
    """
    rubric = json.loads(
        (evaluator_skill / "references" / "plan-rubric.json").read_text(encoding="utf-8")
    )
    gt = rubric["global_thresholds"]
    return {
        "high_max": int(gt["high_max"]),
        "medium_max": int(gt["medium_max"]),
        "all_deterministic_gates_exit0": bool(gt["all_deterministic_gates_exit0"]),
    }


def _verdict(high_count: int, medium_count: int, all_gates_exit0: bool, thresholds: dict) -> str:
    """global_thresholds 駆動の verdict 判定 (副作用なし=単体テスト可能)。"""
    passed = (
        high_count <= thresholds["high_max"]
        and medium_count <= thresholds["medium_max"]
        and (all_gates_exit0 or not thresholds["all_deterministic_gates_exit0"])
    )
    return "PASS" if passed else "FAIL"


def _run_gate(gate: dict, repo_root: Path) -> dict:
    proc = subprocess.run(
        gate["command"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "id": gate["id"],
        "name": gate["name"],
        "command": [str(x) for x in gate["command"]],
        "exit_code": int(proc.returncode),
        "conditions": gate["conditions"],
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _gate_defs(run_skill: Path, plan_dir: Path) -> list[dict]:
    scripts = run_skill / "scripts"
    py = sys.executable or "python3"
    inventory = plan_dir / "component-inventory.json"
    handoff = plan_dir / "handoff-run-plugin-dev-plan.json"
    return [
        {
            "id": "G1",
            "name": "verify-index-topsort",
            "conditions": ["C4"],
            "command": [py, str(scripts / "verify-index-topsort.py"), str(plan_dir)],
        },
        {
            "id": "G2",
            "name": "detect-unassigned",
            "conditions": ["C2", "C4"],
            "command": [
                py,
                str(scripts / "detect-unassigned.py"),
                "--inventory",
                str(inventory),
                "--specs-dir",
                str(plan_dir),
            ],
        },
        {
            "id": "G3",
            "name": "check-spec-frontmatter",
            "conditions": ["C2", "C3"],
            "command": [py, str(scripts / "check-spec-frontmatter.py"), "--specs-dir", str(plan_dir)],
        },
        {
            "id": "G4",
            "name": "check-spec-gates",
            "conditions": ["C2", "C3"],
            "command": [py, str(scripts / "check-spec-gates.py"), "--specs-dir", str(plan_dir)],
        },
        {
            "id": "G5",
            "name": "check-spec-matrix-coverage-self-test",
            "conditions": ["C3"],
            "command": [py, str(scripts / "check-spec-matrix-coverage.py"), "--self-test"],
        },
        {
            "id": "G6",
            "name": "check-spec-matrix-coverage-plan",
            "conditions": ["C3"],
            "command": [py, str(scripts / "check-spec-matrix-coverage.py"), str(plan_dir)],
        },
        {
            "id": "G7",
            "name": "check-surface-inventory",
            "conditions": ["C2"],
            "command": [py, str(scripts / "check-surface-inventory.py"), str(inventory)],
        },
        {
            "id": "G8",
            "name": "check-build-handoff",
            "conditions": ["C1", "C4"],
            "command": [py, str(scripts / "check-build-handoff.py"), str(handoff)],
        },
        {
            "id": "G9",
            "name": "check-requirements-coverage",
            "conditions": ["C2"],
            "command": [py, str(scripts / "check-requirements-coverage.py"), str(plan_dir)],
        },
        {
            # install 携帯性 (F8): 共有 script の plugin-root hoist + build_target の plugin 内自己完結。
            # plan の依存整合 (C4) に直結する plan-scoped ゲート。build-handoff(G8) と同型で、
            # 評価器が回さないと携帯性の壊れた plan が独立評価を PASS しうる (S2 Goodhart 穴)。
            "id": "G10",
            "name": "check-runtime-portability",
            "conditions": ["C4"],
            "command": [py, str(scripts / "check-runtime-portability.py"), str(plan_dir)],
        },
        {
            # デフォルト成果物 task-graph.json の 10 検査 (DAG 非循環/orphan 0/producer 一意/
            # inventory 矛盾 0/dangling 端点 0/非正準拒否)。task-graph は成果物の第一級 (§9) ゆえ
            # 依存グラフ整合 (C4) に直結する plan-scoped ゲート。build-handoff(G8)/runtime(G10) と同型で、
            # 評価器が回さないと壊れた依存グラフ (循環/orphan) を持つ plan が独立評価を PASS しうる。
            "id": "G11",
            "name": "validate-task-graph",
            "conditions": ["C4"],
            "command": [py, str(scripts / "validate-task-graph.py"), str(plan_dir)],
        },
    ]


def _load_inventory(plan_dir: Path) -> tuple[dict, list[str]]:
    path = plan_dir / "component-inventory.json"
    if not path.is_file():
        return {}, [f"component-inventory.json not found: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"component-inventory.json parse error: {exc}"]
    if not isinstance(data, dict):
        return {}, ["component-inventory.json root is not an object"]
    return data, []


def _surface_findings(plan_dir: Path) -> list[dict]:
    inventory, errors = _load_inventory(plan_dir)
    findings: list[dict] = []
    for err in errors:
        findings.append({
            "severity": "high",
            "bucket": "C2",
            "observation": err,
            "suggested_fix": "Emit a component-inventory.json object with plugin_level_surfaces.",
            "evidence": [str(plan_dir / "component-inventory.json")],
        })
    if errors:
        return findings

    surfaces = inventory.get("plugin_level_surfaces")
    if not isinstance(surfaces, dict) or not surfaces:
        return [{
            "severity": "high",
            "bucket": "C2",
            "observation": "plugin_level_surfaces is missing or empty, so plugin-level manifest/harness/composition coverage is not evaluated.",
            "suggested_fix": "Add plugin_level_surfaces with required=true or omitted_reason for each required surface.",
            "evidence": ["component-inventory.json"],
        }]

    for key in REQUIRED_PLUGIN_SURFACES:
        item = surfaces.get(key)
        if not isinstance(item, dict):
            findings.append({
                "severity": "high",
                "bucket": "C2",
                "observation": f"plugin_level_surfaces.{key} is missing.",
                "suggested_fix": f"Record plugin_level_surfaces.{key} with required=true or an omitted_reason.",
                "evidence": ["component-inventory.json"],
            })
            continue
        required = item.get("required")
        omitted = item.get("omitted_reason")
        if required is False and not (isinstance(omitted, str) and omitted.strip()):
            findings.append({
                "severity": "high",
                "bucket": "C2",
                "observation": f"plugin_level_surfaces.{key} is omitted without a reason.",
                "suggested_fix": f"Add a non-empty omitted_reason for {key}.",
                "evidence": ["component-inventory.json"],
            })
        elif required is not True and not (isinstance(omitted, str) and omitted.strip()):
            findings.append({
                "severity": "high",
                "bucket": "C2",
                "observation": f"plugin_level_surfaces.{key} does not state required=true or omitted_reason.",
                "suggested_fix": f"Make {key} explicit so the plan cannot silently skip that surface.",
                "evidence": ["component-inventory.json"],
            })
    return findings


def _gate_findings(gate_results: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for result in gate_results:
        if result["exit_code"] == 0:
            continue
        for condition in result["conditions"]:
            findings.append({
                "severity": "high",
                "bucket": condition,
                "observation": f"{result['name']} exited {result['exit_code']}.",
                "suggested_fix": "Fix the generated plan artifact and rerun assign-plugin-plan-evaluator.",
                "evidence": [result.get("stderr") or result.get("stdout") or "no output"],
            })
    return findings


def _conditions(gate_results: list[dict], findings: list[dict]) -> dict:
    out: dict = {}
    for cid, condition_id in CONDITION_IDS.items():
        related_gates = [g for g in gate_results if cid in g["conditions"]]
        related_findings = [f for f in findings if f["bucket"] == cid and f["severity"] == "high"]
        failed_gates = [g["name"] for g in related_gates if g["exit_code"] != 0]
        status = "FAIL" if failed_gates or related_findings else "PASS"
        evidence = [f"{g['name']} exit={g['exit_code']}" for g in related_gates]
        evidence += [f["observation"] for f in related_findings]
        if status == "PASS":
            summary = f"{CONDITION_LABELS[cid]}: deterministic gates passed"
        else:
            summary = f"{CONDITION_LABELS[cid]}: failures detected"
        out[cid] = {
            "id": condition_id,
            "status": status,
            "summary": summary,
            "evidence": evidence,
        }
    return out


def evaluate(plan_dir: Path, output: Path) -> tuple[int, dict]:
    evaluator_skill, run_skill, repo_root = _paths()
    gate_results = [_run_gate(g, repo_root) for g in _gate_defs(run_skill, plan_dir)]
    findings = _gate_findings(gate_results)
    findings.extend(_surface_findings(plan_dir))

    if not findings:
        findings.append({
            "severity": "info",
            "bucket": "C1-C4",
            "observation": "All deterministic gates exited 0 and plugin-level surfaces were explicit.",
            "evidence": [str(plan_dir)],
        })

    conditions = _conditions(gate_results, findings)
    thresholds = _load_thresholds(evaluator_skill)
    high_count = sum(1 for f in findings if f["severity"] == "high")
    medium_count = sum(1 for f in findings if f["severity"] == "medium")
    all_gates_exit0 = all(g["exit_code"] == 0 for g in gate_results)
    verdict = _verdict(high_count, medium_count, all_gates_exit0, thresholds)
    data = {
        "plan_dir": str(plan_dir),
        "evaluator": {
            "name": "assign-plugin-plan-evaluator",
            "version": "0.2.0",
            "context": "fork",
        },
        "verdict": verdict,
        "conditions": conditions,
        "gate_results": gate_results,
        "findings": findings,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return (0 if verdict == "PASS" else 1), data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate a plugin-dev-planner plan and emit plan-findings.json")
    ap.add_argument("--plan-dir", required=True, help="Plan directory containing index.md and component-inventory.json")
    ap.add_argument("--output", default=None, help="Output findings path (default: <PLAN_DIR>/plan-findings.json)")
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir).resolve()
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    output = Path(args.output).resolve() if args.output else plan_dir / "plan-findings.json"
    code, data = evaluate(plan_dir, output)
    sys.stdout.write(f"{data['verdict']}: wrote {output}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
