from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SKILL = ROOT / "skills" / "run-build-skill"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = _load(
    "verification_obligation_planner_test",
    BUILD_SKILL / "scripts" / "plan-verification-obligations.py",
)
DERIVER = _load(
    "verification_contract_deriver_test",
    BUILD_SKILL / "scripts" / "derive-verification-contract.py",
)
ROUTE_DERIVER = _load(
    "route_build_obligation_deriver_test",
    BUILD_SKILL / "scripts" / "derive-route-build-obligations.py",
)
TASK_GRAPH_DERIVER = _load(
    "real_plan_task_graph_deriver_test",
    ROOT.parent / "plugin-dev-planner" / "skills" / "run-plugin-dev-plan" / "scripts" / "derive-task-graph.py",
)
INPUT_INJECTOR = _load(
    "execution_unit_input_injector_test",
    ROOT / "scripts" / "inject-task-inputs.py",
)
RECORDER = _load(
    "verification_evidence_recorder_test",
    BUILD_SKILL / "scripts" / "record-verification-evidence.py",
)


def _input(path: str, context: bool = False) -> dict:
    return {"path": path, "required": True, "context": context}


def _contract() -> dict:
    obligations = []
    for unit in ("a", "b"):
        obligations.extend(
            [
                {
                    "id": f"machine:{unit}",
                    "claim": f"{unit} passes deterministic checks",
                    "kind": "deterministic",
                    "risk": "high",
                    "activation": "changed",
                    "depends_on": [],
                    "inputs": [_input(f"{unit}.txt")],
                    "checker": {"id": "fixture", "argv": ["true"]},
                    "minimum_confidence": 1.0,
                    "reuse": True,
                },
                {
                    "id": f"semantic:{unit}",
                    "claim": f"{unit} preserves user intent",
                    "kind": "semantic",
                    "risk": "medium",
                    "activation": "changed",
                    "depends_on": [f"machine:{unit}"],
                    "inputs": [_input(f"{unit}.txt", context=True)],
                    "minimum_confidence": 0.8,
                    "reuse": True,
                },
            ]
        )
    obligations.append(
        {
            "id": "audit:30",
            "claim": "30-method adversarial catalog coverage",
            "kind": "audit",
            "risk": "low",
            "activation": "exhaustive",
            "depends_on": ["semantic:a", "semantic:b"],
            "inputs": [_input("a.txt", context=True), _input("b.txt", context=True)],
            "minimum_confidence": 0.8,
            "reuse": False,
        }
    )
    return {"schema_version": 1, "subject": "fixture", "obligations": obligations}


def _write_receipt(
    evidence_dir: Path,
    repo_root: Path,
    plan: dict,
    obligation_id: str,
    *,
    status: str = "PASS",
    confidence: float = 1.0,
    finding_codes: list[str] | None = None,
    suffix: str = "one",
    evidence_path: str | None = None,
) -> None:
    if evidence_path is None:
        report = repo_root / f"report-{obligation_id.replace(':', '-')}-{suffix}.txt"
        report.write_text(f"{status}:{suffix}\n", encoding="utf-8")
        evidence_path = report.name
    snapshot = PLANNER.snapshot_path(repo_root, evidence_path)
    record = next(item for item in plan["obligations"] if item["id"] == obligation_id)
    receipt = {
        "schema_version": 1,
        "subject": plan["subject"],
        "obligation_id": obligation_id,
        "fingerprint_sha256": record["fingerprint_sha256"],
        "status": status,
        "confidence": confidence,
        "verifier": {"kind": "deterministic" if obligation_id.startswith("machine:") else "llm", "id": "fixture"},
        "evidence": [{"path": evidence_path, "sha256": snapshot["sha256"]}],
        "finding_codes": finding_codes or [],
        "produced_at": "2026-07-13T00:00:00Z",
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / f"{obligation_id.replace(':', '-')}-{suffix}.json").write_text(
        json.dumps(receipt), encoding="utf-8"
    )


def _actions(plan: dict) -> dict[str, str]:
    return {item["id"]: item["action"] for item in plan["obligations"]}


def _reasons(plan: dict) -> dict[str, str]:
    return {item["id"]: item["reason"] for item in plan["obligations"]}


