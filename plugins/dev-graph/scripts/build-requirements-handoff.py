#!/usr/bin/env python3
# /// script
# name: build-requirements-handoff
# purpose: Validate C11/C02/exact-13 lineage gates and emit a capability-build requirements handoff.
# inputs: ["argv: --repo-root DIR --feature-id ID --package FILE"]
# outputs: ["requirements.md", "readiness-matrix.json", "capability-build-handoff.json", "goal anchors"]
# requires-python = ">=3.10"
# dependencies: [_common.py, resolve-repo-context.py, validate-graph-schema.py, system-dev-planner/validate-system-plan.py, system-dev-planner/check-implementation-readiness.py]
# contexts: [C, E]
# network: false
# write-scope: repository-contained requirements output and goal anchors selected by validated arguments
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from _common import ContractError, atomic_json, canonical_digest, contained, dump, load_json, run


GOAL = (
    "system-spec-harness確定成果物とsystem development task planを含むグラフ情報から実装要件を導出し、"
    "implementation-readiness完了時だけcapability-build/task-graph buildへ実装をhandoffした状態になっている"
)
PHASES = [f"P{index:02d}" for index in range(1, 14)]
REPO_CONTEXT_RESOLVER = Path(__file__).with_name("resolve-repo-context.py")
SHA256_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
LEGACY_EVIDENCE_KEYS = {
    "schema_version", "evidence_contract", "status", "issued_at", "feature_package_id",
    "parent_feature", "source_digest", "node_ids", "immutable_receipt_path",
    "immutable_receipt_sha256", "output_path", "graph_revision", "graph_sha256",
    "c11_readiness_digest", "implementation_readiness_status",
    "implementation_readiness_source_digest", "binding_digest",
}
REGISTRATION_RECEIPT_KEYS = {
    "schema_version", "status", "registered_at", "feature_package_id", "parent_feature",
    "source_digest", "expected_count", "applied_count", "phase_refs", "node_ids",
    "graph_revision_before", "graph_revision_after", "graph_digest_after", "output_path",
}
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


def _sha_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _is_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and SHA256_DIGEST.fullmatch(value) is not None


def _legacy_evidence_path(receipt: Path, binding_digest: str) -> Path:
    return receipt.with_name(
        f"{receipt.stem}.evidence-v1.{binding_digest.removeprefix('sha256:')}.json"
    )


