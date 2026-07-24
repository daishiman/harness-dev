#!/usr/bin/env python3
# /// script
# name: promote-system-plan
# purpose: readiness/validation/evaluation digest一致時のみ staged plan を atomic rename で publish する。
# inputs: argv --repo-root/--run-id/--session-owner/--staging/--findings/--readiness/--validation
# outputs: atomic receipt, registration manifest, current pointer
# contexts: [C, E]
# network: false
# write-scope: configured staging/published/state roots inside caller repository
# dependencies: [resolve-project-context.py, manage-system-plan-lock.py, validate-system-plan.py]
# requires-python: ">=3.10"
# ///
"""C11 same-digest atomic promoter."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASES = [f"P{i:02d}" for i in range(1, 14)]
REGISTRATION_NODE_KEYS = {
    "graph_node_id", "artifact_kind", "artifact_subtypes", "title", "project_id",
    "domain", "status", "owners", "tags", "priority", "start_date", "target_date",
    "iteration", "created_at", "updated_at", "depends_on", "related_nodes",
    "resource_scope", "parent_feature", "feature_package_id", "phase_ref", "file_path",
    "template_id", "template_version", "confirmation_status", "evaluation_status",
    "confirmation_evidence", "source_lineage", "classification_confidence",
    "classification_reason", "classification_candidates", "github_publication",
    "issue_linkage", "tracker_binding", "beads_linkage", "github_project_linkages",
    "pull_request_linkages", "execution_contexts", "completion_evidence",
    "implementation_readiness",
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"JSON object required: {path}")
    return value


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2); fh.write("\n"); fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _fsync_dir(path: Path) -> None:
    """Persist directory entries where the platform permits directory fsync."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_tree(root: Path) -> None:
    """Flush every regular file and directory before the rename commit point."""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with path.open("rb") as fh:
                os.fsync(fh.fileno())
    for path in sorted((x for x in root.rglob("*") if x.is_dir()), reverse=True):
        _fsync_dir(path)
    _fsync_dir(root)


def _conditions(findings: dict) -> dict:
    keys = {"C1": "no_contradiction", "C2": "no_missing", "C3": "consistent", "C4": "dependency_integrity"}
    result = {}
    for key, out in keys.items():
        condition = findings.get("conditions", {}).get(key, {})
        status = condition.get("status")
        if status != "PASS": raise ValueError(f"independent condition {key} is not PASS")
        if condition.get("id") != key:
            raise ValueError(f"independent condition {key} id mismatch")
        if not isinstance(condition.get("summary"), str) or not condition["summary"].strip():
            raise ValueError(f"independent condition {key} summary is empty")
        evidence = condition.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not item.strip() for item in evidence
        ):
            raise ValueError(f"independent condition {key} requires non-empty evidence")
        result[out] = "PASS"
    if findings.get("verdict") != "PASS": raise ValueError("independent evaluator verdict is not PASS")
    return result