def test_machine_first_then_semantic_claims_share_one_context(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    assert _actions(first) == {
        "machine:a": "check",
        "semantic:a": "blocked",
        "machine:b": "check",
        "semantic:b": "blocked",
        "audit:30": "defer",
    }
    assert first["llm_batch_count"] == 0

    _write_receipt(evidence_dir, tmp_path, first, "machine:a")
    _write_receipt(evidence_dir, tmp_path, first, "machine:b")
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    assert _actions(second)["semantic:a"] == "adjudicate"
    assert _actions(second)["semantic:b"] == "adjudicate"
    assert second["llm_batch_count"] == 1
    assert second["llm_batches"][0]["obligation_ids"] == ["semantic:a", "semantic:b"]
    assert second["llm_batches"][0]["context_paths"] == ["a.txt", "b.txt"]
    assert second["cost_summary"]["avoided_executions"] == 2
    assert second["cost_summary"]["semantic_actions"] == 2


def test_exact_evidence_reuse_and_local_dependency_invalidation(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    for oid in ("machine:a", "machine:b"):
        _write_receipt(evidence_dir, tmp_path, first, oid)
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    for oid in ("semantic:a", "semantic:b"):
        _write_receipt(evidence_dir, tmp_path, second, oid)

    current = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    assert _actions(current)["machine:a"] == "reuse"
    assert _actions(current)["semantic:a"] == "reuse"
    assert _actions(current)["machine:b"] == "reuse"
    assert _actions(current)["semantic:b"] == "reuse"
    assert current["llm_batch_count"] == 0

    (tmp_path / "a.txt").write_text("alpha changed", encoding="utf-8")
    changed = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    assert _actions(changed)["machine:a"] == "check"
    assert _actions(changed)["semantic:a"] == "blocked"
    assert _actions(changed)["machine:b"] == "reuse"
    assert _actions(changed)["semantic:b"] == "reuse"


def test_low_confidence_escalates_without_agent_fanout(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    _write_receipt(evidence_dir, tmp_path, first, "machine:a")
    _write_receipt(evidence_dir, tmp_path, first, "machine:b")
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    _write_receipt(evidence_dir, tmp_path, second, "semantic:a", confidence=0.4)

    plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    assert _actions(plan)["semantic:a"] == "escalate"
    assert plan["llm_batch_count"] == 1  # only still-missing semantic:b


def test_context_budget_blocks_model_launch_instead_of_silently_spending(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, stage="release")
    _write_receipt(evidence_dir, tmp_path, first, "machine:a")
    _write_receipt(evidence_dir, tmp_path, first, "machine:b")

    plan = PLANNER.build_plan(
        _contract(), tmp_path, evidence_dir, max_context_bytes=1, stage="release"
    )
    assert plan["llm_batch_count"] == 2
    assert plan["budget_gate"]["status"] == "blocked"
    assert "semantic-context-batch-exceeds-byte-budget" in plan["budget_gate"]["reasons"]
    assert "semantic-batch-count-exceeds-run-budget" in plan["budget_gate"]["reasons"]


def test_cumulative_model_action_budget_covers_generation_and_build_only_still_builds(tmp_path: Path) -> None:
    obligations = []
    for name in ("a", "b"):
        obligations.append(
            {
                "id": f"build:{name}",
                "claim": f"build {name}",
                "kind": "generative",
                "risk": "medium",
                "activation": "changed",
                "depends_on": [],
                "inputs": [],
                "parameters": {"name": name},
                "expected_evidence_paths": [f"{name}.txt"],
                "model_required": True,
                "minimum_confidence": 0.9,
                "reuse": True,
            }
        )
    contract = {"schema_version": 1, "subject": "generation-budget", "obligations": obligations}
    plan = PLANNER.build_plan(
        contract,
        tmp_path,
        tmp_path / "evidence",
        profile="build-only",
        max_model_actions=1,
    )
    assert plan["generation_queue"] == ["build:a", "build:b"]
    assert plan["cost_summary"]["planned_model_actions"] == 2
    assert plan["budget_gate"]["status"] == "blocked"
    assert "cumulative-model-actions-exceed-run-budget" in plan["budget_gate"]["reasons"]


def test_repeated_semantic_finding_becomes_automation_candidate(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(evidence_dir, tmp_path, plan, "machine:a")
    plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(
        evidence_dir,
        tmp_path,
        plan,
        "semantic:a",
        status="FAIL",
        finding_codes=["MISSING-NAMING-GATE"],
        suffix="one",
    )
    (tmp_path / "a.txt").write_text("alpha v2", encoding="utf-8")
    next_plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(evidence_dir, tmp_path, next_plan, "machine:a", suffix="two")
    next_plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(
        evidence_dir,
        tmp_path,
        next_plan,
        "semantic:a",
        status="INCONCLUSIVE",
        finding_codes=["MISSING-NAMING-GATE"],
        suffix="two",
    )

    final = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    assert final["automation_candidates"] == [
        {
            "obligation_id": "semantic:a",
            "finding_code": "MISSING-NAMING-GATE",
            "occurrences": 2,
            "next_action": "promote-to-deterministic-checker",
        }
    ]


def test_deriver_builds_one_graph_contract_with_per_unit_claims(tmp_path: Path) -> None:
    skill_a = tmp_path / "plugins" / "demo" / "skills" / "run-a"
    skill_b = tmp_path / "plugins" / "demo" / "skills" / "ref-b"
    skill_a.mkdir(parents=True)
    skill_b.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text("a", encoding="utf-8")
    (skill_b / "SKILL.md").write_text("b", encoding="utf-8")
    (tmp_path / "a-plan.json").write_text(json.dumps({"acceptance_tier": "live"}), encoding="utf-8")
    (tmp_path / "b-plan.json").write_text(json.dumps({"acceptance_tier": "static"}), encoding="utf-8")
    (tmp_path / "a-brief.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b-brief.json").write_text("{}", encoding="utf-8")
    units = [
        {"build_plan": "a-plan.json", "skill_dir": "plugins/demo/skills/run-a", "brief": "a-brief.json"},
        {"build_plan": "b-plan.json", "skill_dir": "plugins/demo/skills/ref-b", "brief": "b-brief.json"},
    ]

    contract = DERIVER.derive_contract(units, tmp_path, "demo-build")
    ids = {item["id"] for item in contract["obligations"]}
    assert "semantic:demo:run-a:intent-fidelity" in ids
    assert "semantic:demo:ref-b:intent-fidelity" in ids
    assert "behavior:demo:run-a:live-acceptance" in ids
    assert not any(item.startswith("behavior:demo:ref-b") for item in ids)
    assert sum(item.startswith("audit:") for item in ids) == 1


def test_route_build_proofs_skip_unchanged_agents_and_invalidate_one_route(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plugin-plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "A.md").write_text("build A", encoding="utf-8")
    (plan_dir / "B.md").write_text("build B", encoding="utf-8")
    handoff = {
        "plan_dir": "plugin-plans/demo",
        "target_plugin_slug": "demo",
        "mode": "update",
        "routes": [
            {
                "id": "A",
                "build_kind": "script",
                "build_args": {"script_path": "scripts/a.py"},
                "build_target": "plugins/demo/scripts/a.py",
                "task_spec_ref": "A.md",
                "depends_on": [],
            },
            {
                "id": "B",
                "build_kind": "script",
                "build_args": {"script_path": "scripts/b.py"},
                "build_target": "plugins/demo/scripts/b.py",
                "task_spec_ref": "B.md",
                "depends_on": ["A"],
            },
        ],
    }
    handoff_path = plan_dir / "handoff-run-plugin-dev-plan.json"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    evidence_dir = tmp_path / "evidence"

    first = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    assert _actions(first)["build:A"] == "generate"
    assert _actions(first)["build:B"] == "blocked"
    assert first["generation_queue"] == ["build:A"]

    target_a = tmp_path / "plugins" / "demo" / "scripts" / "a.py"
    target_a.parent.mkdir(parents=True)
    target_a.write_text("print('a')", encoding="utf-8")
    _write_receipt(
        evidence_dir,
        tmp_path,
        first,
        "build:A",
        evidence_path="plugins/demo/scripts/a.py",
    )
    second = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    assert _actions(second)["build:A"] == "reuse"
    assert _actions(second)["build:B"] == "generate"

    target_b = tmp_path / "plugins" / "demo" / "scripts" / "b.py"
    target_b.write_text("print('b')", encoding="utf-8")
    _write_receipt(
        evidence_dir,
        tmp_path,
        second,
        "build:B",
        evidence_path="plugins/demo/scripts/b.py",
    )
    current = PLANNER.build_plan(contract, tmp_path, evidence_dir)
    assert current["generation_queue"] == []
    assert _actions(current)["build:A"] == "reuse"
    assert _actions(current)["build:B"] == "reuse"

    (plan_dir / "B.md").write_text("build B differently", encoding="utf-8")
    changed_contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    changed = PLANNER.build_plan(changed_contract, tmp_path, evidence_dir)
    assert _actions(changed)["build:A"] == "reuse"
    assert _actions(changed)["build:B"] == "generate"
    assert changed["generation_queue"] == ["build:B"]


def test_direct_tasks_join_route_proofs_and_phase_gates_do_not_spawn_agents(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plugin-plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "A.md").write_text("build A", encoding="utf-8")
    (plan_dir / "D1.md").write_text("verify the built graph", encoding="utf-8")
    task_graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "B-A", "entity_ref": "A", "execution_kind": "component-build"},
            {
                "id": "D1",
                "entity_ref": None,
                "execution_kind": "direct-task",
                "task_spec_ref": "D1.md",
                "write_scope": "plugin-plans/demo/evidence/D1.json",
                "acceptance_criterion": "D1 evidence proves graph integrity",
                "phase_ref": "P09",
            },
            {"id": "P09", "entity_ref": None, "execution_kind": "phase-gate", "phase_ref": "P09"},
        ],
        "edges": [
            {"type": "depends_on", "from": "D1", "to": "B-A"},
            {"type": "depends_on", "from": "P09", "to": "D1"},
            {"type": "produces", "from": "D1", "to": "plugin-plans/demo/evidence/D1.json"},
        ],
    }
    (plan_dir / "task-graph.json").write_text(json.dumps(task_graph), encoding="utf-8")
    handoff = {
        "plan_dir": "plugin-plans/demo",
        "target_plugin_slug": "demo",
        "task_graph_ref": {"path": "task-graph.json"},
        "routes": [
            {
                "id": "A",
                "build_kind": "script",
                "build_args": {"script_path": "scripts/a.py"},
                "build_target": "plugins/demo/scripts/a.py",
                "task_spec_ref": "A.md",
                "depends_on": [],
            }
        ],
    }
    handoff_path = plan_dir / "handoff.json"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    ids = {item["id"] for item in contract["obligations"]}
    assert ids == {"build:A", "task:D1"}

    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    assert first["generation_queue"] == ["build:A"]
    target = tmp_path / "plugins" / "demo" / "scripts" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('a')", encoding="utf-8")
    _write_receipt(
        evidence_dir,
        tmp_path,
        first,
        "build:A",
        evidence_path="plugins/demo/scripts/a.py",
    )
    second = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    assert second["generation_queue"] == ["task:D1"]


def test_real_harness_plan_claims_compile_to_order_preserving_execution_units(tmp_path: Path) -> None:
    """synthetic でなく実 handoff/13-phase plan で coverage と draft scheduler を固定する。"""
    repo_root = ROOT.parents[1]
    plan_dir = repo_root / "plugin-plans" / "harness-creator"
    handoff_path = plan_dir / "handoff-run-plugin-dev-plan.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    inventory = json.loads((plan_dir / "component-inventory.json").read_text(encoding="utf-8"))
    graph = TASK_GRAPH_DERIVER.canonicalize(TASK_GRAPH_DERIVER.derive(plan_dir))
    contract = ROUTE_DERIVER.compile_execution_units(
        handoff,
        graph,
        inventory,
        plan_dir=plan_dir,
        plan_dir_rel="plugin-plans/harness-creator",
        repo_root=repo_root,
    )
    # committed real graph は migration 前タグ無しでも、実 handoff 経由で同じ coverage へ射影。
    committed_contract = ROUTE_DERIVER.derive_contract(handoff, repo_root, handoff_path)
    assert committed_contract["claim_coverage"] == contract["claim_coverage"]
    import jsonschema
    graph_schema = json.loads((
        ROOT.parent / "plugin-dev-planner" / "skills" / "run-plugin-dev-plan" / "schemas" / "task-graph.schema.json"
    ).read_text(encoding="utf-8"))
    contract_schema = json.loads((BUILD_SKILL / "schemas" / "verification-contract.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(graph, graph_schema)
    jsonschema.validate(contract, contract_schema)

    coverage = contract["claim_coverage"]
    assert coverage | {"assignment_sha256": "ignored"} == {
        "executable_claim_count": 304,
        "assigned_claim_count": 304,
        "execution_unit_count": 48,
        "phase_gate_count": 13,
        "unassigned_task_ids": [],
        "duplicate_task_ids": [],
        "assignment_sha256": "ignored",
    }
    units = [item["parameters"]["execution_unit"] for item in contract["obligations"]]
    assert sum(unit["grouping"] == "route-phase" for unit in units) == 40
    assert sum(unit["grouping"] == "global-phase" for unit in units) == 8
    covered = [task_id for unit in units for task_id in unit["covered_task_ids"]]
    assert len(covered) == len(set(covered)) == 304
    assert all(item["id"] not in item["depends_on"] for item in contract["obligations"])
    assert len(contract["proof_projections"]) == 13
    assert all(item["dispatch"] == "none" for item in contract["proof_projections"])

    # P05 draft が P04 release に dependency-deferred にならないことを実 planner で検査。
    release_ids = {item["id"] for item in contract["obligations"] if item["stage"] == "release"}
    assert all(not (set(item["depends_on"]) & release_ids)
               for item in contract["obligations"] if item["stage"] == "draft")
    plan = PLANNER.build_plan(contract, repo_root, tmp_path / "evidence", stage="draft")
    assert plan["generation_queue"] == ["unit:global:P01"]
    assert plan["stage_gate"]["status"] == "draft-building"
    assert len(plan["stage_gate"]["pending_draft"]) == 17
    assert len(plan["stage_gate"]["deferred_to_release"]) == 31


def test_execution_unit_compiler_fails_closed_on_untyped_or_duplicate_real_claim(tmp_path: Path) -> None:
    repo_root = ROOT.parents[1]
    plan_dir = repo_root / "plugin-plans" / "harness-creator"
    handoff = json.loads((plan_dir / "handoff-run-plugin-dev-plan.json").read_text(encoding="utf-8"))
    inventory = json.loads((plan_dir / "component-inventory.json").read_text(encoding="utf-8"))
    graph = TASK_GRAPH_DERIVER.canonicalize(TASK_GRAPH_DERIVER.derive(plan_dir))
    broken = json.loads(json.dumps(graph))
    claim = next(node for node in broken["nodes"] if node.get("execution_kind") == "verification-claim")
    claim["execution_kind"] = "direct-task"
    import pytest
    with pytest.raises(ValueError, match="未対応 execution kind"):
        ROUTE_DERIVER.compile_execution_units(
            handoff, broken, inventory, plan_dir=plan_dir,
            plan_dir_rel="plugin-plans/harness-creator", repo_root=repo_root,
        )
    duplicate = json.loads(json.dumps(graph))
    duplicate["nodes"].append(dict(duplicate["nodes"][0]))
    with pytest.raises(ValueError, match="node ids"):
        ROUTE_DERIVER.compile_execution_units(
            handoff, duplicate, inventory, plan_dir=plan_dir,
            plan_dir_rel="plugin-plans/harness-creator", repo_root=repo_root,
        )


def test_real_p05_draft_unit_inputs_follow_scheduler_not_raw_p04_gate(tmp_path: Path) -> None:
    """draft reorder 後の入力解決が raw P04 gate を再適用せず、P02 proof で閉じる。"""
    repo_root = ROOT.parents[1]
    plan_dir = repo_root / "plugin-plans" / "harness-creator"
    handoff = json.loads((plan_dir / "handoff-run-plugin-dev-plan.json").read_text(encoding="utf-8"))
    inventory = json.loads((plan_dir / "component-inventory.json").read_text(encoding="utf-8"))
    graph = TASK_GRAPH_DERIVER.canonicalize(TASK_GRAPH_DERIVER.derive(plan_dir))
    contract = ROUTE_DERIVER.compile_execution_units(
        handoff, graph, inventory, plan_dir=plan_dir,
        plan_dir_rel="plugin-plans/harness-creator", repo_root=repo_root,
    )
    unit_id = "unit:route:C01:P05"
    obligation = next(item for item in contract["obligations"] if item["id"] == unit_id)
    assert obligation["parameters"]["execution_unit"]["raw_dependency_unit_ids"]
    assert all(dep.endswith(":P02") for dep in obligation["depends_on"])
    dependency_claims = [
        task_id
        for dep_id in obligation["depends_on"]
        for task_id in next(item for item in contract["obligations"] if item["id"] == dep_id)
        ["parameters"]["covered_task_ids"]
    ]
    report = tmp_path / "p02-proof.json"
    report.write_text(json.dumps({"covered_task_ids": dependency_claims}), encoding="utf-8")
    state = {task_id: {"state": "done", "route_report": str(report)} for task_id in dependency_claims}
    out = INPUT_INJECTOR.resolve_execution_unit_inputs(
        graph, state, contract, unit_id, repo_root=str(repo_root),
    )
    assert "rejected" not in out
    assert out["dependency_unit_ids"] == obligation["depends_on"]
    assert out["covered_task_ids"] == obligation["parameters"]["covered_task_ids"]

    # 実plan最大の P05/C06 入力も claimごと310 entryではなく unique path 9件。
    largest = next(item for item in contract["obligations"] if item["id"] == "unit:route:C06:P05")
    largest_dependencies = [
        task_id
        for dep_id in largest["depends_on"]
        for task_id in next(item for item in contract["obligations"] if item["id"] == dep_id)
        ["parameters"]["covered_task_ids"]
    ]
    largest_report = tmp_path / "largest-proof.json"
    largest_report.write_text(json.dumps({"covered_task_ids": largest_dependencies}), encoding="utf-8")
    largest_state = {
        task_id: {"state": "done", "route_report": str(largest_report)}
        for task_id in largest_dependencies
    }
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    raw_entries = sum(
        1 + len(INPUT_INJECTOR._producer_artifacts(nodes_by_id[task_id], graph, task_id))
        for task_id in largest_dependencies
    )
    largest_out = INPUT_INJECTOR.resolve_execution_unit_inputs(
        graph, largest_state, contract, "unit:route:C06:P05", repo_root=str(repo_root),
    )
    assert raw_entries == 310
    assert len(largest_out["injected_inputs"]) == 9
    assert all(item["producer_task_ids"] for item in largest_out["injected_inputs"])


def test_recorder_binds_default_expected_artifact_and_enables_reuse(tmp_path: Path) -> None:
    target = tmp_path / "artifact.txt"
    target.write_text("built", encoding="utf-8")
    contract = {
        "schema_version": 1,
        "subject": "record-fixture",
        "obligations": [
            {
                "id": "build:artifact",
                "claim": "artifact is built",
                "kind": "generative",
                "risk": "medium",
                "activation": "changed",
                "depends_on": [],
                "inputs": [],
                "parameters": {"spec": "v1"},
                "expected_evidence_paths": ["artifact.txt"],
                "model_required": True,
                "minimum_confidence": 0.9,
                "reuse": True,
            }
        ],
    }
    evidence_dir = tmp_path / "evidence"
    plan = PLANNER.build_plan(contract, tmp_path, evidence_dir, run_id="run-1")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert RECORDER.main(
        [
            "--plan", str(plan_path),
            "--obligation-id", "build:artifact",
            "--status", "PASS",
            "--verifier-kind", "llm",
            "--verifier-id", "fixture-builder",
            "--model-action-id", "build-artifact-1",
            "--repo-root", str(tmp_path),
            "--evidence-dir", str(evidence_dir),
            "--input-tokens", "10",
            "--output-tokens", "5",
            "--elapsed-ms", "20",
        ]
    ) == 0
    receipt_path = next(evidence_dir.glob("*.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["usage"] == {"input_tokens": 10, "output_tokens": 5, "elapsed_ms": 20}
    assert receipt["run_id"] == "run-1"
    assert receipt["model_action_id"] == "build-artifact-1"

    current = PLANNER.build_plan(contract, tmp_path, evidence_dir, run_id="run-1")
    assert _actions(current)["build:artifact"] == "reuse"
    assert current["cost_summary"]["consumed_model_actions"] == 1


def _staged_handoff(tmp_path: Path) -> tuple[dict, Path]:
    """厳格 TDD の task-graph を最小構成で再現する。

    実際の計画では P04 (受入テストを赤で固定する) が component 数と同じだけの
    direct-task を持ち、実装 (P05) の前段に丸ごと積まれる。ここではその形だけを
    2 ノードで縮約する — 検証したいのは件数ではなく phase による stage 分類である。
    """
    plan_dir = tmp_path / "plugin-plans" / "staged"
    plan_dir.mkdir(parents=True)
    (plan_dir / "A.md").write_text("build A", encoding="utf-8")
    (plan_dir / "brief.md").write_text("design brief for A", encoding="utf-8")
    (plan_dir / "red.md").write_text("author the failing acceptance suite", encoding="utf-8")
    task_graph = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "B-A", "entity_ref": "A", "execution_kind": "component-build", "phase_ref": "P05"},
            {
                "id": "P02-A-01", "entity_ref": "A", "execution_kind": "direct-task",
                "task_spec_ref": "brief.md", "phase_ref": "P02",
                "write_scope": "plugin-plans/staged/briefs/script-brief-A.json",
                "acceptance_criterion": "A の設計ブリーフが確定している",
            },
            {
                # entity_ref を持つ点が要。実グラフの P04-Cxx-01 も component を
                # 指しており、route obligation へ畳み込まれると第1稿から外れない。
                "id": "P04-A-01", "entity_ref": "A", "execution_kind": "direct-task",
                "task_spec_ref": "red.md", "phase_ref": "P04",
                "write_scope": "plugins/staged/tests/a.py",
                "acceptance_criterion": "A の受入テストが赤で固定されている",
            },
            {
                # 実装完了の集約。実グラフでは P05-x-01 が P04-x-01 に依存しており
                # (plugin-plans/guide-doc-generator/task-graph.json)、draft 側の
                # ノードが release へ繰り越したノードへぶら下がる形が実在する。
                "id": "P05-x-01", "entity_ref": None, "execution_kind": "direct-task",
                "phase_ref": "P05", "write_scope": "plugin-plans/staged/evidence/P05.json",
                "acceptance_criterion": "実装完了が集約されている",
            },
            {
                "id": "P09-x-01", "entity_ref": None, "execution_kind": "direct-task",
                "phase_ref": "P09", "write_scope": "plugin-plans/staged/evidence/P09.json",
                "acceptance_criterion": "品質保証の証跡が揃っている",
            },
        ],
        "edges": [
            {"type": "depends_on", "from": "P05-x-01", "to": "P04-A-01"},
            {"type": "depends_on", "from": "P09-x-01", "to": "P04-A-01"},
        ],
    }
    (plan_dir / "task-graph.json").write_text(json.dumps(task_graph), encoding="utf-8")
    handoff = {
        "plan_dir": "plugin-plans/staged",
        "target_plugin_slug": "staged",
        "task_graph_ref": {"path": "task-graph.json"},
        "routes": [{
            "id": "A", "build_kind": "script", "build_args": {"script_path": "scripts/a.py"},
            "build_target": "plugins/staged/scripts/a.py", "task_spec_ref": "A.md", "depends_on": [],
        }],
    }
    handoff_path = plan_dir / "handoff.json"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    return handoff, handoff_path


def test_stage_is_derived_from_phase_not_from_titles(tmp_path: Path) -> None:
    """stage は phase_ref だけで決まる。title の自然文解釈へ依存させない。"""
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    stages = {item["id"]: item["stage"] for item in contract["obligations"]}
    # P02-A-01 は entity_ref=A かつ draft 段なので build:A へ畳み込まれ、
    # 独立した obligation にはならない (畳み込み単位は component × stage)。
    assert stages == {
        "build:A": "draft",          # 成果物 + draft 段の設計ブリーフ
        "task:P05-x-01": "draft",    # 実装の集約
        "task:P04-A-01": "release",  # 実物より先に払っていた赤いスイート
        "task:P09-x-01": "release",
    }


def test_draft_stage_produces_the_artifact_without_paying_for_release_work(tmp_path: Path) -> None:
    """第1稿は『使える実体』まで走り、現物が出てから効く工程を繰り越す。

    利用者の要望「さっとまずは作って、それを使いながらブラッシュアップする」を
    機械化した中心の振る舞い。速さは検証を緩めることではなく、生成の集合を
    実体が立ち上がる範囲へ絞ることで得る。
    """
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    evidence_dir = tmp_path / "evidence"

    draft = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="draft")
    assert draft["generation_queue"] == ["build:A"]
    actions = _actions(draft)
    assert actions["task:P04-A-01"] == "defer"
    assert actions["task:P09-x-01"] == "defer"
    # P05-x-01 は draft だが P04 (繰り越し) にぶら下がる。上流を意図的に後ろへ
    # 回した以上、blocked (証拠が足りない) ではなく defer (繰り越し) として
    # 理由が読めなければならない。両者を混ぜると、昇格時に何を回収すべきか
    # 計画から引けなくなる。
    assert actions["task:P05-x-01"] == "defer"
    assert "dependency-deferred" in _reasons(draft)["task:P05-x-01"]

    release = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    assert set(release["generation_queue"]) == {"build:A", "task:P04-A-01"}


def test_draft_building_is_not_mistaken_for_a_ready_handoff(tmp_path: Path) -> None:
    """draft は実体の proof が付くまで引き渡し可能と偽装しない。"""
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    draft = PLANNER.build_plan(contract, tmp_path, (tmp_path / "evidence"), stage="draft")
    assert draft["stage_gate"]["status"] == "draft-building"
    assert draft["stage_gate"]["handoff_ready"] is False
    assert draft["stage_gate"]["pending_draft"] == ["build:A"]
    assert draft["stage_gate"]["deferred_to_release"] == [
        "task:P04-A-01", "task:P05-x-01", "task:P09-x-01",
    ]


def test_default_stage_stops_at_a_usable_draft_handoff(tmp_path: Path) -> None:
    """無指定 build は完成版へ走らず、使える第1稿を見せる地点で停止する。"""
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)

    evidence_dir = tmp_path / "evidence"
    building = PLANNER.build_plan(contract, tmp_path, evidence_dir)

    assert building["stage"] == "draft"
    assert building["generation_queue"] == ["build:A"]
    assert building["stage_gate"]["status"] == "draft-building"
    assert building["stage_gate"]["handoff_ready"] is False

    target = tmp_path / "plugins" / "staged" / "scripts" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('a')", encoding="utf-8")
    _write_receipt(
        evidence_dir,
        tmp_path,
        building,
        "build:A",
        evidence_path="plugins/staged/scripts/a.py",
    )
    plan = PLANNER.build_plan(contract, tmp_path, evidence_dir)

    assert plan["stage_gate"]["status"] == "usable-draft"
    assert plan["stage_gate"]["handoff_ready"] is True
    assert plan["stage_gate"]["next_gate"] == "build-improvement-gate.py"
    assert plan["stage_gate"]["pending_draft"] == []
    assert plan["stage_gate"]["auto_promote"] is False
    assert plan["stage_gate"]["max_repair_rounds"] == 1