def _legacy_evidence_shape(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != LEGACY_EVIDENCE_KEYS:
        return False
    if (
        value.get("schema_version") != "1.0.0"
        or value.get("evidence_contract") != "package-registration-revalidation/v1"
        or value.get("status") != "revalidated"
        or value.get("implementation_readiness_status") != "complete"
    ):
        return False
    digests = (
        "source_digest", "immutable_receipt_sha256", "graph_sha256",
        "c11_readiness_digest", "implementation_readiness_source_digest", "binding_digest",
    )
    node_ids = value.get("node_ids")
    return (
        all(_is_sha256_digest(value.get(key)) for key in digests)
        and isinstance(value.get("graph_revision"), int)
        and isinstance(node_ids, list)
        and len(node_ids) == 13
        and len(set(node_ids)) == 13
        and all(isinstance(node_id, str) and node_id for node_id in node_ids)
    )


def _registration_receipt_findings(
    receipt: object,
    *,
    package: dict[str, Any],
    graph: dict[str, Any],
    graph_path: Path,
    repo_root: Path,
    task_ids: list[str],
    plan_digest: object,
) -> list[str]:
    prefix = "C02 registration receipt contract"
    if not isinstance(receipt, dict):
        return [f"{prefix}: receipt must be an object"]
    allowed_keys = REGISTRATION_RECEIPT_KEYS | {"c11_readiness_digest"}
    keys = frozenset(receipt)
    if keys not in {frozenset(REGISTRATION_RECEIPT_KEYS), frozenset(allowed_keys)}:
        return [f"{prefix}: keys are not the canonical current/legacy set"]
    findings: list[str] = []
    if receipt.get("schema_version") != "1.0.0" or receipt.get("status") != "registered":
        findings.append(f"{prefix}: schema_version/status mismatch")
    registered_at = receipt.get("registered_at")
    if not isinstance(registered_at, str) or RFC3339.fullmatch(registered_at) is None:
        findings.append(f"{prefix}: registered_at is invalid")
    if receipt.get("feature_package_id") != package.get("feature_package_id"):
        findings.append(f"{prefix}: feature_package_id mismatch")
    if receipt.get("parent_feature") != package.get("parent_feature"):
        findings.append(f"{prefix}: parent_feature mismatch")
    if receipt.get("source_digest") != plan_digest:
        findings.append(f"{prefix}: source_digest mismatch")
    if receipt.get("expected_count") != 13 or receipt.get("applied_count") != 13:
        findings.append(f"{prefix}: expected/applied count is not exact 13")
    if receipt.get("phase_refs") != PHASES:
        findings.append(f"{prefix}: phase_refs are not exact P01..P13")
    if receipt.get("node_ids") != task_ids:
        findings.append(f"{prefix}: node_ids do not match the package exact set/order")
    before = receipt.get("graph_revision_before")
    after = receipt.get("graph_revision_after")
    current_revision = graph.get("graph_revision")
    if (
        not isinstance(before, int) or isinstance(before, bool) or before < 0
        or not isinstance(after, int) or isinstance(after, bool) or after != before + 1
        or not isinstance(current_revision, int) or isinstance(current_revision, bool)
        or after > current_revision
    ):
        findings.append(f"{prefix}: graph revision lineage is invalid")
    graph_digest_after = receipt.get("graph_digest_after")
    if not _is_sha256_digest(graph_digest_after):
        findings.append(f"{prefix}: graph_digest_after is invalid")
    elif after == current_revision and graph_digest_after != canonical_digest(graph):
        findings.append(f"{prefix}: graph_digest_after does not match the registered graph")
    expected_output = graph_path.relative_to(repo_root).as_posix()
    if receipt.get("output_path") != expected_output:
        findings.append(f"{prefix}: output_path mismatch")
    stored_c11 = receipt.get("c11_readiness_digest")
    if stored_c11 is not None and not _is_sha256_digest(stored_c11):
        findings.append(f"{prefix}: c11_readiness_digest is invalid")
    return findings


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _atomic_text_if_changed(path: Path, text: str) -> int:
    raw = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == raw:
        return 0
    _atomic_text(path, text)
    return 1


def _atomic_json_if_changed(path: Path, value: Any) -> int:
    raw = _json_bytes(value)
    if path.is_file() and path.read_bytes() == raw:
        return 0
    atomic_json(path, value)
    return 1


def _run_json(argv: Sequence[str]) -> dict[str, Any]:
    completed = run(argv, check=False)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = (completed.stderr or completed.stdout).strip()
        raise ContractError(f"validator did not return JSON ({argv[0]}): {detail}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"validator returned non-object JSON: {argv[0]}")
    value["_exit_code"] = completed.returncode
    return value


def _state_file(state_root: Path, feature_id: str, suffix: str) -> Path:
    direct = state_root / f"{feature_id.lower()}-{suffix}.json"
    if direct.is_file():
        return direct
    candidates = []
    for path in state_root.glob(f"*-{suffix}.json"):
        try:
            value = load_json(path)
        except ContractError:
            continue
        if isinstance(value, dict) and (
            value.get("parent_feature") == feature_id
            or value.get("feature_id") == feature_id
        ):
            candidates.append(path)
    if len(candidates) != 1:
        raise ContractError(f"cannot resolve unique C02 {suffix} state for {feature_id}")
    return candidates[0]


def _node_id(node: dict[str, Any]) -> str | None:
    value = node.get("graph_node_id") or node.get("id")
    return value if isinstance(value, str) and value else None


def _ready_row(node: dict[str, Any]) -> dict[str, Any]:
    readiness = node.get("implementation_readiness")
    readiness = readiness if isinstance(readiness, dict) else {}
    missing = readiness.get("missing_sections")
    missing = missing if isinstance(missing, list) else []
    row = {
        "graph_node_id": _node_id(node),
        "artifact_kind": node.get("artifact_kind"),
        "file_path": node.get("file_path"),
        "phase_ref": node.get("phase_ref"),
        "implementation_readiness": readiness.get("status"),
        "evaluation_status": node.get("evaluation_status"),
        "confirmation_status": node.get("confirmation_status"),
        "missing_sections": missing,
        "parent_feature": node.get("parent_feature"),
        "feature_package_id": node.get("feature_package_id"),
        "source_lineage": node.get("source_lineage"),
    }
    row["verdict"] = "ready" if (
        row["implementation_readiness"] == "complete"
        and row["evaluation_status"] == "pass"
        and row["confirmation_status"] == "confirmed"
        and not missing
    ) else "blocked"
    row["remediation_owner"] = None if row["verdict"] == "ready" else (
        "system-dev-planner/run-system-dev-plan"
        if row["artifact_kind"] == "task"
        else "system-spec-harness/run-system-spec-compile"
    )
    return row


def _requirements(feature: dict[str, Any], related: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_refs = sorted(
        {
            str((node.get("source_lineage") or {}).get("source_path"))
            for node in [feature, *related]
            if isinstance(node.get("source_lineage"), dict)
            and (node.get("source_lineage") or {}).get("source_path")
        }
    )
    items: list[dict[str, Any]] = []
    goal = feature.get("goal")
    if isinstance(goal, str) and goal.strip():
        items.append(
            {"requirement_id": "GOAL-001", "kind": "goal", "statement": goal, "source_refs": source_refs}
        )
    for index, statement in enumerate(feature.get("scope_in") or [], 1):
        if isinstance(statement, str) and statement.strip():
            items.append(
                {
                    "requirement_id": f"REQ-{index:03d}",
                    "kind": "functional",
                    "statement": statement,
                    "source_refs": source_refs,
                }
            )
    for index, statement in enumerate(feature.get("acceptance") or [], 1):
        if isinstance(statement, str) and statement.strip():
            items.append(
                {
                    "requirement_id": f"ACC-{index:03d}",
                    "kind": "acceptance",
                    "statement": statement,
                    "source_refs": source_refs,
                }
            )
    if not items:
        raise ContractError("feature has no goal/scope_in/acceptance requirements")
    return items


def _write_anchor(
    goal_spec: Path,
    progress: Path,
    intermediate: Path,
    handoff_ref: str,
    evidence: dict[str, Any],
    generated_at: str,
) -> int:
    goal_hash = hashlib.sha256(GOAL.encode("utf-8")).hexdigest()
    write_count = _atomic_json_if_changed(
        goal_spec, {"original_goal": GOAL, "original_goal_hash": goal_hash},
    )
    write_count += _atomic_json_if_changed(
        progress,
        {
            "original_goal_hash": goal_hash,
            "updated_at": generated_at,
            "checklist": {
                "lineage_closure": {"status": "PASS", "evidence": evidence["graph_snapshot_digest"]},
                "c11_c02_digest_agreement": {"status": "PASS", "evidence": evidence["readiness_digest"]},
                "missing_sections": {"status": "PASS", "evidence": "count=0"},
                "atomic_handoff": {"status": "PASS", "evidence": handoff_ref},
                "implementation_code_files": {"status": "PASS", "evidence": "count=0"},
            },
        },
    )
    row = {
        "iteration": 1,
        "original_goal": GOAL,
        "original_goal_hash": goal_hash,
        "current_goal_snapshot": GOAL,
        "delta_from_original": "none",
        "merged_directive_for_next": "handoff complete",
        "drift_signal": False,
        "handoff_ref": handoff_ref,
    }
    write_count += _atomic_text_if_changed(
        intermediate, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return write_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--handoff-target", default="capability-build/task-graph")
    parser.add_argument("--output-dir")
    parser.add_argument("--graph-validator")
    parser.add_argument("--plan-validator")
    parser.add_argument("--readiness-validator")
    parser.add_argument("--goal-spec")
    parser.add_argument("--goal-progress")
    parser.add_argument("--goal-intermediate")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=True)
    validator_overrides = (args.graph_validator, args.plan_validator, args.readiness_validator)
    if any(validator_overrides) and os.environ.get("DEV_GRAPH_TEST_VALIDATOR_OVERRIDES") != "1":
        raise ContractError("validator overrides are test-only; canonical validators cannot be replaced")
    anchor_args = (args.goal_spec, args.goal_progress, args.goal_intermediate)
    if any(anchor_args) and not all(anchor_args):
        raise ContractError("goal anchor requires --goal-spec, --goal-progress, and --goal-intermediate together")
    goal_spec = Path(args.goal_spec) if args.goal_spec else Path("eval-log/run-dev-graph-requirements-goal-spec.json")
    progress = Path(args.goal_progress) if args.goal_progress else Path("eval-log/run-dev-graph-requirements-progress.json")
    intermediate = Path(args.goal_intermediate) if args.goal_intermediate else Path("eval-log/run-dev-graph-requirements-intermediate.jsonl")
    goal_spec = contained(goal_spec if goal_spec.is_absolute() else repo_root / goal_spec, repo_root, must_exist=False)
    progress = contained(progress if progress.is_absolute() else repo_root / progress, repo_root, must_exist=False)
    intermediate = contained(intermediate if intermediate.is_absolute() else repo_root / intermediate, repo_root, must_exist=False)
    requested_output = Path(args.output_dir) if args.output_dir else Path(f".dev-graph/requirements/{args.feature_id}")
    output_dir = contained(
        requested_output if requested_output.is_absolute() else repo_root / requested_output,
        repo_root,
        must_exist=False,
    )
    requirements_path = contained(output_dir / "requirements.md", repo_root, must_exist=False)
    matrix_path = contained(output_dir / "readiness-matrix.json", repo_root, must_exist=False)
    handoff_path = contained(output_dir / "capability-build-handoff.json", repo_root, must_exist=False)
    for output_path in (requirements_path, matrix_path, handoff_path):
        if output_path.exists() and not output_path.is_file():
            raise ContractError(f"requirements output target must be a regular file: {output_path}")
    context = _run_json([
        sys.executable,
        str(REPO_CONTEXT_RESOLVER),
        "--repo-root",
        str(repo_root),
        "--mode",
        "read",
    ])
    if context.get("_exit_code") != 0:
        raise ContractError("C24 repository context did not PASS")
    if Path(str(context.get("repo_root", ""))).resolve() != repo_root:
        raise ContractError("C24 repository context identity mismatch")
    graph_value = (context.get("local_state_paths") or {}).get("graph")
    if not isinstance(graph_value, str) or not graph_value:
        raise ContractError("C24 repository context omits local_state.graph")
    graph_path = contained(Path(graph_value), repo_root)
    package_input = Path(args.package)
    package_path = contained(
        package_input if package_input.is_absolute() else repo_root / package_input,
        repo_root,
    )
    staging = package_path.parent
    staging_rel = staging.relative_to(repo_root).as_posix()
    state_root = contained(graph_path.parent, repo_root)
    feature_id = args.feature_id
    plugins_root = Path(__file__).resolve().parents[2]
    graph_validator = Path(args.graph_validator).resolve() if args.graph_validator else Path(__file__).with_name("validate-graph-schema.py")
    plan_validator = Path(args.plan_validator).resolve() if args.plan_validator else plugins_root / "system-dev-planner/scripts/validate-system-plan.py"
    readiness_validator = Path(args.readiness_validator).resolve() if args.readiness_validator else plugins_root / "system-dev-planner/scripts/check-implementation-readiness.py"
    for validator in (graph_validator, plan_validator, readiness_validator):
        if not validator.is_file():
            raise ContractError(f"validator missing: {validator}")

    c11 = _run_json([
        sys.executable,
        str(graph_validator),
        "--graph",
        str(graph_path),
        "--repo-root",
        str(repo_root),
        "--feature-id",
        feature_id,
    ])
    plan = _run_json([sys.executable, str(plan_validator), "--repo-root", str(repo_root), "--staging", staging_rel])
    readiness = _run_json([sys.executable, str(readiness_validator), "--repo-root", str(repo_root)])
    package = load_json(package_path)
    graph = load_json(graph_path)
    if not isinstance(package, dict) or not isinstance(graph, dict):
        raise ContractError("package and graph must be JSON objects")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ContractError("graph.nodes must be an array")
    by_id = {_node_id(node): node for node in nodes if isinstance(node, dict) and _node_id(node)}
    feature = by_id.get(feature_id)
    if not isinstance(feature, dict):
        raise ContractError(f"feature node not found: {feature_id}")

    validation_path = _state_file(state_root, feature_id, "validation")
    readiness_path = _state_file(state_root, feature_id, "readiness")
    registration_path = _state_file(state_root, feature_id, "registration-receipt")
    saved_validation = load_json(validation_path)
    saved_readiness = load_json(readiness_path)
    registration = load_json(registration_path)
    current_path = state_root / "current.json"
    current = load_json(current_path)

    blockers: list[str] = []
    if c11.get("_exit_code") != 0 or c11.get("valid") is not True or c11.get("violations"):
        blockers.append("C11 validate-graph-schema did not PASS")
    if c11.get("implementation_readiness") != "complete":
        blockers.append("C11 implementation_readiness is not complete")
    c11_readiness_digest = c11.get("readiness_digest")
    if not _is_sha256_digest(c11_readiness_digest):
        blockers.append("C11 readiness digest is missing or invalid")
    if plan.get("_exit_code") != 0 or plan.get("status") != "pass" or plan.get("violations"):
        blockers.append("system-dev-planner validate-system-plan did not PASS")
    if plan.get("phase_refs") != PHASES:
        blockers.append("system-dev-planner receipt is not exact P01..P13")
    if readiness.get("_exit_code") != 0 or readiness.get("status") != "complete":
        blockers.append("implementation readiness did not complete")
    if package.get("parent_feature") != feature_id:
        blockers.append("package parent_feature mismatch")
    if package.get("task_count") != 13 or package.get("phase_refs") != PHASES:
        blockers.append("package is not exact P01..P13")
    task_ids = package.get("task_node_ids")
    task_paths = package.get("task_spec_paths")
    if not isinstance(task_ids, list) or len(task_ids) != 13 or len(set(task_ids)) != 13:
        blockers.append("package task_node_ids is not exact 13")
        task_ids = []
    if not isinstance(task_paths, list) or len(task_paths) != 13:
        blockers.append("package task_spec_paths is not exact 13")
        task_paths = []
    plan_digest = plan.get("validated_digest")
    if saved_validation.get("validated_digest") != plan_digest:
        blockers.append("C02 saved validation digest is stale")
    if saved_validation.get("status") != "pass" or saved_validation.get("violations"):
        blockers.append("C02 saved validation state did not PASS")
    blockers.extend(
        _registration_receipt_findings(
            registration,
            package=package,
            graph=graph,
            graph_path=graph_path,
            repo_root=repo_root,
            task_ids=task_ids,
            plan_digest=plan_digest,
        )
    )
    if current.get("published_digest") != plan_digest:
        blockers.append("published plan digest is stale")
    saved_source = (saved_readiness.get("source_pin") or {}).get("source_digest")
    live_source = (readiness.get("source_pin") or {}).get("source_digest")
    c02_readiness_digest = registration.get("c11_readiness_digest")
    supplemental_evidence_ref: str | None = None
    supplemental_evidence: dict[str, Any] | None = None
    if c02_readiness_digest is None:
        if not all(
            _is_sha256_digest(value)
            for value in (c11_readiness_digest, live_source, plan_digest)
        ) or len(task_ids) != 13:
            blockers.append("legacy C02 supplemental evidence inputs are incomplete")
        else:
            graph_digest = _sha_file(graph_path)
            receipt_digest = _sha_file(registration_path)
            binding = {
                "immutable_receipt_sha256": receipt_digest,
                "graph_sha256": graph_digest,
                "c11_readiness_digest": c11_readiness_digest,
                "implementation_readiness_source_digest": live_source,
                "source_digest": plan_digest,
            }
            binding_digest = canonical_digest(binding)
            evidence_path = _legacy_evidence_path(registration_path, binding_digest)
            supplemental_evidence_ref = evidence_path.relative_to(repo_root).as_posix()
            if not evidence_path.is_file():
                blockers.append("legacy C02 supplemental evidence is missing")
            else:
                try:
                    candidate = load_json(evidence_path)
                except ContractError:
                    candidate = None
                expected_evidence = {
                    "schema_version": "1.0.0",
                    "evidence_contract": "package-registration-revalidation/v1",
                    "status": "revalidated",
                    "feature_package_id": package.get("feature_package_id"),
                    "parent_feature": feature_id,
                    "source_digest": plan_digest,
                    "node_ids": task_ids,
                    "immutable_receipt_path": registration_path.relative_to(repo_root).as_posix(),
                    "immutable_receipt_sha256": receipt_digest,
                    "output_path": graph_path.relative_to(repo_root).as_posix(),
                    "graph_revision": graph.get("graph_revision"),
                    "graph_sha256": graph_digest,
                    "c11_readiness_digest": c11_readiness_digest,
                    "implementation_readiness_status": "complete",
                    "implementation_readiness_source_digest": live_source,
                    "binding_digest": binding_digest,
                }
                if not _legacy_evidence_shape(candidate) or any(
                    candidate.get(key) != value for key, value in expected_evidence.items()
                ):
                    blockers.append("legacy C02 supplemental evidence does not match current inputs")
                else:
                    supplemental_evidence = candidate
                    c02_readiness_digest = candidate["c11_readiness_digest"]
    elif not _is_sha256_digest(c02_readiness_digest):
        blockers.append("C02 registration C11 readiness digest is invalid")
    if _is_sha256_digest(c02_readiness_digest) and c02_readiness_digest != c11_readiness_digest:
        blockers.append("C11/C02 readiness digest mismatch")
    if supplemental_evidence is None and (not saved_source or saved_source != live_source):
        blockers.append("C02 saved readiness source digest is stale")
    if saved_readiness.get("status") != "complete" or saved_readiness.get("missing_sections"):
        blockers.append("C02 saved readiness state is incomplete")

    related_ids = feature.get("related_nodes") or []
    if not isinstance(related_ids, list):
        blockers.append("feature related_nodes must be an array")
        related_ids = []
    scope_ids = [feature_id, *related_ids, *task_ids]
    scope_nodes: list[dict[str, Any]] = []
    for node_id in scope_ids:
        node = by_id.get(node_id)
        if not isinstance(node, dict):
            blockers.append(f"lineage closure node missing: {node_id}")
        else:
            scope_nodes.append(node)
    rows = [_ready_row(node) for node in scope_nodes]
    for node in [feature, *(by_id[node_id] for node_id in related_ids if node_id in by_id)]:
        lineage = node.get("source_lineage")
        if not isinstance(lineage, dict) or not all(
            isinstance(lineage.get(key), str) and lineage[key]
            for key in ("source_plugin", "source_path", "source_digest")
        ):
            blockers.append(f"system-spec lineage incomplete: {_node_id(node)}")
    missing_sections = [
        {
            "graph_node_id": row["graph_node_id"],
            "missing_sections": row["missing_sections"] or [
                "implementation_readiness/evaluation/confirmation"
            ],
            "remediation_owner": row["remediation_owner"],
        }
        for row in rows
        if row["verdict"] != "ready"
    ]
    order = {phase: index for index, phase in enumerate(PHASES)}
    task_by_id = {node_id: by_id.get(node_id) for node_id in task_ids}
    if sorted(
        node.get("phase_ref") for node in task_by_id.values() if isinstance(node, dict)
    ) != PHASES:
        blockers.append("registered task phase_refs are not exact P01..P13")
    digest_raw = plan_digest.split(":", 1)[-1] if isinstance(plan_digest, str) else None
    for node_id, node in task_by_id.items():
        if not isinstance(node, dict):
            continue
        if node.get("parent_feature") != feature_id or node.get("feature_package_id") != package.get("feature_package_id"):
            blockers.append(f"task lineage mismatch: {node_id}")
        if (node.get("source_lineage") or {}).get("source_digest") != digest_raw:
            blockers.append(f"task source digest mismatch: {node_id}")
        phase = node.get("phase_ref")
        for dependency in node.get("depends_on") or []:
            upstream = task_by_id.get(dependency)
            if not isinstance(upstream, dict):
                blockers.append(f"package-external dependency: {node_id}->{dependency}")
            elif phase not in order or upstream.get("phase_ref") not in order or order[upstream["phase_ref"]] >= order[phase]:
                blockers.append(f"non-forward dependency: {node_id}->{dependency}")
    if blockers or missing_sections:
        dump({"status": "blocked", "handoff_count": 0, "blockers": sorted(set(blockers)), "missing_sections": missing_sections})
        return 1

    related = [by_id[node_id] for node_id in related_ids]
    requirements = _requirements(feature, related)
    graph_digest = _sha_file(graph_path)
    readiness_digest = c11_readiness_digest
    if not isinstance(readiness_digest, str):
        raise ContractError("C11 readiness digest missing after readiness gate")
    c11_receipt = {key: value for key, value in c11.items() if key != "_exit_code"}
    if "schema" in c11_receipt:
        reported_schema = Path(str(c11_receipt["schema"])).resolve()
        canonical_schema = Path(__file__).resolve().parents[1] / "schemas/graph-node.schema.json"
        if reported_schema != canonical_schema.resolve():
            raise ContractError("C11 validator reported an unexpected schema")
        c11_receipt["schema"] = "schemas/graph-node.schema.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    # The immutable registration event identifies this validated snapshot.  A
    # wall-clock timestamp would make the same handoff change on every rerun.
    now = registration["registered_at"]
    matrix = {
        "schema_version": "1.0.0",
        "kind": "requirements-readiness-matrix",
        "feature_id": feature_id,
        "feature_package_id": package.get("feature_package_id"),
        "generated_at": now,
        "graph_snapshot_digest": graph_digest,
        "readiness_digest": readiness_digest,
        "gates": {
            "c11": {"status": "pass", "receipt": c11_receipt},
            "c02": {
                "status": "pass",
                "validation_ref": str(validation_path.relative_to(repo_root)),
                "readiness_ref": str(readiness_path.relative_to(repo_root)),
                "registration_ref": str(registration_path.relative_to(repo_root)),
                "supplemental_evidence_ref": supplemental_evidence_ref,
                "c11_readiness_digest": c02_readiness_digest,
            },
            "system_plan": {"status": "pass", "validated_digest": plan_digest, "phase_refs": PHASES},
            "implementation_readiness": {"status": "complete", "source_digest": live_source},
        },
        "nodes": rows,
        "missing_sections": [],
        "verdict": "ready",
    }
    execution_tasks = []
    for index, node_id in enumerate(task_ids):
        node = by_id[node_id]
        execution_tasks.append(
            {
                "graph_node_id": node_id,
                "phase_ref": node.get("phase_ref"),
                "title": node.get("title"),
                "task_node_ref": node.get("file_path"),
                "task_spec_ref": f"{staging_rel}/{task_paths[index]}",
                "depends_on": node.get("depends_on") or [],
                "resource_scope": node.get("resource_scope") or [],
                "source_digest": (node.get("source_lineage") or {}).get("source_digest"),
            }
        )
    handoff = {
        "schema_version": "1.0.0",
        "kind": "capability-build-handoff",
        "status": "handoff_ready",
        "handoff_target": args.handoff_target,
        "generated_at": now,
        "generated_by": {"plugin": "dev-graph", "skill": "run-dev-graph-requirements", "component": "C04"},
        "identity": {
            "feature_id": feature_id,
            "feature_package_id": package.get("feature_package_id"),
            "parent_feature": package.get("parent_feature"),
            "source_feature_digest": package.get("source_feature_digest"),
        },
        "snapshot": {
            "graph_ref": str(graph_path.relative_to(repo_root)),
            "graph_snapshot_digest": graph_digest,
            "readiness_digest": readiness_digest,
            "plan_digest": plan_digest,
        },
        "requirements": {
            "document_ref": str(requirements_path.relative_to(repo_root)),
            "readiness_matrix_ref": str(matrix_path.relative_to(repo_root)),
            "items": requirements,
            "scope_out": feature.get("scope_out") or [],
        },
        "package_reference": {
            "owner_plugin": "system-dev-planner",
            "package_ref": str(package_path.relative_to(repo_root)),
            "task_count": 13,
            "phase_refs": PHASES,
            "task_spec_paths": task_paths,
        },
        "execution_tasks": execution_tasks,
        "lineage": [
            {
                "graph_node_id": _node_id(node),
                "artifact_kind": node.get("artifact_kind"),
                "file_path": node.get("file_path"),
                "source_lineage": node.get("source_lineage"),
            }
            for node in [feature, *related]
        ],
        "code_generation": {"generated_by_this_skill": 0, "generated_files": [], "policy": "delegated-to-capability-build"},
        "missing_sections": [],
        "blockers": [],
    }
    lines = [
        f"# 実装要件定義: {feature.get('title') or feature_id}",
        "",
        "本書は確定 system-spec lineage と system-dev-planner exact-13 package から導出した handoff である。",
        "実装コードは生成せず、capability-build/task-graph へ委譲する。",
        "",
        "## 要件",
        "",
    ]
    lines.extend(f"- **{item['requirement_id']}** {item['statement']}" for item in requirements)
    lines.extend(["", "## exact-13 実行タスク", ""])
    lines.extend(
        f"- `{task['phase_ref']}` `{task['graph_node_id']}` — {task['title']}"
        for task in execution_tasks
    )
    lines.extend(
        [
            "",
            "## 検証済み digest",
            "",
            f"- graph: `{graph_digest}`",
            f"- readiness: `{readiness_digest}`",
            f"- system plan: `{plan_digest}`",
            "",
        ]
    )
    write_count = _atomic_text_if_changed(requirements_path, "\n".join(lines))
    write_count += _atomic_json_if_changed(matrix_path, matrix)
    handoff["artifact_digests"] = {
        "requirements": _sha_file(requirements_path),
        "readiness_matrix": _sha_file(matrix_path),
    }
    # The handoff is the commit marker and is therefore emitted last. Consumers
    # reject a partial generation because no new digest-bound handoff exists yet.
    write_count += _atomic_json_if_changed(handoff_path, handoff)

    handoff_ref = handoff_path.relative_to(repo_root).as_posix()
    write_count += _write_anchor(
        goal_spec,
        progress,
        intermediate,
        handoff_ref,
        {"graph_snapshot_digest": graph_digest, "readiness_digest": readiness_digest},
        now,
    )
    dump(
        {
            "status": "handoff_ready",
            "handoff": str(handoff_path),
            "requirements": str(requirements_path),
            "readiness_matrix": str(matrix_path),
            "task_count": len(execution_tasks),
            "implementation_code_files": 0,
            "write_count": write_count,
            "idempotent": write_count == 0,
            "goal_anchor": {"goal_spec": str(goal_spec), "progress": str(progress), "intermediate": str(intermediate)},
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
