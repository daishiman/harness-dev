from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
PLAN_DIGEST = "sha256:" + "a" * 64
C11_DIGEST = "sha256:" + "c" * 64
READINESS_SOURCE_DIGEST = "sha256:" + "b" * 64


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_script(name: str, *args: object) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if name == "build-requirements-handoff.py":
        env["DEV_GRAPH_TEST_VALIDATOR_OVERRIDES"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )


def absolute_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in absolute_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in absolute_strings(child)]
    if isinstance(value, str) and (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):
        return [value]
    return []


def ready_node(node_id: str, **overrides: object) -> dict:
    node = {
        "graph_node_id": node_id,
        "artifact_kind": "task",
        "title": node_id,
        "file_path": f"tasks/{node_id}.md",
        "status": "active",
        "confirmation_status": "confirmed",
        "evaluation_status": "pass",
        "implementation_readiness": {"status": "complete", "missing_sections": []},
        "depends_on": [],
        "resource_scope": [],
        "source_lineage": {"source_digest": "plan-digest", "source_path": f"task-specs/{node_id}.md"},
    }
    node.update(overrides)
    return node


def test_schedule_cli_materializes_receipt_anchor_and_c17_verifies(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    leases = tmp_path / "leases.json"
    schedule = tmp_path / "eval-log/schedule.json"
    goal = tmp_path / "eval-log/goal.json"
    progress = tmp_path / "eval-log/progress.json"
    intermediate = tmp_path / "eval-log/intermediate.jsonl"
    verdict = tmp_path / "eval-log/c17.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("DONE", status="done"),
                ready_node("T1", depends_on=["DONE"], resource_scope=["api"]),
                ready_node("T2", resource_scope=["web"]),
                ready_node("T3", resource_scope=["api"]),
                ready_node("BLOCKED", confirmation_status="pending"),
            ]
        },
    )
    write_json(leases, {"leases": []})
    graph_before = hashlib.sha256(graph.read_bytes()).hexdigest()
    leases_before = hashlib.sha256(leases.read_bytes()).hexdigest()

    created = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--max-parallel", 2,
        "--out", schedule,
        "--goal-spec", goal,
        "--goal-progress", progress,
        "--goal-intermediate", intermediate,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["ready_set"]["tasks"] == ["T1", "T2", "T3"]
    assert actual["batches"]["tasks"] == [["T1", "T2"], ["T3"]]
    assert actual["conflict_pairs"] == [
        {"kind": "tasks", "nodes": ["T1", "T3"], "resources": ["api"]}
    ]
    assert "BLOCKED" not in actual["ready_set"]["tasks"]
    assert len({item["suggested_branch"] for item in actual["assignment_hints"]}) == 3
    assert hashlib.sha256(graph.read_bytes()).hexdigest() == graph_before
    assert hashlib.sha256(leases.read_bytes()).hexdigest() == leases_before

    repeated = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--max-parallel", 2,
        "--out", schedule,
        "--goal-spec", goal,
        "--goal-progress", progress,
        "--goal-intermediate", intermediate,
    )
    assert repeated.returncode == 0, repeated.stderr
    repeated_schedule = json.loads(schedule.read_text(encoding="utf-8"))
    assert (
        repeated_schedule["input_digests"]["schedule"]
        == actual["input_digests"]["schedule"]
    )
    assert repeated_schedule["ready_set"] == actual["ready_set"]
    assert repeated_schedule["batches"] == actual["batches"]
    assert hashlib.sha256(graph.read_bytes()).hexdigest() == graph_before
    assert hashlib.sha256(leases.read_bytes()).hexdigest() == leases_before

    checked = run_script(
        "validate-schedule-receipt.py",
        "--graph", graph,
        "--schedule", schedule,
        "--leases", leases,
        "--max-parallel", 2,
        "--out", verdict,
    )
    assert checked.returncode == 0, checked.stderr
    c17 = json.loads(verdict.read_text(encoding="utf-8"))
    assert c17["verifier"] == "dev-graph-parallel-safety-verifier"
    assert c17["component"] == "C17"
    assert c17["verdict"] == "PASS"
    assert c17["findings"] == []
    assert c17["schedule_ref"] == "schedule.json"
    assert absolute_strings(c17) == []
    assert absolute_strings(json.loads(progress.read_text(encoding="utf-8"))) == []

    anchor = run_script(
        "validate-goal-seek-runtime.py",
        "--goal-spec", goal,
        "--progress", progress,
        "--intermediate", intermediate,
    )
    assert anchor.returncode == 0, anchor.stderr
    progress_value = json.loads(progress.read_text(encoding="utf-8"))
    progress_value["original_goal_hash"] = "0" * 64
    write_json(progress, progress_value)
    tampered_anchor = run_script(
        "validate-goal-seek-runtime.py",
        "--goal-spec", goal,
        "--progress", progress,
        "--intermediate", intermediate,
    )
    assert tampered_anchor.returncode == 1
    assert "progress original_goal_hash mismatch" in tampered_anchor.stderr