def test_draft_proof_cannot_be_profile_deferred_and_zero_deferred_is_usable(
    tmp_path: Path,
) -> None:
    """draftの実体proofはactivation/profileで逃がさず、proof後だけ引き渡す。"""
    (tmp_path / "spec.txt").write_text("build one artifact", encoding="utf-8")
    contract = {
        "schema_version": 1,
        "subject": "draft-only-fixture",
        "obligations": [
            {
                "id": "build:only",
                "claim": "a usable artifact exists",
                "kind": "generative",
                "stage": "draft",
                "risk": "high",
                "activation": "exhaustive",
                "depends_on": [],
                "inputs": [_input("spec.txt")],
                "model_required": True,
                "minimum_confidence": 1.0,
                "reuse": True,
            }
        ],
    }
    evidence_dir = tmp_path / "evidence"

    building = PLANNER.build_plan(contract, tmp_path, evidence_dir, profile="incremental")
    assert _actions(building)["build:only"] == "generate"
    assert building["stage_gate"]["status"] == "draft-building"
    assert building["stage_gate"]["handoff_ready"] is False
    assert building["stage_gate"]["pending_draft"] == ["build:only"]

    artifact = tmp_path / "artifact.txt"
    artifact.write_text("usable", encoding="utf-8")
    _write_receipt(
        evidence_dir,
        tmp_path,
        building,
        "build:only",
        evidence_path="artifact.txt",
    )
    ready = PLANNER.build_plan(contract, tmp_path, evidence_dir, profile="incremental")

    assert _actions(ready)["build:only"] == "reuse"
    assert ready["stage_gate"]["deferred_to_release"] == []
    assert ready["stage_gate"]["status"] == "usable-draft"
    assert ready["stage_gate"]["handoff_ready"] is True
    assert ready["stage_gate"]["next_gate"] == "build-improvement-gate.py"