def _validate_findings(findings: dict, validator) -> None:
    violations = validator.schema_violations(
        findings, validator._load_schema("plan-findings.schema.json")
    )
    if violations:
        raise ValueError("plan findings schema violation: " + "; ".join(violations))
    gates = findings["gate_results"]
    if not gates:
        raise ValueError("plan findings must contain at least one gate result")
    failed_gates = [str(gate.get("id", "<unknown>")) for gate in gates if gate.get("exit_code") != 0]
    if failed_gates:
        raise ValueError("plan findings include nonzero gate results: " + ", ".join(failed_gates))
    covered = {condition for gate in gates for condition in gate.get("conditions", [])}
    if covered != {"C1", "C2", "C3", "C4"}:
        raise ValueError("plan findings gate evidence must cover C1, C2, C3, and C4")
    for gate in gates:
        if not all(isinstance(gate.get(field), str) and gate[field].strip() for field in ("id", "name")):
            raise ValueError("plan findings gate id/name must be non-empty")
        if not isinstance(gate.get("command"), list) or not gate["command"] or any(
            not isinstance(item, str) or not item.strip() for item in gate["command"]
        ):
            raise ValueError(f"plan findings gate command is empty: {gate.get('id', '<unknown>')}")
    deterministic_gates = [gate for gate in gates if gate.get("id") == "deterministic-validation"]
    if len(deterministic_gates) != 1:
        raise ValueError("exactly one deterministic-validation gate is required")
    deterministic_gate = deterministic_gates[0]
    if deterministic_gate.get("name") != "validate-system-plan":
        raise ValueError("deterministic-validation gate name mismatch")
    command = deterministic_gate["command"]
    if (
        not any(Path(part).name == "validate-system-plan.py" for part in command)
        or "--repo-root" not in command
        or "--staging" not in command
        or set(deterministic_gate.get("conditions", [])) != {"C1", "C2", "C3", "C4"}
    ):
        raise ValueError("deterministic-validation gate command/condition contract mismatch")
    try:
        gate_stdout = json.loads(deterministic_gate.get("stdout", ""))
    except json.JSONDecodeError as exc:
        raise ValueError("deterministic-validation stdout must be JSON") from exc
    if (
        not isinstance(gate_stdout, dict)
        or gate_stdout.get("status") != "pass"
        or gate_stdout.get("validated_digest") != findings.get("evaluated_digest")
    ):
        raise ValueError("deterministic-validation stdout digest/status mismatch")
    high_findings = [item for item in findings["findings"] if item.get("severity") == "high"]
    if high_findings:
        raise ValueError("plan findings include unresolved high-severity findings")


def _validate_evaluated_inputs(findings: dict, staging: Path) -> None:
    """Bind fork-review evidence to the exact current staging byte set."""
    if not isinstance(findings.get("staleness_rule"), str) or not findings["staleness_rule"].strip():
        raise ValueError("plan findings staleness_rule is required")
    manifest = _json(staging / "staging-manifest.json")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        raise ValueError("staging manifest files must be an object")
    expected = set(manifest_files) | {"staging-manifest.json"}
    entries = findings.get("evaluated_inputs")
    if not isinstance(entries, list) or not entries:
        raise ValueError("plan findings evaluated_inputs are required")
    provided: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ValueError("plan findings evaluated_inputs entry shape mismatch")
        rel = entry["path"]
        if (
            not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts
            or rel in provided
        ):
            raise ValueError("plan findings evaluated_inputs path is invalid or duplicated")
        provided[rel] = entry["sha256"]
    if set(provided) != expected:
        raise ValueError("plan findings evaluated_inputs exact-set mismatch")
    for rel, expected_sha in provided.items():
        actual = hashlib.sha256((staging / rel).read_bytes()).hexdigest()
        if expected_sha != actual:
            raise ValueError(f"plan findings evaluated_inputs digest mismatch: {rel}")
    allowed_evidence = expected | {f"gate:{gate['id']}" for gate in findings["gate_results"]}
    for key, condition in findings["conditions"].items():
        for evidence in condition["evidence"]:
            if evidence.split("#", 1)[0] not in allowed_evidence:
                raise ValueError(f"independent condition {key} evidence is not bound to evaluated inputs")