def test_c17_rejects_tampered_schedule_and_stale_graph(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    schedule = tmp_path / "schedule.json"
    write_json(graph, {"nodes": [ready_node("T1", resource_scope=["api"]) ]})
    assert run_script("schedule-graph.py", "--graph", graph, "--out", schedule).returncode == 0
    value = json.loads(schedule.read_text(encoding="utf-8"))
    value["ready_set"]["tasks"] = []
    write_json(schedule, value)
    rejected = run_script("validate-schedule-receipt.py", "--graph", graph, "--schedule", schedule)
    assert rejected.returncode == 1
    receipt = json.loads(rejected.stdout)
    assert receipt["verdict"] == "FAIL"
    assert {item["field"] for item in receipt["findings"] if item["kind"] == "schedule_mismatch"} >= {"ready_set"}


def c28_ready(
    *items: tuple[str, bool], conflicts: list[dict] | None = None
) -> dict:
    return {
        "op": "ready",
        "ready_set": [
            {
                "external_ref": node_id,
                "edge_parity": {
                    "confirmed": confirmed,
                    "expected_status": "open",
                    "actual_status": "open",
                    "expected_depends_on": [],
                    "actual_depends_on": [],
                    "missing_edges": [],
                    "unexpected_edges": [],
                },
            }
            for node_id, confirmed in items
        ],
        "conflicts": conflicts or [],
        "unmapped": [],
    }


def test_schedule_scope_uses_fixed_point_feature_dependency_closure(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    schedule = tmp_path / "schedule.json"
    verdict = tmp_path / "c17.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("BASE", status="done", artifact_kind="feature"),
                ready_node(
                    "FEATURE",
                    artifact_kind="feature",
                    depends_on=["BASE"],
                    resource_scope=["feature"],
                ),
                ready_node(
                    "TASK-1",
                    parent_feature="FEATURE",
                    depends_on=["BASE"],
                    resource_scope=["api"],
                ),
                ready_node(
                    "TASK-2", parent_feature="FEATURE", resource_scope=["web"]
                ),
                ready_node("UNRELATED", resource_scope=["other"]),
            ]
        },
    )
    created = run_script(
        "schedule-graph.py",
        "--graph",
        graph,
        "--scope",
        "FEATURE",
        "--out",
        schedule,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["scope"] == "FEATURE"
    assert actual["scope_node_ids"] == ["BASE", "FEATURE", "TASK-1", "TASK-2"]
    assert actual["ready_set"] == {
        "features": ["FEATURE"],
        "tasks": ["TASK-1", "TASK-2"],
    }
    assert "UNRELATED" not in actual["scope_node_ids"]

    checked = run_script(
        "validate-schedule-receipt.py",
        "--graph",
        graph,
        "--schedule",
        schedule,
        "--scope",
        "FEATURE",
        "--out",
        verdict,
    )
    assert checked.returncode == 0, checked.stderr
    wrong_scope = run_script(
        "validate-schedule-receipt.py",
        "--graph",
        graph,
        "--schedule",
        schedule,
        "--scope",
        "UNRELATED",
    )
    assert wrong_scope.returncode == 1
    missing = run_script(
        "schedule-graph.py", "--graph", graph, "--scope", "DOES-NOT-EXIST"
    )
    assert missing.returncode == 2
    assert "scope node does not exist" in missing.stderr


def test_beads_ready_requires_confirmed_c28_parity_and_c17_rechecks_it(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    ready = tmp_path / "c28-ready.json"
    schedule = tmp_path / "schedule.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("BEADS-OK", tracker_binding="beads"),
                ready_node("BEADS-CONFLICT", tracker_binding="beads"),
            ]
        },
    )
    write_json(
        ready,
        c28_ready(
            ("BEADS-OK", True),
            ("BEADS-CONFLICT", False),
            conflicts=[
                {
                    "graph_node_id": "BEADS-CONFLICT",
                    "reason": "Beads parity conflict",
                }
            ],
        ),
    )
    created = run_script(
        "schedule-graph.py",
        "--graph",
        graph,
        "--ready-source",
        "bd-bridge",
        "--ready-json",
        ready,
        "--out",
        schedule,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["ready_set"]["tasks"] == ["BEADS-OK"]
    assert {
        item.get("graph_node_id") for item in actual["source_conflicts"]
    } == {"BEADS-CONFLICT"}

    checked = run_script(
        "validate-schedule-receipt.py",
        "--graph",
        graph,
        "--schedule",
        schedule,
        "--ready-source",
        "bd-bridge",
        "--ready-json",
        ready,
    )
    assert checked.returncode == 0, checked.stderr
    wrong_authority = run_script(
        "validate-schedule-receipt.py", "--graph", graph, "--schedule", schedule
    )
    assert wrong_authority.returncode == 1

    tampered = json.loads(schedule.read_text(encoding="utf-8"))
    tampered["ready_set"]["tasks"].append("BEADS-CONFLICT")
    write_json(schedule, tampered)
    rejected = run_script(
        "validate-schedule-receipt.py",
        "--graph",
        graph,
        "--schedule",
        schedule,
        "--ready-source",
        "bd-bridge",
        "--ready-json",
        ready,
    )
    assert rejected.returncode == 1
    findings = json.loads(rejected.stdout)["findings"]
    assert any(item["kind"] == "unconfirmed_parity_scheduled" for item in findings)


def test_c28_confirmed_flag_cannot_override_non_exact_status_or_edges(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    ready = tmp_path / "c28-ready.json"
    schedule = tmp_path / "schedule.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("EXACT", tracker_binding="beads"),
                ready_node("FORGED", tracker_binding="beads"),
            ]
        },
    )
    evidence = c28_ready(("EXACT", True), ("FORGED", True))
    evidence["ready_set"][1]["edge_parity"]["actual_depends_on"] = ["BD-STALE"]
    evidence["ready_set"][1]["edge_parity"]["unexpected_edges"] = ["BD-STALE"]
    write_json(ready, evidence)

    created = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--ready-source", "bd-bridge",
        "--ready-json", ready,
        "--out", schedule,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["ready_set"]["tasks"] == ["EXACT"]
    assert any(
        item.get("graph_node_id") == "FORGED"
        and item.get("reason") == "edge_parity_not_confirmed"
        for item in actual["source_conflicts"]
    )

    tampered = json.loads(schedule.read_text(encoding="utf-8"))
    tampered["ready_set"]["tasks"].append("FORGED")
    write_json(schedule, tampered)
    rejected = run_script(
        "validate-schedule-receipt.py",
        "--graph", graph,
        "--schedule", schedule,
        "--ready-source", "bd-bridge",
        "--ready-json", ready,
    )
    assert rejected.returncode == 1
    assert any(
        finding["kind"] == "unconfirmed_parity_scheduled"
        for finding in json.loads(rejected.stdout)["findings"]
    )