def test_promotion_to_release_reuses_draft_proofs_instead_of_rebuilding(tmp_path: Path) -> None:
    """draft で得た証明は release でそのまま効く。

    stage を fingerprint へ含めない設計の理由がこれである。含めてしまうと昇格の
    たびに全 route を作り直すことになり、二段階にした意味 (待ち時間の短縮) が
    そっくり失われる。
    """
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    evidence_dir = tmp_path / "evidence"
    draft = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="draft")

    target = tmp_path / "plugins" / "staged" / "scripts" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('a')", encoding="utf-8")
    _write_receipt(evidence_dir, tmp_path, draft, "build:A",
                   evidence_path="plugins/staged/scripts/a.py")

    release = PLANNER.build_plan(contract, tmp_path, evidence_dir, stage="release")
    actions = _actions(release)
    assert actions["build:A"] == "reuse"
    # 昇格で新たに払うのは繰り越した分だけ (下流 P05-x-01 / P09-x-01 は
    # P04 の証明が付いた次の周回で ready になる)。
    assert release["generation_queue"] == ["task:P04-A-01"]


def test_unstaged_obligations_run_in_draft_so_nothing_is_silently_dropped(tmp_path: Path) -> None:
    """stage 未宣言は draft 扱い。

    未分類を release へ倒すと、stage を知らない旧 contract を draft で回した瞬間に
    全件 defer され「何も作られていないのに何も落ちていない」計画が成立する。
    分類漏れは遅くなる側へ倒す。
    """
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    plan = PLANNER.build_plan(_contract(), tmp_path, (tmp_path / "evidence"), stage="draft")
    assert all(item["stage"] == "draft" for item in plan["obligations"])
    assert _actions(plan)["machine:a"] == "check"