def _validate_readiness(readiness: dict, repository_id: str) -> None:
    required = {
        "status", "missing_sections", "checked_at", "repository_id", "source_pin", "probes",
        "system_spec_root", "architecture_root", "completeness_report",
    }
    missing = sorted(required - set(readiness))
    if missing:
        raise ValueError("readiness report missing fields: " + ", ".join(missing))
    if readiness["status"] != "complete":
        raise ValueError("implementation_readiness is not complete")
    if readiness["missing_sections"] != []:
        raise ValueError("implementation_readiness has unresolved missing_sections")
    if readiness["repository_id"] != repository_id:
        raise ValueError("readiness repository_id does not match caller repository")
    checked_at = readiness["checked_at"]
    if not isinstance(checked_at, str):
        raise ValueError("readiness checked_at must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError as exc:
        raise ValueError("readiness checked_at must be an RFC3339 timestamp") from exc

    probes = readiness["probes"]
    if not isinstance(probes, dict):
        raise ValueError("readiness probes must be an object")
    for name in (
        "system_spec_index", "requirements_definition", "architecture_graph",
        "completeness_evaluation", "source_plugin_manifest",
    ):
        probe = probes.get(name)
        if not isinstance(probe, dict):
            raise ValueError(f"readiness probe is missing: {name}")
        if any(probe.get(field) is not True for field in ("exists", "non_empty", "placeholder_free")):
            raise ValueError(f"readiness probe is not satisfied: {name}")
        if probe.get("verified") is not True:
            raise ValueError(f"readiness probe is not producer-verified: {name}")
        if name != "architecture_graph":
            count = probe.get("heading_count")
            if name in {"system_spec_index", "requirements_definition"} and (
                not isinstance(count, int) or isinstance(count, bool) or count < 1
            ):
                raise ValueError(f"readiness markdown probe has no heading: {name}")

    source_pin = readiness["source_pin"]
    expected_pin = {
        "plugin": "system-spec-harness",
        "version": "0.1.0",
        "compile_entrypoint": "run-system-spec-compile",
        "completeness_entrypoint": "assign-system-spec-completeness-evaluator",
    }
    if not isinstance(source_pin, dict) or any(source_pin.get(key) != value for key, value in expected_pin.items()):
        raise ValueError("readiness source_pin does not match the required producer contract")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", str(source_pin.get("source_digest", ""))) is None:
        raise ValueError("readiness source_pin source_digest is invalid")


def _validate_generated_artifacts(registration: dict, receipt: dict, validator) -> None:
    receipt_errors = validator.schema_violations(
        receipt, validator._load_schema("atomic-promotion-receipt.schema.json")
    )
    if receipt_errors:
        raise ValueError("promotion receipt schema violation: " + "; ".join(receipt_errors))

    # The registration schema's node item delegates to dev-graph through an
    # external $ref.  C11 owns only the local envelope here; C02 validates the
    # transformed dev-graph nodes before its all-or-none transaction.
    registration_schema = validator._load_schema("dev-graph-registration.schema.json")
    local_schema = json.loads(json.dumps(registration_schema))
    local_schema["properties"]["nodes"]["items"] = {}
    registration_errors = validator.schema_violations(registration, local_schema)
    if registration_errors:
        raise ValueError("registration schema violation: " + "; ".join(registration_errors))
    node_ids = [str(node.get("graph_node_id", node.get("id", ""))) for node in registration["nodes"]]
    phases = [node.get("phase_ref") for node in registration["nodes"]]
    if len(set(node_ids)) != 13 or any(not node_id for node_id in node_ids):
        raise ValueError("registration nodes must contain 13 unique ids")
    if set(registration["binding_intents"]) != set(node_ids):
        raise ValueError("registration binding_intents must exactly match node ids")
    if phases != PHASES:
        raise ValueError("registration node phases must be ordered P01..P13")
    for index, node in enumerate(registration["nodes"]):
        if set(node) != REGISTRATION_NODE_KEYS:
            raise ValueError(
                f"registration nodes[{index}] field exact-set mismatch: "
                f"{sorted(set(node) ^ REGISTRATION_NODE_KEYS)}"
            )
        if node["artifact_kind"] != "task" or node["artifact_subtypes"] != []:
            raise ValueError(f"registration nodes[{index}] is not a canonical task")
        if node["status"] != "active" or node["confirmation_status"] != "confirmed" or node["evaluation_status"] != "pass":
            raise ValueError(f"registration nodes[{index}] is not active/confirmed/pass")
        if node["tracker_binding"] != "repo-config-default":
            raise ValueError(f"registration nodes[{index}] lost the unresolved binding sentinel")
        if node["implementation_readiness"].get("status") != "complete":
            raise ValueError(f"registration nodes[{index}] readiness is incomplete")


def _registration_nodes(*, inventory: dict, package: dict, destination_rel: str,
                        digest: str, findings_rel: str, promoted_at: str) -> list[dict]:
    """Transform typed inventory tasks into dev-graph's canonical task-node contract."""
    project_id = re.sub(r"[^A-Za-z0-9._-]+", "-", package["feature_package_id"]).strip("-")
    digest_hex = digest.removeprefix("sha256:")
    nodes: list[dict] = []
    for index, task in enumerate(inventory.get("tasks", [])):
        registration = task.get("graph_node_registration") or {}
        node_id = registration.get("graph_node_id") or task.get("id")
        file_path = registration.get("file_path")
        if node_id != task.get("id"):
            raise ValueError(f"task {task.get('id')} graph_node_registration id mismatch")
        parent_feature = task.get("parent_feature")
        if (
            not isinstance(file_path, str)
            or re.fullmatch(r"tasks/[A-Za-z0-9._-]+/[^/]+\.md", file_path) is None
            or ".." in Path(file_path).parts
            or not isinstance(parent_feature, str)
            or not file_path.startswith(f"tasks/{parent_feature}/")
        ):
            raise ValueError(
                f"task {task.get('id')} registration file_path must be "
                "tasks/<parent_feature>/<file>.md (feature 単位の namespace 分離)"
            )
        for field in ("parent_feature", "feature_package_id", "phase_ref"):
            if registration.get(field) != task.get(field):
                raise ValueError(f"task {task.get('id')} graph_node_registration {field} mismatch")
        classification = task.get("classification") or {}
        # Keep the mapping explicit and stable without importing the validator
        # module into this pure transformation.
        task_spec_paths = [
            "task-specs/phase-01-requirements.md", "task-specs/phase-02-architecture.md",
            "task-specs/phase-03-design-review.md", "task-specs/phase-04-test-design.md",
            "task-specs/phase-05-implementation.md", "task-specs/phase-06-test-run.md",
            "task-specs/phase-07-acceptance.md", "task-specs/phase-08-refactoring-migration.md",
            "task-specs/phase-09-quality-assurance.md", "task-specs/phase-10-final-review.md",
            "task-specs/phase-11-evidence.md", "task-specs/phase-12-documentation-operations.md",
            "task-specs/phase-13-release-deploy.md",
        ]
        task_spec_rel = task_spec_paths[index]
        nodes.append({
            "graph_node_id": node_id,
            "artifact_kind": "task", "artifact_subtypes": [], "title": task["title"],
            "project_id": project_id, "domain": task["workstream_kind"], "status": "active",
            "owners": task["owners"], "tags": task["tags"],
            "priority": task.get("priority"), "start_date": task.get("start_date"),
            "target_date": task.get("target_date"), "iteration": task.get("iteration"),
            "created_at": promoted_at, "updated_at": promoted_at,
            "depends_on": task["depends_on"], "related_nodes": task["related_nodes"],
            "resource_scope": task["write_scope"], "parent_feature": package["parent_feature"],
            "feature_package_id": package["feature_package_id"], "phase_ref": task["phase_ref"],
            "file_path": file_path, "template_id": "task", "template_version": "1.0.0",
            "confirmation_status": "confirmed", "evaluation_status": "pass",
            "confirmation_evidence": {
                "evaluator": "system-dev-plan-evaluator", "evidence_ref": findings_rel,
                "evaluated_digest": digest_hex,
            },
            "source_lineage": {
                "origin_kind": "system-dev-planner", "source_plugin": "system-dev-planner",
                "source_path": f"{destination_rel}/{task_spec_rel}", "source_version": "0.1.0",
                "source_digest": digest_hex, "imported_at": promoted_at,
            },
            "classification_confidence": classification["confidence"],
            "classification_reason": classification["reason"],
            "classification_candidates": classification["candidates"],
            "github_publication": task["github_publication"],
            "issue_linkage": None, "tracker_binding": "repo-config-default", "beads_linkage": None,
            "github_project_linkages": [], "pull_request_linkages": [], "execution_contexts": [],
            "completion_evidence": {
                "policy": task["pr_completion_policy"], "status": "in_progress", "source": None,
                "completed_at": None, "reconciled_at": None, "evidence_refs": [],
            },
            "implementation_readiness": task["implementation_readiness"],
        })
    return nodes


def _intent_path(root: Path, context: dict, staging_rel: str) -> Path:
    key = hashlib.sha256(staging_rel.encode("utf-8")).hexdigest()
    state_root = context["plan_roots"]["state"]["relative"]
    return root / state_root / "promotion-intents" / f"{key}.json"


def _current_payload(intent: dict) -> dict:
    return {
        "schema_version": "1.0.0", "feature_package_id": intent["feature_package_id"],
        "published_path": intent["destination"], "published_digest": intent["digest"],
        "receipt": intent["receipt"],
    }


def _validate_feature_pin(package: dict, context: dict) -> None:
    feature = context.get("feature_context")
    if not isinstance(feature, dict):
        raise ValueError("promotion requires C09-validated feature context")
    if package.get("parent_feature") != feature.get("graph_node_id"):
        raise ValueError("package parent_feature does not match feature context")
    if package.get("source_feature_digest") != f"sha256:{feature.get('sha256')}":
        raise ValueError("package source_feature_digest does not match current feature context bytes")


def _validate_handoff_boundary(handoff: dict) -> None:
    """Require C14's declared ownership boundary before C11 emits receipts."""
    request = handoff.get("registration_request")
    if not isinstance(request, dict):
        raise ValueError("system handoff registration_request is missing")
    expected = {
        "path": "dev-graph-registration.json",
        "owner": "system-dev-planner/C11",
        "consumer": "dev-graph/C02",
        "status": "deferred-until-promotion",
    }
    if any(request.get(key) != value for key, value in expected.items()):
        raise ValueError("system handoff registration request ownership mismatch")
    promotion = request.get("promotion_receipt")
    registration = request.get("registration_receipt")
    if not isinstance(promotion, dict) or (
        promotion.get("path") != "atomic-promotion-receipt.json"
        or promotion.get("owner") != "system-dev-planner/C11"
        or promotion.get("status") != "not-emitted"
        or promotion.get("produced_by_this_component") is not False
    ):
        raise ValueError("system handoff promotion receipt ownership mismatch")
    if not isinstance(registration, dict) or (
        registration.get("path") != "dev-graph-registration-receipt.json"
        or registration.get("owner") != "dev-graph/C02"
        or registration.get("status") != "not-emitted"
        or registration.get("produced_by_this_component") is not False
    ):
        raise ValueError("system handoff registration receipt ownership mismatch")


def _validate_active_plan_lock(root: Path, context: dict, package: dict, args, c09, lock_manager) -> dict:
    """Require the exact C13 owner lock before any promotion/recovery write."""
    locks_rel = context["local_state"]["locks"]["relative"]
    locks = Path(c09.guard_relative_path(root, locks_rel))
    return lock_manager.validate_active_lock(
        repo_root=root,
        locks=locks,
        repository_id=context["repository_id"],
        run_id=args.run_id,
        session_owner=args.session_owner,
        feature_id=package["parent_feature"],
        feature_digest=package["source_feature_digest"],
    )


def _recover_published(root: Path, context: dict, intent_path: Path, intent: dict, c09, validator) -> dict:
    """Finish an interrupted post-rename current-pointer update idempotently."""
    destination = Path(c09.guard_relative_path(root, intent["destination"]))
    receipt_path = destination / "atomic-promotion-receipt.json"
    registration_path = destination / "dev-graph-registration.json"
    findings_path = destination / "plan-findings.json"
    if not receipt_path.is_file() or not registration_path.is_file() or not findings_path.is_file():
        raise ValueError("published generation is incomplete; receipt/registration/findings missing")
    receipt = _json(receipt_path)
    registration = _json(registration_path)
    findings = _json(findings_path)
    digest = intent["digest"]
    deterministic = validator.validate(destination, context["repository_id"])
    if deterministic.get("status") != "pass" or deterministic.get("validated_digest") != digest:
        raise ValueError("published generation bytes do not match promotion intent digest")
    if receipt.get("status") != "promoted" or any(
        receipt.get(key) != digest for key in ("staging_digest", "evaluated_digest", "published_digest")
    ):
        raise ValueError("published generation does not match promotion intent")
    _validate_findings(findings, validator)
    _validate_evaluated_inputs(findings, destination)
    _validate_feature_pin(_json(destination / "feature-package.json"), context)
    _validate_handoff_boundary(_json(destination / "system-build-handoff.json"))
    _validate_generated_artifacts(registration, receipt, validator)
    if findings.get("evaluated_digest") != digest or registration.get("source_digest") != digest:
        raise ValueError("published findings/registration digest does not match promotion intent")
    state_root = context["plan_roots"]["state"]["relative"]
    current = Path(c09.guard_relative_path(root, f"{state_root}/current.json"))
    _atomic_json(current, _current_payload(intent))
    completed = dict(intent, status="completed", completed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    _atomic_json(intent_path, completed)
    return receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Atomically promote a validated system plan")
    p.add_argument("--repo-root"); p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--feature-id", required=True); p.add_argument("--feature-context", required=True)
    p.add_argument("--run-id", required=True); p.add_argument("--session-owner", required=True)
    p.add_argument("--staging", required=True); p.add_argument("--findings", required=True)
    p.add_argument("--readiness", required=True); p.add_argument("--validation", required=True)
    p.add_argument("--destination", help="repo-relative destination; default configured published/<package-slug>")
    args = p.parse_args(argv)
    c09 = _load("sdp_context", HERE / "resolve-project-context.py")
    lock_manager = _load("sdp_lock_manager", HERE / "manage-system-plan-lock.py")
    validator = _load("sdp_validator", HERE / "validate-system-plan.py")
    readiness_gate = _load("sdp_readiness", HERE / "check-implementation-readiness.py")
    try:
        cargs = ["--config", args.config]
        if args.repo_root: cargs[:0] = ["--repo-root", args.repo_root]
        cargs += ["--feature-id", args.feature_id, "--feature-context", args.feature_context]
        context = c09.build_context(cargs, dict(os.environ)); root = Path(context["repo_root"])
        staging = Path(c09.guard_relative_path(root, args.staging))
        intent_path = _intent_path(root, context, args.staging)
        if not staging.exists() and intent_path.is_file():
            intent = _json(intent_path)
            recovered_destination = Path(c09.guard_relative_path(root, intent["destination"]))
            recovered_package = _json(recovered_destination / "feature-package.json")
            _validate_feature_pin(recovered_package, context)
            _validate_active_plan_lock(root, context, recovered_package, args, c09, lock_manager)
            receipt = _recover_published(root, context, intent_path, intent, c09, validator)
            print(json.dumps(receipt, ensure_ascii=False, indent=2)); return 0
        findings = _json(Path(c09.guard_relative_path(root, args.findings)))
        readiness = _json(Path(c09.guard_relative_path(root, args.readiness)))
        validation = _json(Path(c09.guard_relative_path(root, args.validation)))
        deterministic = validator.validate(staging, context["repository_id"])
        _validate_findings(findings, validator)
        if findings.get("plan_dir") != args.staging:
            raise ValueError("plan findings plan_dir does not match promotion staging")
        _validate_evaluated_inputs(findings, staging)
        _validate_readiness(readiness, context["repository_id"])
        for rel in (
            readiness["system_spec_root"], readiness["architecture_root"],
            readiness["completeness_report"],
        ):
            c09.guard_relative_path(root, rel)
        fresh_readiness = readiness_gate.build_report(
            context,
            readiness["system_spec_root"],
            readiness["architecture_root"],
            readiness["completeness_report"],
        )
        if fresh_readiness["status"] != "complete":
            raise ValueError("current implementation_readiness is not complete")
        if fresh_readiness["source_pin"]["source_digest"] != readiness["source_pin"]["source_digest"]:
            raise ValueError("readiness source bytes changed after evaluation")
        if validation.get("status") != "pass" or deterministic.get("status") != "pass":
            raise ValueError("deterministic validation is not PASS")
        digest = deterministic.get("validated_digest")
        if not digest or validation.get("validated_digest") != digest or findings.get("evaluated_digest") != digest:
            raise ValueError("staging/validation/evaluator digest mismatch")
        quality = _conditions(findings)
        package = _json(staging / "feature-package.json")
        _validate_feature_pin(package, context)
        _validate_active_plan_lock(root, context, package, args, c09, lock_manager)
        _validate_handoff_boundary(_json(staging / "system-build-handoff.json"))
        inventory = _json(staging / "workstream-inventory.json")
        package_id = package["feature_package_id"]
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", package_id).strip("-")
        published_root = context["plan_roots"]["published"]["relative"]
        destination_rel = args.destination or f"{published_root}/{slug}"
        destination = Path(c09.guard_relative_path(root, destination_rel))
        if not staging.is_dir(): raise ValueError("staging generation is not a directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        promoted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        findings_rel = f"{destination_rel}/plan-findings.json"
        nodes = _registration_nodes(
            inventory=inventory, package=package, destination_rel=destination_rel,
            digest=digest, findings_rel=findings_rel, promoted_at=promoted_at,
        )
        binding_intents = {}
        tasks_by_phase = {x.get("phase_ref"): x for x in inventory.get("tasks", [])}
        for node in nodes:
            node_id = str(node.get("graph_node_id", node.get("id", "")))
            binding_intents[node_id] = tasks_by_phase.get(node.get("phase_ref"), {}).get("tracker_binding_intent", "auto")
        registration_rel = f"{destination_rel}/dev-graph-registration.json"
        receipt_rel = f"{destination_rel}/atomic-promotion-receipt.json"
        registration = {
            "schema_version": "1.0.0", "source_digest": digest, "promotion_receipt": receipt_rel,
            "feature_package_id": package_id, "parent_feature": package["parent_feature"],
            "expected_count": 13, "phase_refs": PHASES, "binding_intents": binding_intents, "nodes": nodes,
        }
        receipt = {
            "schema_version": "1.0.0", "status": "promoted",
            "promoted_at": promoted_at,
            "repo_identity": context["repository_id"], "staging_digest": digest,
            "evaluated_digest": digest, "published_digest": digest,
            "implementation_readiness": "complete", "quality_conditions": quality,
            "promotion_method": "same-filesystem-atomic-rename", "registration_manifest": registration_rel,
        }
        _validate_generated_artifacts(registration, receipt, validator)
        intent = {
            "schema_version": "1.0.0", "status": "prepared", "staging": args.staging,
            "destination": destination_rel, "digest": digest, "feature_package_id": package_id,
            "receipt": receipt_rel,
        }
        _atomic_json(intent_path, intent)
        if destination.exists():
            recovered = _recover_published(root, context, intent_path, intent, c09, validator)
            print(json.dumps(recovered, ensure_ascii=False, indent=2)); return 0
        if staging.stat().st_dev != destination.parent.stat().st_dev:
            raise ValueError("staging and published destination are on different filesystems")

        # Receipt and registration are part of the generation and must be durable
        # before the only commit point. No partial published directory is exposed.
        _atomic_json(staging / "dev-graph-registration.json", registration)
        _atomic_json(staging / "atomic-promotion-receipt.json", receipt)
        _atomic_json(staging / "plan-findings.json", findings)
        _fsync_tree(staging)
        os.replace(staging, destination)
        _fsync_dir(destination.parent)
        _recover_published(root, context, intent_path, intent, c09, validator)
        print(json.dumps(receipt, ensure_ascii=False, indent=2)); return 0
    except (OSError, json.JSONDecodeError) as exc: print(f"[promote] {exc}", file=sys.stderr); return 1
    except (ValueError, c09.PolicyError, c09.UsageError, lock_manager.DomainBlock, lock_manager.ContractError) as exc:
        print(f"[promote fail-closed] {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
