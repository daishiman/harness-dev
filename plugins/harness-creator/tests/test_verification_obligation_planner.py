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


def test_machine_first_then_semantic_claims_share_one_context(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"

    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
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
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
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
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    for oid in ("machine:a", "machine:b"):
        _write_receipt(evidence_dir, tmp_path, first, oid)
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    for oid in ("semantic:a", "semantic:b"):
        _write_receipt(evidence_dir, tmp_path, second, oid)

    current = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    assert _actions(current)["machine:a"] == "reuse"
    assert _actions(current)["semantic:a"] == "reuse"
    assert _actions(current)["machine:b"] == "reuse"
    assert _actions(current)["semantic:b"] == "reuse"
    assert current["llm_batch_count"] == 0

    (tmp_path / "a.txt").write_text("alpha changed", encoding="utf-8")
    changed = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    assert _actions(changed)["machine:a"] == "check"
    assert _actions(changed)["semantic:a"] == "blocked"
    assert _actions(changed)["machine:b"] == "reuse"
    assert _actions(changed)["semantic:b"] == "reuse"


def test_low_confidence_escalates_without_agent_fanout(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(evidence_dir, tmp_path, first, "machine:a")
    _write_receipt(evidence_dir, tmp_path, first, "machine:b")
    second = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(evidence_dir, tmp_path, second, "semantic:a", confidence=0.4)

    plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    assert _actions(plan)["semantic:a"] == "escalate"
    assert plan["llm_batch_count"] == 1  # only still-missing semantic:b


def test_context_budget_blocks_model_launch_instead_of_silently_spending(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    first = PLANNER.build_plan(_contract(), tmp_path, evidence_dir)
    _write_receipt(evidence_dir, tmp_path, first, "machine:a")
    _write_receipt(evidence_dir, tmp_path, first, "machine:b")

    plan = PLANNER.build_plan(_contract(), tmp_path, evidence_dir, max_context_bytes=1)
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

    first = PLANNER.build_plan(contract, tmp_path, evidence_dir)
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
    second = PLANNER.build_plan(contract, tmp_path, evidence_dir)
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
    first = PLANNER.build_plan(contract, tmp_path, evidence_dir)
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
    second = PLANNER.build_plan(contract, tmp_path, evidence_dir)
    assert second["generation_queue"] == ["task:D1"]


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