def test_draft_defers_semantic_and_audit_even_when_unstaged(tmp_path: Path) -> None:
    """第1稿は実体と決定論ゲートまで。意味裁定・監査は現物が出てから効く。"""
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    plan = PLANNER.build_plan(_contract(), tmp_path, (tmp_path / "evidence"), stage="draft")
    actions = _actions(plan)
    assert actions["semantic:a"] == "defer"
    assert actions["audit:30"] == "defer"
    assert plan["llm_batch_count"] == 0


def test_release_phase_nodes_do_not_fold_into_the_route_obligation(tmp_path: Path) -> None:
    """entity_ref を持つ release 段 node は route build へ畳み込まない。

    畳み込みの単位は component ではなく「component × stage」である。実グラフの
    P04-Cxx-01 は component を entity_ref に持つため、component 単位で畳むと
    stage=draft の route build 指示に「受入テストを赤で固定する」が同梱され、
    第1稿から外れない。stage を分けても待ち時間が縮まらない状態が黙って成立する。
    """
    handoff, handoff_path = _staged_handoff(tmp_path)
    contract = ROUTE_DERIVER.derive_contract(handoff, tmp_path, handoff_path)
    ids = {item["id"] for item in contract["obligations"]}
    assert "task:P04-A-01" in ids
    route = next(item for item in contract["obligations"] if item["id"] == "build:A")
    folded = {str(node.get("id")) for node in route["parameters"]["task_nodes"]}
    assert "P04-A-01" not in folded
    assert "P02-A-01" in folded  # draft 段の設計ブリーフは route build と一体で扱う
    assert "B-A" in folded       # component-build は phase_ref を問わず route 本体