def test_active_lease_and_leased_resource_are_excluded_from_ready_batches(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    leases = tmp_path / "leases.json"
    schedule = tmp_path / "schedule.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("LEASED-ID", resource_scope=["api"]),
                ready_node("LEASED-RESOURCE", resource_scope=["db"]),
                ready_node("SAFE", resource_scope=["web"]),
            ]
        },
    )
    write_json(
        leases,
        {
            "leases": [
                {
                    "graph_node_id": "LEASED-ID",
                    "state": "claimed",
                    "resource_scope": ["db"],
                }
            ]
        },
    )
    created = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--out", schedule,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["ready_set"]["tasks"] == ["SAFE"]
    assert actual["batches"]["tasks"] == [["SAFE"]]
    assert actual["conflicts"] == ["LEASED-ID", "LEASED-RESOURCE"]


def test_schedule_and_c17_reject_missing_lease_and_input_overwrite_before_write(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    leases = tmp_path / "leases.json"
    schedule = tmp_path / "schedule.json"
    goal = tmp_path / "goal.json"
    progress = tmp_path / "progress.json"
    intermediate = tmp_path / "intermediate.jsonl"
    write_json(graph, {"nodes": [ready_node("T1")]})
    write_json(leases, {"leases": []})
    graph_before = graph.read_bytes()
    leases_before = leases.read_bytes()

    missing_lease = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", tmp_path / "missing-leases.json",
        "--out", schedule,
    )
    assert missing_lease.returncode == 2
    assert "lease snapshot does not exist" in missing_lease.stderr
    assert not schedule.exists()

    overwrite_graph = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--out", graph,
    )
    assert overwrite_graph.returncode == 2
    assert "must not overwrite" in overwrite_graph.stderr
    assert graph.read_bytes() == graph_before
    assert leases.read_bytes() == leases_before

    partial_anchor = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--out", schedule,
        "--goal-spec", goal,
    )
    assert partial_anchor.returncode == 2
    assert "goal anchor requires" in partial_anchor.stderr
    assert not schedule.exists()

    created = run_script(
        "schedule-graph.py",
        "--graph", graph,
        "--leases", leases,
        "--out", schedule,
        "--goal-spec", goal,
        "--goal-progress", progress,
        "--goal-intermediate", intermediate,
    )
    assert created.returncode == 0, created.stderr
    schedule_before = schedule.read_bytes()
    c17_overwrite = run_script(
        "validate-schedule-receipt.py",
        "--graph", graph,
        "--schedule", schedule,
        "--leases", leases,
        "--out", schedule,
    )
    assert c17_overwrite.returncode == 2
    assert "must not overwrite" in c17_overwrite.stderr
    assert schedule.read_bytes() == schedule_before
    assert graph.read_bytes() == graph_before
    assert leases.read_bytes() == leases_before


def test_both_mode_partitions_authority_then_builds_one_resource_safe_batch(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    ready = tmp_path / "c28-ready.json"
    schedule = tmp_path / "schedule.json"
    write_json(
        graph,
        {
            "nodes": [
                ready_node("B", tracker_binding="beads", resource_scope=["shared"]),
                ready_node("B-BLOCKED", tracker_binding="beads", resource_scope=["db"]),
                ready_node("G", tracker_binding="github", resource_scope=["shared"]),
                ready_node("N", tracker_binding="none", resource_scope=["docs"]),
            ]
        },
    )
    write_json(
        ready,
        c28_ready(
            ("B", True),
            ("B-BLOCKED", False),
            ("G", True),
            conflicts=[{"graph_node_id": "B-BLOCKED", "reason": "parity"}],
        ),
    )
    created = run_script(
        "schedule-graph.py",
        "--graph",
        graph,
        "--ready-source",
        "both",
        "--ready-json",
        ready,
        "--max-parallel",
        4,
        "--out",
        schedule,
    )
    assert created.returncode == 0, created.stderr
    actual = json.loads(schedule.read_text(encoding="utf-8"))
    assert actual["ready_set"]["tasks"] == ["B", "G", "N"]
    assert actual["binding_ready_set"] == {
        "beads": {"features": [], "tasks": ["B"]},
        "github": {"features": [], "tasks": ["G"]},
        "none": {"features": [], "tasks": ["N"]},
    }
    assert all(
        not {"B", "G"} <= set(batch) for batch in actual["batches"]["tasks"]
    )
    assert {
        "kind": "tasks",
        "nodes": ["B", "G"],
        "resources": ["shared"],
    } in actual["conflict_pairs"]
    assert any(
        item.get("reason") == "c28_candidate_binding_is_not_beads"
        and item.get("graph_node_id") == "G"
        for item in actual["source_conflicts"]
    )
    assert "B-BLOCKED" not in actual["ready_set"]["tasks"]

    checked = run_script(
        "validate-schedule-receipt.py",
        "--graph",
        graph,
        "--schedule",
        schedule,
        "--ready-source",
        "both",
        "--ready-json",
        ready,
    )
    assert checked.returncode == 0, checked.stderr


def _validator(path: Path, payload: dict) -> None:
    path.write_text(
        "import json\nprint(json.dumps(" + repr(payload) + "))\n",
        encoding="utf-8",
    )


def requirements_fixture(root: Path) -> tuple[Path, dict[str, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    plan_digest = PLAN_DIGEST
    c11_digest = C11_DIGEST
    feature_id = "FEATURE-1"
    package_id = "feature-package/FEATURE-1"
    task_ids = [f"SYS-P{index:02d}" for index in range(1, 14)]
    nodes = [
        ready_node(
            feature_id,
            artifact_kind="feature",
            title="注文処理を非同期化する",
            file_path="features/FEATURE-1.md",
            goal="注文処理が非同期で収束する",
            scope_in=["受付と処理を分離する"],
            scope_out=["UI刷新"],
            acceptance=["再送でも二重処理しない"],
            related_nodes=["SPEC-1"],
            source_lineage={"source_plugin": "system-spec-harness", "source_digest": "feature", "source_path": "system-spec/index.md"},
        ),
        ready_node(
            "SPEC-1",
            artifact_kind="specification",
            file_path="specs/spec-1.md",
            source_lineage={"source_plugin": "system-spec-harness", "source_digest": "spec", "source_path": "system-spec/00-requirements-definition.md"},
        ),
    ]
    for index, node_id in enumerate(task_ids, 1):
        nodes.append(
            ready_node(
                node_id,
                phase_ref=f"P{index:02d}",
                parent_feature=feature_id,
                feature_package_id=package_id,
                depends_on=[] if index == 1 else [task_ids[index - 2]],
                source_lineage={"source_digest": PLAN_DIGEST.removeprefix("sha256:"), "source_path": f"system-plan/task-{index}.md"},
            )
        )
    graph = root / ".dev-graph/state/graph.json"
    graph_value = {"graph_revision": 1, "nodes": nodes}
    write_json(graph, graph_value)
    package = root / "system-plan/FEATURE-1/package.json"
    write_json(
        package,
        {
            "feature_package_id": package_id,
            "parent_feature": feature_id,
            "source_feature_digest": "sha256:feature",
            "task_count": 13,
            "phase_refs": [f"P{index:02d}" for index in range(1, 14)],
            "task_node_ids": task_ids,
            "task_spec_paths": [f"task-specs/phase-{index:02d}.md" for index in range(1, 14)],
        },
    )
    state = root / ".dev-graph/state"
    write_json(state / "feature-1-validation.json", {"parent_feature": feature_id, "status": "pass", "violations": [], "validated_digest": plan_digest})
    write_json(state / "feature-1-readiness.json", {"feature_id": feature_id, "status": "complete", "missing_sections": [], "source_pin": {"source_digest": READINESS_SOURCE_DIGEST}})
    write_json(
        state / "feature-1-registration-receipt.json",
        {
            "schema_version": "1.0.0",
            "parent_feature": feature_id,
            "status": "registered",
            "registered_at": "2026-08-24T00:00:00Z",
            "feature_package_id": package_id,
            "source_digest": plan_digest,
            "expected_count": 13,
            "applied_count": 13,
            "phase_refs": [f"P{index:02d}" for index in range(1, 14)],
            "node_ids": task_ids,
            "graph_revision_before": 0,
            "graph_revision_after": 1,
            "graph_digest_after": "sha256:" + hashlib.sha256(
                json.dumps(graph_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "c11_readiness_digest": c11_digest,
            "output_path": ".dev-graph/state/graph.json",
        },
    )
    write_json(state / "current.json", {"published_digest": plan_digest})
    validators = {
        "graph": root / "graph-validator.py",
        "plan": root / "plan-validator.py",
        "readiness": root / "readiness-validator.py",
    }
    _validator(
        validators["graph"],
        {
            "valid": True,
            "violations": [],
            "implementation_readiness": "complete",
            "readiness_digest": c11_digest,
            "schema": str(PLUGIN / "schemas/graph-node.schema.json"),
        },
    )
    _validator(validators["plan"], {"status": "pass", "violations": [], "validated_digest": plan_digest, "phase_refs": [f"P{index:02d}" for index in range(1, 14)]})
    _validator(validators["readiness"], {"status": "complete", "missing_sections": [], "source_pin": {"source_digest": READINESS_SOURCE_DIGEST}})
    return package, validators


def write_legacy_evidence(root: Path, package_path: Path) -> Path:
    graph_path = root / ".dev-graph/state/graph.json"
    receipt_path = root / ".dev-graph/state/feature-1-registration-receipt.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    package = json.loads(package_path.read_text(encoding="utf-8"))
    graph_digest = "sha256:" + hashlib.sha256(graph_path.read_bytes()).hexdigest()
    receipt_digest = "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    binding = {
        "immutable_receipt_sha256": receipt_digest,
        "graph_sha256": graph_digest,
        "c11_readiness_digest": C11_DIGEST,
        "implementation_readiness_source_digest": READINESS_SOURCE_DIGEST,
        "source_digest": PLAN_DIGEST,
    }
    binding_raw = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    binding_digest = "sha256:" + hashlib.sha256(binding_raw).hexdigest()
    evidence_path = receipt_path.with_name(
        f"{receipt_path.stem}.evidence-v1.{binding_digest.removeprefix('sha256:')}.json"
    )
    write_json(
        evidence_path,
        {
            "schema_version": "1.0.0",
            "evidence_contract": "package-registration-revalidation/v1",
            "status": "revalidated",
            "issued_at": "2026-08-24T00:00:00Z",
            "feature_package_id": package["feature_package_id"],
            "parent_feature": package["parent_feature"],
            "source_digest": PLAN_DIGEST,
            "node_ids": package["task_node_ids"],
            "immutable_receipt_path": receipt_path.relative_to(root).as_posix(),
            "immutable_receipt_sha256": receipt_digest,
            "output_path": graph_path.relative_to(root).as_posix(),
            "graph_revision": graph["graph_revision"],
            "graph_sha256": graph_digest,
            "c11_readiness_digest": C11_DIGEST,
            "implementation_readiness_status": "complete",
            "implementation_readiness_source_digest": READINESS_SOURCE_DIGEST,
            "binding_digest": binding_digest,
        },
    )
    return evidence_path


def test_requirements_cli_emits_exact13_handoff_without_code(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    arguments = (
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    created = run_script(*arguments)
    assert created.returncode == 0, created.stderr
    receipt = json.loads(created.stdout)
    assert receipt["task_count"] == 13
    assert receipt["implementation_code_files"] == 0
    handoff = json.loads(Path(receipt["handoff"]).read_text(encoding="utf-8"))
    assert handoff["handoff_target"] == "capability-build/task-graph"
    assert len(handoff["execution_tasks"]) == 13
    assert handoff["code_generation"]["generated_files"] == []
    assert handoff["snapshot"]["plan_digest"] == PLAN_DIGEST
    assert handoff["snapshot"]["readiness_digest"] == "sha256:" + "c" * 64
    assert handoff["lineage"][0]["source_lineage"]["source_path"] == "system-spec/index.md"
    assert handoff["artifact_digests"]["requirements"] == "sha256:" + hashlib.sha256(
        Path(receipt["requirements"]).read_bytes()
    ).hexdigest()
    assert handoff["artifact_digests"]["readiness_matrix"] == "sha256:" + hashlib.sha256(
        Path(receipt["readiness_matrix"]).read_bytes()
    ).hexdigest()
    matrix = json.loads(Path(receipt["readiness_matrix"]).read_text(encoding="utf-8"))
    assert matrix["gates"]["c11"]["receipt"]["schema"] == "schemas/graph-node.schema.json"
    assert not any(path.suffix in {".py", ".js", ".ts"} for path in (tmp_path / ".dev-graph/requirements").rglob("*"))
    anchor = receipt["goal_anchor"]
    persisted_json = [
        Path(receipt["readiness_matrix"]),
        Path(receipt["handoff"]),
        Path(anchor["goal_spec"]),
        Path(anchor["progress"]),
    ]
    assert all(absolute_strings(json.loads(path.read_text(encoding="utf-8"))) == [] for path in persisted_json)
    intermediate = json.loads(Path(anchor["intermediate"]).read_text(encoding="utf-8"))
    assert not Path(intermediate["handoff_ref"]).is_absolute()
    before = {
        path: path.read_bytes()
        for path in [
            Path(receipt["requirements"]),
            Path(receipt["readiness_matrix"]),
            Path(receipt["handoff"]),
            Path(anchor["goal_spec"]),
            Path(anchor["progress"]),
            Path(anchor["intermediate"]),
        ]
    }
    repeated = run_script(*arguments)
    assert repeated.returncode == 0, repeated.stderr
    repeated_receipt = json.loads(repeated.stdout)
    assert repeated_receipt["write_count"] == 0
    assert repeated_receipt["idempotent"] is True
    assert {path: path.read_bytes() for path in before} == before
    checked = run_script(
        "validate-goal-seek-runtime.py",
        "--goal-spec", anchor["goal_spec"],
        "--progress", anchor["progress"],
        "--intermediate", anchor["intermediate"],
    )
    assert checked.returncode == 0, checked.stderr


def test_requirements_cli_preflights_anchor_contract_before_any_write(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--goal-spec", "eval-log/custom-goal.json",
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 2
    assert "goal anchor requires" in rejected.stderr
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1").exists()
    assert not (tmp_path / "eval-log").exists()


def test_requirements_cli_uses_c24_custom_graph_and_state_authority(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    default_state = tmp_path / ".dev-graph/state"
    custom_state = tmp_path / "runtime/custom-state"
    custom_state.parent.mkdir(parents=True)
    default_state.rename(custom_state)
    write_json(
        tmp_path / ".dev-graph/config.json",
        {
            "local_state": {
                "graph": "runtime/custom-state/graph.json",
                "cache": "runtime/cache",
                "locks": "runtime/locks",
            },
            "path_policy": {
                "authority": "caller-repository",
                "allow_outside_repository": False,
                "follow_content_symlinks_outside_repository": False,
            },
        },
    )
    receipt_path = custom_state / "feature-1-registration-receipt.json"
    registration = json.loads(receipt_path.read_text(encoding="utf-8"))
    registration["output_path"] = "runtime/custom-state/graph.json"
    write_json(receipt_path, registration)

    created = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package.relative_to(tmp_path),
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert created.returncode == 0, created.stderr + created.stdout
    handoff = json.loads(Path(json.loads(created.stdout)["handoff"]).read_text(encoding="utf-8"))
    assert handoff["snapshot"]["graph_ref"] == "runtime/custom-state/graph.json"
    matrix = json.loads(
        (tmp_path / ".dev-graph/requirements/FEATURE-1/readiness-matrix.json").read_text(encoding="utf-8")
    )
    assert matrix["gates"]["c02"]["registration_ref"] == "runtime/custom-state/feature-1-registration-receipt.json"


def test_requirements_cli_rejects_validator_replacement_outside_test_contract(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    env = dict(os.environ)
    env.pop("DEV_GRAPH_TEST_VALIDATOR_OVERRIDES", None)
    rejected = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "build-requirements-handoff.py"),
            "--repo-root", str(tmp_path),
            "--feature-id", "FEATURE-1",
            "--package", str(package),
            "--graph-validator", str(validators["graph"]),
            "--plan-validator", str(validators["plan"]),
            "--readiness-validator", str(validators["readiness"]),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    assert rejected.returncode == 2
    assert "validator overrides are test-only" in rejected.stderr
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1").exists()


def test_requirements_cli_rejects_non_exact_current_registration_receipts(tmp_path: Path) -> None:
    cases: list[tuple[str, dict[str, object], str | None]] = [
        ("package", {"feature_package_id": "feature-package/WRONG"}, None),
        ("count", {"expected_count": 12}, None),
        ("phase", {"phase_refs": list(reversed([f"P{index:02d}" for index in range(1, 14)]))}, None),
        ("revision", {"graph_revision_after": 2}, None),
        ("digest", {"graph_digest_after": "sha256:" + "0" * 64}, None),
        ("output", {"output_path": "wrong/graph.json"}, None),
        ("missing-node-ids", {}, "node_ids"),
    ]
    for name, updates, removed in cases:
        root = tmp_path / name
        root.mkdir()
        package, validators = requirements_fixture(root)
        receipt_path = root / ".dev-graph/state/feature-1-registration-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.update(updates)
        if removed is not None:
            receipt.pop(removed)
        write_json(receipt_path, receipt)
        rejected = run_script(
            "build-requirements-handoff.py",
            "--repo-root", root,
            "--feature-id", "FEATURE-1",
            "--package", package,
            "--graph-validator", validators["graph"],
            "--plan-validator", validators["plan"],
            "--readiness-validator", validators["readiness"],
        )
        assert rejected.returncode == 1, f"{name}: {rejected.stdout} {rejected.stderr}"
        result = json.loads(rejected.stdout)
        assert any("C02 registration receipt contract" in blocker for blocker in result["blockers"])
        assert not (root / ".dev-graph/requirements/FEATURE-1/capability-build-handoff.json").exists()


def test_requirements_cli_blocks_stale_digest_without_handoff(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    write_json(tmp_path / ".dev-graph/state/current.json", {"published_digest": "sha256:stale"})
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 1
    result = json.loads(rejected.stdout)
    assert result["handoff_count"] == 0
    assert "published plan digest is stale" in result["blockers"]
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1/capability-build-handoff.json").exists()


def test_requirements_cli_blocks_c11_c02_readiness_digest_mismatch(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    receipt_path = tmp_path / ".dev-graph/state/feature-1-registration-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["c11_readiness_digest"] = "sha256:" + "d" * 64
    write_json(receipt_path, receipt)
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 1
    result = json.loads(rejected.stdout)
    assert result["handoff_count"] == 0
    assert "C11/C02 readiness digest mismatch" in result["blockers"]
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1/capability-build-handoff.json").exists()


def test_requirements_cli_blocks_legacy_c02_receipt_without_c11_digest(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    receipt_path = tmp_path / ".dev-graph/state/feature-1-registration-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.pop("c11_readiness_digest")
    write_json(receipt_path, receipt)
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 1
    result = json.loads(rejected.stdout)
    assert result["handoff_count"] == 0
    assert "legacy C02 supplemental evidence is missing" in result["blockers"]
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1/capability-build-handoff.json").exists()


def test_requirements_cli_accepts_exact_legacy_supplement_and_rejects_tamper(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    receipt_path = tmp_path / ".dev-graph/state/feature-1-registration-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.pop("c11_readiness_digest")
    write_json(receipt_path, receipt)
    saved_readiness_path = tmp_path / ".dev-graph/state/feature-1-readiness.json"
    saved_readiness = json.loads(saved_readiness_path.read_text(encoding="utf-8"))
    saved_readiness["source_pin"]["source_digest"] = "sha256:" + "e" * 64
    write_json(saved_readiness_path, saved_readiness)
    evidence_path = write_legacy_evidence(tmp_path, package)

    accepted = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert accepted.returncode == 0, accepted.stderr + accepted.stdout
    accepted_receipt = json.loads(accepted.stdout)
    matrix = json.loads(Path(accepted_receipt["readiness_matrix"]).read_text(encoding="utf-8"))
    assert matrix["gates"]["c02"]["supplemental_evidence_ref"] == evidence_path.relative_to(tmp_path).as_posix()
    assert matrix["gates"]["c02"]["c11_readiness_digest"] == C11_DIGEST

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["c11_readiness_digest"] = "sha256:" + "f" * 64
    write_json(evidence_path, evidence)
    rejected_root = tmp_path / ".dev-graph/requirements-after-tamper"
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--output-dir", rejected_root,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 1
    result = json.loads(rejected.stdout)
    assert result["handoff_count"] == 0
    assert "legacy C02 supplemental evidence does not match current inputs" in result["blockers"]
    assert not (rejected_root / "capability-build-handoff.json").exists()


def test_requirements_cli_surfaces_all_incomplete_nodes_and_emits_no_handoff(tmp_path: Path) -> None:
    package, validators = requirements_fixture(tmp_path)
    graph_path = tmp_path / ".dev-graph/state/graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    for node in graph["nodes"]:
        if node["graph_node_id"] in {"SPEC-1", "SYS-P03"}:
            node["implementation_readiness"] = {
                "status": "incomplete",
                "missing_sections": [f"missing:{node['graph_node_id']}"],
            }
    write_json(graph_path, graph)
    rejected = run_script(
        "build-requirements-handoff.py",
        "--repo-root", tmp_path,
        "--feature-id", "FEATURE-1",
        "--package", package,
        "--graph-validator", validators["graph"],
        "--plan-validator", validators["plan"],
        "--readiness-validator", validators["readiness"],
    )
    assert rejected.returncode == 1
    result = json.loads(rejected.stdout)
    assert {item["graph_node_id"] for item in result["missing_sections"]} == {"SPEC-1", "SYS-P03"}
    assert result["handoff_count"] == 0
    assert not (tmp_path / ".dev-graph/requirements/FEATURE-1/capability-build-handoff.json").exists()


def test_skills_bind_to_maintained_commands_and_real_c17_task() -> None:
    requirements = (PLUGIN / "skills/run-dev-graph-requirements/SKILL.md").read_text(encoding="utf-8")
    schedule = (PLUGIN / "skills/run-dev-graph-schedule/SKILL.md").read_text(encoding="utf-8")
    agent = (PLUGIN / "agents/dev-graph-parallel-safety-verifier.md").read_text(encoding="utf-8")
    assert "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-requirements-handoff.py" in requirements
    assert "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-goal-seek-runtime.py" in requirements
    assert "emit_handoff.py" not in requirements
    assert "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/schedule-graph.py" in schedule
    assert "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-schedule-receipt.py" in schedule
    assert "beads) READY_SOURCE=bd-bridge" in schedule
    assert "both) READY_SOURCE=both" in schedule
    assert 'READY_JSON_ARGS=(--ready-json "<C28_READY_JSON>")' in schedule
    assert 'SCOPE_ARGS=(--scope "$SCOPE")' in schedule
    assert "subagent_type: dev-graph:dev-graph-parallel-safety-verifier" in schedule
    assert "必ず `Task`" in schedule
    assert "validate-schedule-receipt.py" in agent
    assert '`--scope`\u3068`--ready-source`\u3092\u5fc5\u305a\u540c\u5024\u3067\u6e21\u3059' in agent
    assert '`ready-source=bd-bridge|both`' in agent
    assert "C17" in agent
