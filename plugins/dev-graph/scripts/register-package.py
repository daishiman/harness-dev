#!/usr/bin/env python3
# /// script
# name: register-package
# purpose: Provide the C02 single-writer entrypoints for normal artifacts, macro preview, exact-13 registration, and execution-context projection.
# inputs: ["argv: artifacts --repo-root/--input/--plan/--patches?/--initial-state?/--system-spec-attestation?/--dry-run", "argv: preview-macro --repo-root/--graph/--request-json --dry-run", "argv: apply-macro --repo-root/--graph/--request-json/--expected-candidate-digest/--receipt", "argv: register --package/--graph/--output/--receipt", "argv: execution-context --graph/--graph-node-id/--context-json", "argv: preflight"]
# outputs: ["stdout: JSON preview/receipt/preflight report"]
# requires-python = ">=3.10"
# dependencies: [_common.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: explicitly selected dev-graph output, immutable receipt, and content-addressed legacy revalidation evidence
# ///
"""C02 graph preview/registration consumer and cross-plugin preflight."""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from _common import (
    ContractError,
    atomic_json,
    c11_readiness_digest,
    canonical_digest,
    contained,
    dump,
    load_json,
    utc_now,
)

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DEFAULT_SYSTEM_ROOT = PLUGIN_ROOT.parent / "system-dev-planner"
PHASES = [f"P{i:02d}" for i in range(1, 14)]
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
REGISTRATION_KEYS = {
    "schema_version", "source_digest", "promotion_receipt", "feature_package_id",
    "parent_feature", "expected_count", "phase_refs", "binding_intents", "nodes",
}
RECEIPT_STABLE_KEYS = {
    "schema_version", "status", "feature_package_id", "parent_feature", "source_digest",
    "expected_count", "applied_count", "phase_refs", "node_ids", "graph_revision_before",
    "graph_revision_after", "graph_digest_after", "c11_readiness_digest", "output_path",
}
MACRO_INTENT_SCHEMA = PLUGIN_ROOT / "schemas" / "macro-intent.schema.json"
MACRO_RECEIPT_SCHEMA = PLUGIN_ROOT / "schemas" / "macro-registration-receipt.schema.json"
PACKAGE_EVIDENCE_SCHEMA = PLUGIN_ROOT / "schemas" / "package-registration-evidence.schema.json"
ARTIFACT_KINDS = {"issue", "task", "specification", "architecture", "document", "feature"}
NORMAL_ARTIFACT_KINDS = ARTIFACT_KINDS - {"feature"}
ROOT_BY_KIND = {
    "issue": "issues", "task": "tasks", "specification": "specs",
    "architecture": "architecture", "feature": "features", "document": "docs",
}
ARTIFACT_PLAN_KEYS = {"schema_version", "observed_at", "decisions"}
ARTIFACT_DECISION_KEYS = {
    "input_index", "artifact_kind", "artifact_subtypes", "project_id", "domain",
    "owners", "tags", "priority", "resource_scope", "classification_confidence",
    "classification_reason", "classification_candidates", "decision_source",
    "tracker_binding", "depends_on_titles", "related_node_titles",
    "architecture_ref_titles", "rendered_body",
}
ARTIFACT_CANDIDATE_KEYS = {"artifact_kind", "confidence"}
PATCH_PLAN_KEYS = {"patches"}
PATCH_KEYS = {"input_index", "append_sections"}
PATCH_SECTION_KEYS = {"heading", "body"}
INITIAL_STATE_KEYS = {"schema_version", "states"}
INITIAL_STATE_ROW_KEYS = {"input_index", "status", "closed_at"}
SYSTEM_SPEC_ATTESTATION_KEYS = {
    "schema_version", "source_plugin", "source_version", "delegation_receipt_ref",
    "delegation_receipt_sha256", "delegation_progress_ref", "delegation_progress_sha256",
    "artifacts",
}
SYSTEM_SPEC_ATTESTATION_ROW_KEYS = {"input_index", "source_ref", "source_sha256"}
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _schema_error(path: str, detail: str) -> ContractError:
    return ContractError(f"schema violation at {path}: {detail}")


def _is_type(value: Any, expected: str) -> bool:
    if expected == "null": return value is None
    if expected == "object": return isinstance(value, dict)
    if expected == "array": return isinstance(value, list)
    if expected == "string": return isinstance(value, str)
    if expected == "boolean": return isinstance(value, bool)
    if expected == "integer": return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number": return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _matches(value: Any, schema: Any, root: dict[str, Any]) -> bool:
    try:
        _validate_schema(value, schema, root, "$")
        return True
    except ContractError:
        return False


def _validate_schema(value: Any, schema: Any, root: dict[str, Any], path: str) -> None:
    """Validate the stdlib-only subset used by the local package/node schemas."""
    if schema is True: return
    if schema is False: raise _schema_error(path, "value is forbidden")
    if not isinstance(schema, dict): raise _schema_error(path, "invalid schema object")
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith("#/"):
            raise _schema_error(path, f"external $ref is not supported here: {ref}")
        target: Any = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        _validate_schema(value, target, root, path)
    for child in schema.get("allOf", []): _validate_schema(value, child, root, path)
    if "if" in schema and _matches(value, schema["if"], root) and "then" in schema:
        _validate_schema(value, schema["then"], root, path)
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, item) for item in choices):
            raise _schema_error(path, f"expected type {choices}, got {type(value).__name__}")
    if "const" in schema and value != schema["const"]:
        raise _schema_error(path, f"expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise _schema_error(path, f"not in enum {schema['enum']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): raise _schema_error(path, "string too short")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise _schema_error(path, f"does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]: raise _schema_error(path, "below minimum")
        if "maximum" in schema and value > schema["maximum"]: raise _schema_error(path, "above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): raise _schema_error(path, "too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]: raise _schema_error(path, "too many items")
        if schema.get("uniqueItems"):
            packed = [json.dumps(x, sort_keys=True, separators=(",", ":")) for x in value]
            if len(set(packed)) != len(packed): raise _schema_error(path, "items are not unique")
        prefix = schema.get("prefixItems", [])
        for index, child in enumerate(prefix[:len(value)]):
            _validate_schema(value[index], child, root, f"{path}[{index}]")
        items = schema.get("items")
        if items is False and len(value) > len(prefix): raise _schema_error(path, "additional items forbidden")
        if isinstance(items, dict):
            for index, item in enumerate(value): _validate_schema(item, items, root, f"{path}[{index}]")
        if "contains" in schema and not any(_matches(item, schema["contains"], root) for item in value):
            raise _schema_error(path, "contains constraint not satisfied")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value: raise _schema_error(path, f"missing required property {key}")
        props = schema.get("properties", {})
        for key, child in props.items():
            if key in value: _validate_schema(value[key], child, root, f"{path}.{key}")
        additional = schema.get("additionalProperties", True)
        unknown = set(value) - set(props)
        if additional is False and unknown: raise _schema_error(path, f"unknown properties {sorted(unknown)}")
        if isinstance(additional, dict):
            for key in unknown: _validate_schema(value[key], additional, root, f"{path}.{key}")
        if len(value) < schema.get("minProperties", 0): raise _schema_error(path, "too few properties")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            raise _schema_error(path, "too many properties")


def _path(root: Path, raw: str, *, must_exist: bool) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute(): candidate = root / candidate
    if must_exist: return contained(candidate, root, must_exist=True)
    parent = contained(candidate.parent, root, must_exist=True)
    return parent / candidate.name


def _artifact_target(root: Path, raw: str, *, durable: bool) -> Path:
    """Resolve one canonical artifact leaf and reject ambiguous occupancy.

    Artifact paths stored in the graph are repository-relative.  Validate that
    lexical projection and the existing parent realpath both remain under the
    repository authority, then inspect the leaf without following it.  This is
    deliberately stricter than ``Path.is_file()`` alone: broken, in-repository,
    and escaping symlinks must all fail closed.
    """
    authority = root.resolve(strict=True)
    relative = Path(raw)
    if relative.is_absolute():
        raise ContractError(f"artifact path must be repository-relative: {raw}")
    lexical = Path(os.path.abspath(authority / relative))
    try:
        lexical.relative_to(authority)
    except ValueError as exc:
        raise ContractError(f"artifact path escapes authority root: {raw}") from exc
    target = _path(authority, raw, must_exist=False)
    if target.is_symlink():
        raise ContractError(f"artifact path must not be a symlink: {raw}")
    if durable:
        if not target.is_file():
            raise ContractError(f"durable artifact path must be an existing regular file: {raw}")
    elif target.exists():
        raise ContractError(f"artifact path already exists without durable graph node: {raw}")
    return target


def _json_object(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict): raise ContractError(f"JSON object required: {path}")
    return value


def _canonical_digest(value: Any) -> str:
    """Compatibility wrapper for callers/tests; SSOT lives in _common.py."""
    return canonical_digest(value)


def _schema_version(schema: dict[str, Any], name: str) -> str:
    value = (((schema.get("properties") or {}).get("schema_version") or {}).get("const"))
    if not isinstance(value, str): raise ContractError(f"{name} does not pin properties.schema_version.const")
    return value


def preflight_contract(system_root: Path, required_version: str | None, required_schema_version: str) -> dict[str, Any]:
    root = system_root.resolve(strict=True)
    manifest = _json_object(root / ".claude-plugin" / "plugin.json")
    if manifest.get("name") != "system-dev-planner": raise ContractError("unexpected upstream plugin name")
    # 既定は literal pin を置かない: upstream の patch bump で必ず外れる一方、契約の
    # 実体は entry_points と schema_version const が固定する。呼び出し側が
    # --required-version を明示したときだけ従来どおり厳密一致を要求する。
    observed_version = manifest.get("version")
    if not isinstance(observed_version, str) or re.fullmatch(r"\d+\.\d+\.\d+", observed_version) is None:
        raise ContractError(f"system-dev-planner version is missing or not semver: {observed_version!r}")
    if required_version is not None and observed_version != required_version:
        raise ContractError(f"system-dev-planner version mismatch: expected {required_version}, got {observed_version}")
    package_contract = _json_object(root / "references" / "package-contract.json")
    if package_contract.get("plugin_name") != "system-dev-planner":
        raise ContractError("system-dev-planner package contract identity mismatch")
    entry_points = package_contract.get("entry_points")
    if not isinstance(entry_points, dict):
        raise ContractError("system-dev-planner package contract entry_points missing")
    required = {
        "skills": ["run-system-dev-plan", "assign-system-dev-plan-evaluator"],
        "agents": ["system-dev-plan-elicitor", "system-dev-plan-architect", "system-dev-plan-evaluator"],
        "commands": ["system-dev-plan"],
    }
    suffixes = {"skills": "SKILL.md", "agents": ".md", "commands": ".md"}
    for kind, names in required.items():
        declared = entry_points.get(kind)
        if not isinstance(declared, list) or not set(names).issubset(set(declared)):
            raise ContractError(f"missing required {kind} entrypoints: {sorted(set(names) - set(declared or []))}")
        for name in names:
            physical = root / kind / name / suffixes[kind] if kind == "skills" else root / kind / f"{name}{suffixes[kind]}"
            if not physical.is_file(): raise ContractError(f"declared entrypoint is missing: {physical}")
    schemas = {}
    for filename in ("feature-execution-package.schema.json", "dev-graph-registration.schema.json"):
        schema = _json_object(root / "schemas" / filename)
        version = _schema_version(schema, filename)
        if version != required_schema_version:
            raise ContractError(f"{filename} version mismatch: expected {required_schema_version}, got {version}")
        schemas[filename] = version
    for filename in ("validate-system-plan.py", "promote-system-plan.py"):
        if not (root / "scripts" / filename).is_file(): raise ContractError(f"required upstream script missing: {filename}")
    return {"valid": True, "plugin": "system-dev-planner", "version": observed_version,
            "entrypoint_source": "references/package-contract.json",
            "schema_versions": schemas, "required_entrypoints": required}


def _validate_package(package: dict[str, Any], schema: dict[str, Any]) -> None:
    _validate_schema(package, schema, schema, "feature-package")
    if package["phase_refs"] != PHASES or package["task_count"] != 13:
        raise ContractError("feature package is not exact P01..P13")


def _validate_registration(registration: dict[str, Any], package: dict[str, Any], node_schema: dict[str, Any]) -> list[dict[str, Any]]:
    if set(registration) != REGISTRATION_KEYS:
        raise ContractError(f"registration keys mismatch: {sorted(set(registration) ^ REGISTRATION_KEYS)}")
    if registration.get("schema_version") != "1.0.0": raise ContractError("registration schema_version must be 1.0.0")
    if not SHA256.fullmatch(str(registration.get("source_digest", ""))): raise ContractError("invalid source_digest")
    if registration.get("expected_count") != 13 or registration.get("phase_refs") != PHASES:
        raise ContractError("registration is not exact P01..P13")
    if registration.get("feature_package_id") != package.get("feature_package_id"):
        raise ContractError("feature_package_id mismatch")
    if registration.get("parent_feature") != package.get("parent_feature"):
        raise ContractError("parent_feature mismatch")
    nodes = registration.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 13: raise ContractError("registration nodes must contain exactly 13 objects")
    phases = [node.get("phase_ref") if isinstance(node, dict) else None for node in nodes]
    if phases != PHASES: raise ContractError(f"node phase exact-set mismatch: {phases}")
    node_ids = [node.get("graph_node_id") if isinstance(node, dict) else None for node in nodes]
    if node_ids != package.get("task_node_ids") or len(set(node_ids)) != 13:
        raise ContractError("node ids must equal package.task_node_ids in phase order")
    intents = registration.get("binding_intents")
    if not isinstance(intents, dict) or set(intents) != set(node_ids):
        raise ContractError("binding_intents keys must equal exact node id set")
    if any(value not in {"auto", "beads", "github", "none"} for value in intents.values()):
        raise ContractError("invalid binding intent")
    phase_number = {node_ids[i]: i + 1 for i in range(13)}
    source_digest = registration["source_digest"].removeprefix("sha256:")
    for index, node in enumerate(nodes):
        if not isinstance(node, dict): raise ContractError(f"nodes[{index}] must be an object")
        _validate_schema(node, node_schema, node_schema, f"nodes[{index}]")
        if node.get("artifact_kind") != "task" or node.get("artifact_subtypes") != []:
            raise ContractError(f"nodes[{index}] must be a canonical task")
        if node.get("parent_feature") != package["parent_feature"] or node.get("feature_package_id") != package["feature_package_id"]:
            raise ContractError(f"nodes[{index}] has mixed parent/package")
        if node.get("tracker_binding") != "repo-config-default":
            raise ContractError(f"nodes[{index}] must carry unresolved repo-config-default binding")
        if node.get("status") != "active" or node.get("confirmation_status") != "confirmed" or node.get("evaluation_status") != "pass":
            raise ContractError(f"nodes[{index}] is not confirmed active/pass")
        if (node.get("implementation_readiness") or {}).get("status") != "complete":
            raise ContractError(f"nodes[{index}] implementation readiness is incomplete")
        lineage = node.get("source_lineage") or {}
        if lineage.get("origin_kind") != "system-dev-planner" or lineage.get("source_plugin") != "system-dev-planner":
            raise ContractError(f"nodes[{index}] has invalid system-dev-planner lineage")
        if lineage.get("source_digest") != source_digest:
            raise ContractError(f"nodes[{index}] source lineage digest mismatch")
        if not str(node.get("file_path", "")).startswith("tasks/"):
            raise ContractError(f"nodes[{index}] file_path is not under tasks/")
        parent_feature = node.get("parent_feature")
        if isinstance(parent_feature, str) and parent_feature:
            # feature 単位 namespace: 並列 package 登録・worktree 並列実行時の
            # tasks/ 直下衝突を防ぐ (parent_feature 無しの fast-path task は対象外)
            if not str(node.get("file_path", "")).startswith(f"tasks/{parent_feature}/"):
                raise ContractError(
                    f"nodes[{index}] file_path must be under tasks/{parent_feature}/ (per-feature namespace)"
                )
        for dependency in node.get("depends_on", []):
            if dependency not in phase_number: raise ContractError(f"cross-package dependency rejected: {dependency}")
            if phase_number[dependency] >= index + 1: raise ContractError(f"non-forward phase dependency rejected: {dependency}")
    return copy.deepcopy(nodes)


def _resolve_binding(intent: str, mode: str) -> str:
    if intent == "auto":
        if mode == "both": raise ContractError("tracker mode both requires an explicit binding intent for every node")
        return mode
    if intent == "none": return "none"
    if mode not in {intent, "both"}: raise ContractError(f"binding intent {intent} is not allowed by tracker mode {mode}")
    return intent


def _resolved_nodes(nodes: list[dict[str, Any]], intents: dict[str, str], mode: str,
                    node_schema: dict[str, Any]) -> list[dict[str, Any]]:
    result = copy.deepcopy(nodes)
    for index, node in enumerate(result):
        node_id = node["graph_node_id"]
        binding = _resolve_binding(intents[node_id], mode)
        node["tracker_binding"] = binding
        publication = node["github_publication"]
        if binding == "github":
            if publication.get("mode") not in {"issue", "issue_and_projects"}: publication["mode"] = "issue"
        else:
            publication["mode"] = "local_only"
            publication["project_aliases"] = []
        if binding in {"github", "none"}: node["beads_linkage"] = None
        _validate_schema(node, node_schema, node_schema, f"resolved_nodes[{index}]")
        if node["tracker_binding"] == "repo-config-default": raise ContractError("unresolved binding sentinel")
    return result


def _promotion_matches(root: Path, registration_path: Path, registration: dict[str, Any]) -> None:
    raw = registration.get("promotion_receipt")
    if not isinstance(raw, str): raise ContractError("promotion_receipt path missing")
    receipt_path = _path(root, raw, must_exist=True)
    receipt = _json_object(receipt_path)
    if receipt.get("status") != "promoted": raise ContractError("promotion receipt status is not promoted")
    if receipt.get("published_digest") != registration["source_digest"]:
        raise ContractError("promotion/registration digest mismatch")
    manifest = receipt.get("registration_manifest")
    if isinstance(manifest, str):
        manifest_path = _path(root, manifest, must_exist=True)
        if manifest_path != registration_path: raise ContractError("promotion receipt points to a different registration manifest")


def _find_node(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    return next((node for node in nodes if (node.get("graph_node_id") or node.get("id")) == node_id), None)


def _stable_receipt(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value.get(key) for key in RECEIPT_STABLE_KEYS}


def _atomic_create_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        try: os.link(temp, path)
        except FileExistsError as exc: raise ContractError(f"immutable receipt already exists: {path}") from exc
    finally:
        try: os.unlink(temp)
        except FileNotFoundError: pass


def _macro_request(raw: str) -> dict[str, Any]:
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError("macro request is invalid JSON") from exc
    if not isinstance(request, dict):
        raise ContractError("macro request must be an object")
    schema = _json_object(MACRO_INTENT_SCHEMA)
    _validate_schema(request, schema, schema, "macro-intent")
    observed_at = request.get("observed_at")
    if not isinstance(observed_at, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", observed_at
    ) is None:
        raise ContractError("macro request observed_at must be an RFC3339 date-time")
    architecture = request["architecture"]
    features = request["features"]
    all_rows = [architecture, *features]
    ids = [row["graph_node_id"] for row in all_rows]
    if len(set(ids)) != len(ids):
        raise ContractError("macro graph_node_id values must be unique")
    feature_ids = {feature["graph_node_id"] for feature in features}
    for index, feature in enumerate(features):
        unknown = set(feature["depends_on"]) - feature_ids
        if unknown:
            raise ContractError(f"macro features[{index}].depends_on must reference macro features: {sorted(unknown)}")
    return request


def _macro_node_base(request: dict[str, Any], row: dict[str, Any], kind: str) -> dict[str, Any]:
    node_id = row["graph_node_id"]
    observed_at = request["observed_at"]
    is_feature = kind == "feature"
    return {
        "graph_node_id": node_id,
        "artifact_kind": kind,
        "artifact_subtypes": [] if is_feature else list(row["artifact_subtypes"]),
        "title": row["title"],
        "project_id": request["project_id"],
        "domain": row["domain"],
        "status": "draft",
        "owners": [],
        "tags": [],
        "priority": None,
        "start_date": None,
        "target_date": None,
        "iteration": None,
        "created_at": observed_at,
        "updated_at": observed_at,
        "depends_on": list(row.get("depends_on", [])),
        "related_nodes": [],
        "resource_scope": list(row["resource_scope"]),
        "purpose": row["purpose"] if is_feature else None,
        "goal": row["goal"] if is_feature else None,
        "scope_in": list(row["scope_in"]) if is_feature else [],
        "scope_out": list(row["scope_out"]) if is_feature else [],
        "acceptance": list(row["acceptance"]) if is_feature else [],
        "architecture_refs": [request["architecture"]["graph_node_id"]] if is_feature else [],
        "parent_feature": None,
        "feature_package_id": None,
        "phase_ref": None,
        "file_path": f"{'features' if is_feature else 'architecture'}/{node_id}.md",
        "template_id": kind,
        "template_version": "1.0.0",
        "confirmation_status": "draft",
        "evaluation_status": "pending",
        "confirmation_evidence": {"evaluator": None, "evidence_ref": None, "evaluated_digest": None},
        "source_lineage": {
            "origin_kind": "generated",
            "source_plugin": "dev-graph",
            "source_path": None,
            "source_version": None,
            "source_digest": request["source_digest"],
            "imported_at": observed_at,
        },
        "classification_confidence": 1.0,
        "classification_reason": "C14 macro intent normalized by C02 macro contract",
        "classification_candidates": [],
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "issue_linkage": None,
        "tracker_binding": "none",
        "beads_linkage": None,
        "github_project_linkages": [],
        "pull_request_linkages": [],
        "execution_contexts": [],
        "completion_evidence": {
            "policy": "linked_pr_merged_all", "status": "in_progress", "source": None,
            "completed_at": None, "reconciled_at": None, "evidence_refs": [],
        },
        "implementation_readiness": {
            "status": "incomplete", "missing_sections": ["independent_evaluation"], "checked_at": observed_at,
        },
    }


def _validate_macro_graph(nodes: list[dict[str, Any]], candidate_ids: set[str], node_schema: dict[str, Any]) -> None:
    by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        _validate_schema(node, node_schema, node_schema, f"candidate.nodes[{index}]")
        node_id = node.get("graph_node_id")
        if not isinstance(node_id, str) or node_id in by_id:
            raise ContractError(f"candidate graph contains duplicate or invalid node id: {node_id!r}")
        by_id[node_id] = node
    for node_id in candidate_ids:
        node = by_id[node_id]
        for field in ("depends_on", "architecture_refs"):
            for dependency in node.get(field, []):
                if dependency not in by_id:
                    raise ContractError(f"candidate graph has dangling {field}: {node_id}->{dependency}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ContractError(f"candidate graph contains a dependency cycle at {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in by_id[node_id].get("depends_on", []):
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in by_id:
        visit(node_id)
    candidates = [by_id[node_id] for node_id in candidate_ids]
    if any(node["artifact_kind"] not in {"architecture", "feature"} for node in candidates):
        raise ContractError("macro preview may contain only architecture and feature nodes")
    if any(node["status"] != "draft" or node["confirmation_status"] != "draft" or node["evaluation_status"] != "pending" for node in candidates):
        raise ContractError("macro preview candidates must remain draft/unconfirmed/unevaluated")


def _macro_document(node: dict[str, Any]) -> str:
    if node["artifact_kind"] == "feature":
        bullets = lambda values: "\n".join(f"- {value}" for value in values)
        body = "\n\n".join([
            f"# {node['title']}",
            f"## 目的\n\n{node['purpose']}",
            f"## 到達状態\n\n{node['goal']}",
            f"## スコープ\n\n### 対象\n\n{bullets(node['scope_in'])}\n\n### 対象外\n\n{bullets(node['scope_out'])}",
            f"## 受入\n\n{bullets(node['acceptance'])}",
            f"## アーキテクチャ参照\n\n{bullets(node['architecture_refs'])}",
            f"## 機能間依存\n\n{bullets(node['depends_on']) if node['depends_on'] else '依存なし。'}",
            "## Handoff\n\nsystem-dev-plannerへこのfeature文脈を渡す。",
        ])
    else:
        body = "\n\n".join([
            f"# {node['title']}",
            "## Architecture overview\n\nMacro featuresが共有するarchitecture context。",
            "## Context and drivers\n\nMacro intentの共有制約を一箇所に保持する。",
            "## Goals and non-goals\n\nFeature間で共有する設計境界を定義し、phase taskは扱わない。",
            "## System context and boundaries\n\n対象project内のfeature群を境界とする。",
            "## Container and component view\n\n詳細化は後続設計へ委譲する。",
            "## Cross-cutting contracts\n\nFeatureはこのarchitecture nodeをgraph_node_idで参照する。",
            f"## Subtype architecture\n\n対象subtype: {', '.join(node['artifact_subtypes'])}。",
            "## Architecture decisions\n\nMacro分解時点の共有architectureとして登録する。",
            "## Delivery, migration and rollback\n\nDraft登録後、独立評価を経て昇格する。",
            "## Risks and verification\n\nC11 schema/DAG/artifact検証を必須とする。",
        ])
    return _artifact_document(node, body)


def _normalized_c11(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority": "C11/validate-graph-schema.py",
        "valid": report.get("valid") is True,
        "implementation_readiness": report.get("implementation_readiness"),
        "missing_sections": report.get("missing_sections", []),
        "violations": report.get("violations", []),
    }


def _prepare_macro(root: Path, graph_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    current = _json_object(graph_path)
    existing = current.get("nodes")
    if not isinstance(existing, list) or not all(isinstance(node, dict) for node in existing):
        raise ContractError("output graph must contain nodes[] objects")
    architecture = _macro_node_base(request, request["architecture"], "architecture")
    features = [_macro_node_base(request, row, "feature") for row in request["features"]]
    candidate_nodes = [architecture, *features]
    candidate_node_ids = [node["graph_node_id"] for node in candidate_nodes]
    candidate_ids = set(candidate_node_ids)
    present = {node_id for node_id in candidate_node_ids if _find_node(existing, node_id) is not None}
    if present and present != candidate_ids:
        raise ContractError(f"partial macro registration detected: {len(present)}/{len(candidate_ids)} nodes")
    proposed = copy.deepcopy(current)
    revision = current.get("graph_revision", 0)
    if not isinstance(revision, int) or revision < 0:
        raise ContractError("invalid graph_revision")
    idempotent = bool(present)
    if idempotent:
        durable = [_find_node(existing, node_id) for node_id in candidate_node_ids]
        if durable != candidate_nodes:
            raise ContractError("macro node ids exist with different content")
        for node in candidate_nodes:
            _artifact_target(root, node["file_path"], durable=True)
    else:
        proposed["nodes"] = [*existing, *candidate_nodes]
        proposed["graph_revision"] = revision + 1
    node_schema = _json_object(PLUGIN_ROOT / "schemas" / "graph-node.schema.json")
    _validate_macro_graph(proposed["nodes"], candidate_ids, node_schema)
    if not idempotent:
        for node in candidate_nodes:
            _artifact_target(root, node["file_path"], durable=False)
    documents = {} if idempotent else {node["file_path"]: _macro_document(node) for node in candidate_nodes}
    c11 = _normalized_c11(_stage_and_validate(root, graph_path, proposed, documents))
    if c11["valid"] is not True or c11["violations"] or c11["missing_sections"]:
        raise ContractError(f"C11 macro validation failed: {c11}")
    return {
        "request": request,
        "current": current,
        "proposed": proposed,
        "documents": documents,
        "candidate_nodes": candidate_nodes,
        "candidate_node_ids": candidate_node_ids,
        "candidate_graph_digest": _canonical_digest(proposed),
        "candidate_nodes_digest": _canonical_digest(candidate_nodes),
        "intent_digest": _canonical_digest(request),
        "graph_revision_before": revision,
        "graph_revision_after": proposed.get("graph_revision", revision),
        "idempotent": idempotent,
        "validation": c11,
    }


def _preview_macro(args: argparse.Namespace) -> dict[str, Any]:
    if not args.dry_run:
        raise ContractError("preview-macro is dry-run only; --dry-run is required")
    root = Path(args.repo_root or os.getcwd()).resolve(strict=True)
    graph_path = _path(root, args.graph, must_exist=True)
    prepared = _prepare_macro(root, graph_path, _macro_request(args.request_json))
    graph_before_sha = hashlib.sha256(graph_path.read_bytes()).hexdigest()
    return {
        "schema_version": "1.0.0",
        "owner": "C02/run-dev-graph-node",
        "operation": "preview_macro_decomposition",
        "status": "preview",
        "dry_run": True,
        "write_count": 0,
        "source_digest": prepared["request"]["source_digest"],
        "intent_digest": prepared["intent_digest"],
        "graph_path": graph_path.relative_to(root).as_posix(),
        "graph_sha256_before": graph_before_sha,
        "graph_sha256_after": graph_before_sha,
        "graph_revision_before": prepared["graph_revision_before"],
        "graph_revision_after_preview": prepared["graph_revision_after"],
        "candidate_graph_digest": prepared["candidate_graph_digest"],
        "candidate_nodes_digest": prepared["candidate_nodes_digest"],
        "candidate_node_ids": prepared["candidate_node_ids"],
        "candidate_nodes": prepared["candidate_nodes"],
        "idempotent": prepared["idempotent"],
        "validation": prepared["validation"],
    }


def _apply_macro(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root or os.getcwd()).resolve(strict=True)
    graph_path = _path(root, args.graph, must_exist=True)
    receipt_path = _path(root, args.receipt, must_exist=False)
    request = _macro_request(args.request_json)
    receipt_schema = _json_object(MACRO_RECEIPT_SCHEMA)

    def perform() -> dict[str, Any]:
        prepared = _prepare_macro(root, graph_path, request)
        if prepared["candidate_graph_digest"] != args.expected_candidate_digest:
            raise ContractError("macro preview/apply candidate digest mismatch")
        if prepared["idempotent"]:
            if not receipt_path.is_file():
                raise ContractError("registered macro nodes exist without immutable receipt")
            receipt = _json_object(receipt_path)
            _validate_schema(receipt, receipt_schema, receipt_schema, "macro-registration-receipt")
            identity = {
                "source_digest": request["source_digest"],
                "intent_digest": prepared["intent_digest"],
                "candidate_nodes_digest": prepared["candidate_nodes_digest"],
                "candidate_node_ids": prepared["candidate_node_ids"],
                "graph_path": graph_path.relative_to(root).as_posix(),
            }
            if any(receipt.get(key) != value for key, value in identity.items()):
                raise ContractError("immutable macro receipt conflicts with durable graph")
            receipt_revision = receipt.get("graph_revision_after")
            if not isinstance(receipt_revision, int) or receipt_revision > prepared["graph_revision_after"]:
                raise ContractError("immutable macro receipt revision is ahead of the durable graph")
            # The immutable file records the first apply.  The stdout receipt is the
            # current idempotent apply projection, so bind it to the immediately
            # preceding preview even when unrelated nodes grew the graph later.
            projected = {
                **receipt,
                "candidate_graph_digest": prepared["candidate_graph_digest"],
                "graph_revision_before": prepared["graph_revision_before"],
                "graph_revision_after": prepared["graph_revision_after"],
                "graph_sha256_after": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
                "idempotent": True,
                "write_count": 0,
            }
            _validate_schema(projected, receipt_schema, receipt_schema, "macro-registration-receipt")
            return projected
        if receipt_path.exists():
            raise ContractError("immutable macro receipt exists before graph registration")
        receipt = {
            "schema_version": "1.0.0",
            "owner": "C02/run-dev-graph-node",
            "operation": "apply_macro_decomposition",
            "status": "applied",
            "applied_at": utc_now(),
            "dry_run": False,
            "idempotent": False,
            "source_digest": request["source_digest"],
            "intent_digest": prepared["intent_digest"],
            "candidate_graph_digest": prepared["candidate_graph_digest"],
            "candidate_nodes_digest": prepared["candidate_nodes_digest"],
            "candidate_node_ids": prepared["candidate_node_ids"],
            "graph_path": graph_path.relative_to(root).as_posix(),
            "graph_revision_before": prepared["graph_revision_before"],
            "graph_revision_after": prepared["graph_revision_after"],
            "graph_sha256_after": hashlib.sha256(
                (json.dumps(prepared["proposed"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
            ).hexdigest(),
            "validation": prepared["validation"],
            "write_count": len(prepared["documents"]) + 2,
        }
        _validate_schema(receipt, receipt_schema, receipt_schema, "macro-registration-receipt")
        graph_bytes = graph_path.read_bytes()
        backups: dict[Path, bytes | None] = {}
        try:
            for raw, content in prepared["documents"].items():
                target = _path(root, raw, must_exist=False)
                backups[target] = target.read_bytes() if target.exists() else None
                _atomic_text(target, content)
            atomic_json(graph_path, prepared["proposed"])
            receipt["graph_sha256_after"] = hashlib.sha256(graph_path.read_bytes()).hexdigest()
            _atomic_create_json(receipt_path, receipt)
        except Exception:
            for target, original in backups.items():
                if original is None:
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    _atomic_text(target, original.decode("utf-8"))
            _atomic_text(graph_path, graph_bytes.decode("utf-8"))
            raise
        return receipt

    with _single_writer(graph_path):
        return perform()


def _artifact_payload(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _json_object(path)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ContractError("artifact input must contain a non-empty artifacts[]")
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ContractError(f"artifacts[{index}] must be an object")
        for key in ("title", "body"):
            if not isinstance(artifact.get(key), str) or not artifact[key].strip():
                raise ContractError(f"artifacts[{index}].{key} must be a non-empty string")
    return payload, artifacts


def _artifact_plan(path: Path, artifact_count: int) -> dict[str, Any]:
    plan = _json_object(path)
    if set(plan) != ARTIFACT_PLAN_KEYS:
        raise ContractError(f"artifact plan keys mismatch: {sorted(set(plan) ^ ARTIFACT_PLAN_KEYS)}")
    if plan.get("schema_version") != "1.0.0":
        raise ContractError("artifact plan schema_version must be 1.0.0")
    observed_at = plan.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ContractError("artifact plan observed_at must be a non-empty date-time string")
    decisions = plan.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != artifact_count:
        raise ContractError("artifact plan must contain exactly one decision per input artifact")
    indices: list[int] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict) or set(decision) != ARTIFACT_DECISION_KEYS:
            actual = set(decision) if isinstance(decision, dict) else set()
            raise ContractError(f"decisions[{index}] keys mismatch: {sorted(actual ^ ARTIFACT_DECISION_KEYS)}")
        input_index = decision.get("input_index")
        if not isinstance(input_index, int) or isinstance(input_index, bool) or not 0 <= input_index < artifact_count:
            raise ContractError(f"decisions[{index}].input_index is invalid")
        indices.append(input_index)
        kind = decision.get("artifact_kind")
        if kind not in ARTIFACT_KINDS:
            raise ContractError(f"decisions[{index}].artifact_kind is invalid")
        subtypes = decision.get("artifact_subtypes")
        if not isinstance(subtypes, list) or any(not isinstance(value, str) for value in subtypes):
            raise ContractError(f"decisions[{index}].artifact_subtypes must be string[]")
        if len(set(subtypes)) != len(subtypes):
            raise ContractError(f"decisions[{index}].artifact_subtypes contains duplicates")
        if kind == "architecture" and (not subtypes or not set(subtypes) <= {"frontend", "backend", "infrastructure", "data", "security"}):
            raise ContractError(f"decisions[{index}] architecture requires valid subtype(s)")
        if kind == "specification" and not set(subtypes) <= {"api"}:
            raise ContractError(f"decisions[{index}] specification supports only the api subtype here")
        if kind in {"issue", "task", "document", "feature"} and subtypes:
            raise ContractError(f"decisions[{index}] {kind} cannot carry artifact_subtypes")
        for key in ("project_id", "domain", "classification_reason"):
            if not isinstance(decision.get(key), str) or not decision[key].strip():
                raise ContractError(f"decisions[{index}].{key} must be a non-empty string")
        for key in ("owners", "tags", "resource_scope", "depends_on_titles", "related_node_titles", "architecture_ref_titles"):
            values = decision.get(key)
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                raise ContractError(f"decisions[{index}].{key} must be non-empty string[]")
            if len(set(values)) != len(values):
                raise ContractError(f"decisions[{index}].{key} contains duplicates")
        confidence = decision.get("classification_confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise ContractError(f"decisions[{index}].classification_confidence is invalid")
        candidates = decision.get("classification_candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ContractError(f"decisions[{index}].classification_candidates must include the second candidate")
        for cindex, candidate in enumerate(candidates):
            if not isinstance(candidate, dict) or set(candidate) != ARTIFACT_CANDIDATE_KEYS:
                raise ContractError(f"decisions[{index}].classification_candidates[{cindex}] keys mismatch")
            if candidate.get("artifact_kind") not in ARTIFACT_KINDS:
                raise ContractError(f"decisions[{index}].classification_candidates[{cindex}].artifact_kind is invalid")
            score = candidate.get("confidence")
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
                raise ContractError(f"decisions[{index}].classification_candidates[{cindex}].confidence is invalid")
        source = decision.get("decision_source")
        if source not in {"automatic", "user_confirmed"}:
            raise ContractError(f"decisions[{index}].decision_source is invalid")
        runner_up = max(float(candidate["confidence"]) for candidate in candidates)
        if source == "automatic" and (confidence < 0.80 or float(confidence) - runner_up < 0.15):
            raise ContractError(f"decisions[{index}] automatic classification is below confidence/margin threshold")
        if decision.get("tracker_binding") not in {"auto", "beads", "github", "none"}:
            raise ContractError(f"decisions[{index}].tracker_binding is invalid")
        if decision.get("priority") is not None and not isinstance(decision.get("priority"), str):
            raise ContractError(f"decisions[{index}].priority must be a string or null")
        body = decision.get("rendered_body")
        if not isinstance(body, str):
            raise ContractError(f"decisions[{index}].rendered_body must be a string")
        if kind != "feature" and not body.strip():
            raise ContractError(f"decisions[{index}].rendered_body is required for normal artifacts")
    if sorted(indices) != list(range(artifact_count)):
        raise ContractError("artifact plan decision indices must be an exact input-index set")
    return plan


def _patch_plan(path: Path | None, artifact_count: int) -> dict[int, list[dict[str, str]]]:
    if path is None:
        return {}
    plan = _json_object(path)
    if set(plan) != PATCH_PLAN_KEYS or not isinstance(plan.get("patches"), list):
        raise ContractError("patch plan must contain only patches[]")
    result: dict[int, list[dict[str, str]]] = {}
    for index, patch in enumerate(plan["patches"]):
        if not isinstance(patch, dict) or set(patch) != PATCH_KEYS:
            raise ContractError(f"patches[{index}] keys mismatch")
        input_index = patch.get("input_index")
        if not isinstance(input_index, int) or isinstance(input_index, bool) or not 0 <= input_index < artifact_count:
            raise ContractError(f"patches[{index}].input_index is invalid")
        if input_index in result:
            raise ContractError(f"duplicate patch input_index: {input_index}")
        sections = patch.get("append_sections")
        if not isinstance(sections, list) or not sections:
            raise ContractError(f"patches[{index}].append_sections must be non-empty")
        normalized: list[dict[str, str]] = []
        for sindex, section in enumerate(sections):
            if not isinstance(section, dict) or set(section) != PATCH_SECTION_KEYS:
                raise ContractError(f"patches[{index}].append_sections[{sindex}] keys mismatch")
            heading, body = section.get("heading"), section.get("body")
            if not isinstance(heading, str) or re.fullmatch(r"#{1,4} [^\n]+", heading) is None:
                raise ContractError(f"patches[{index}].append_sections[{sindex}].heading is invalid")
            if not isinstance(body, str) or not body.strip():
                raise ContractError(f"patches[{index}].append_sections[{sindex}].body is empty")
            normalized.append({"heading": heading, "body": body})
        result[input_index] = normalized
    return result


def _initial_state_plan(path: Path | None, artifact_count: int) -> dict[int, dict[str, str]]:
    """Validate explicit historical close-state imports for newly created local artifacts."""
    if path is None:
        return {}
    plan = _json_object(path)
    if set(plan) != INITIAL_STATE_KEYS or plan.get("schema_version") != "1.0.0":
        raise ContractError("initial-state plan must contain schema_version=1.0.0 and states[] only")
    states = plan.get("states")
    if not isinstance(states, list) or not states:
        raise ContractError("initial-state plan states[] must be non-empty")
    result: dict[int, dict[str, str]] = {}
    for index, state in enumerate(states):
        if not isinstance(state, dict) or set(state) != INITIAL_STATE_ROW_KEYS:
            raise ContractError(f"states[{index}] keys mismatch")
        input_index = state.get("input_index")
        if not isinstance(input_index, int) or isinstance(input_index, bool) or not 0 <= input_index < artifact_count:
            raise ContractError(f"states[{index}].input_index is invalid")
        if input_index in result:
            raise ContractError(f"duplicate initial-state input_index: {input_index}")
        if state.get("status") != "closed":
            raise ContractError(f"states[{index}].status must be closed")
        closed_at = state.get("closed_at")
        if not isinstance(closed_at, str) or RFC3339.fullmatch(closed_at) is None:
            raise ContractError(f"states[{index}].closed_at must be an RFC3339 date-time")
        try:
            datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError(f"states[{index}].closed_at must be a real RFC3339 date-time") from exc
        result[input_index] = {"status": "closed", "closed_at": closed_at}
    return result


def _sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attestation_ref(root: Path, raw: object, *, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip() or Path(raw).is_absolute():
        raise ContractError(f"{field} must be a non-empty repo-relative path")
    return _path(root, raw, must_exist=True)


def _system_spec_attestation(
    root: Path,
    path: Path | None,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Validate the C19 proof bundle before C02 can promote imported artifacts."""

    if path is None:
        return None
    value = _json_object(path)
    if set(value) != SYSTEM_SPEC_ATTESTATION_KEYS or value.get("schema_version") != "1.0.0":
        raise ContractError(
            "system-spec attestation must contain only the canonical 1.0.0 fields"
        )
    if value.get("source_plugin") != "system-spec-harness":
        raise ContractError("system-spec attestation source_plugin mismatch")
    version = value.get("source_version")
    match = SEMVER.fullmatch(version) if isinstance(version, str) else None
    if match is None or not ((0, 1, 0) <= tuple(map(int, match.groups())) < (1, 0, 0)):
        raise ContractError("system-spec attestation source_version must be >=0.1.0 <1.0.0")

    receipt_path = _attestation_ref(
        root, value.get("delegation_receipt_ref"), field="delegation_receipt_ref"
    )
    progress_path = _attestation_ref(
        root, value.get("delegation_progress_ref"), field="delegation_progress_ref"
    )
    for field, file_path in (
        ("delegation_receipt_sha256", receipt_path),
        ("delegation_progress_sha256", progress_path),
    ):
        expected = value.get(field)
        if not isinstance(expected, str) or HEX_SHA256.fullmatch(expected) is None:
            raise ContractError(f"{field} must be lowercase sha256 hex")
        if _sha256_hex(file_path) != expected:
            raise ContractError(f"{field} mismatch")

    validator = PLUGIN_ROOT / "scripts" / "validate-system-spec-delegation.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--repo-root",
            str(root),
            "--receipt",
            str(receipt_path),
            "--progress",
            str(progress_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContractError(
            f"system-spec delegation is not importable: {(completed.stderr or completed.stdout).strip()}"
        )

    receipt = _json_object(receipt_path)
    evaluator_row = receipt["invocations"][3]
    evaluator_path = _attestation_ref(
        root, evaluator_row.get("evidence_ref"), field="evaluator evidence_ref"
    )
    evaluator = _json_object(evaluator_path)
    identity = evaluator.get("evaluator") if isinstance(evaluator, dict) else None
    if (
        evaluator.get("verdict") != "PASS"
        or not isinstance(identity, dict)
        or identity.get("name") != "assign-system-spec-completeness-evaluator"
        or identity.get("context") != "fork"
    ):
        raise ContractError("qualified completeness evaluator report is not a fork-context PASS")

    rows = value.get("artifacts")
    if not isinstance(rows, list) or len(rows) != len(artifacts):
        raise ContractError("system-spec attestation must map every input artifact exactly once")
    mapped: dict[int, dict[str, str]] = {}
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != SYSTEM_SPEC_ATTESTATION_ROW_KEYS:
            raise ContractError(f"system-spec attestation artifacts[{row_index}] keys mismatch")
        input_index = row.get("input_index")
        if (
            not isinstance(input_index, int)
            or isinstance(input_index, bool)
            or not 0 <= input_index < len(artifacts)
            or input_index in mapped
        ):
            raise ContractError(f"system-spec attestation artifacts[{row_index}].input_index is invalid")
        source_path = _attestation_ref(
            root, row.get("source_ref"), field=f"artifacts[{row_index}].source_ref"
        )
        expected = row.get("source_sha256")
        if not isinstance(expected, str) or HEX_SHA256.fullmatch(expected) is None:
            raise ContractError(f"artifacts[{row_index}].source_sha256 must be lowercase sha256 hex")
        if _sha256_hex(source_path) != expected:
            raise ContractError(f"artifacts[{row_index}] source digest mismatch")
        if source_path.read_text(encoding="utf-8") != artifacts[input_index]["body"]:
            raise ContractError(f"artifacts[{row_index}] source bytes do not match input artifact body")
        mapped[input_index] = {
            "source_ref": source_path.relative_to(root).as_posix(),
            "source_sha256": expected,
        }
    if set(mapped) != set(range(len(artifacts))):
        raise ContractError("system-spec attestation input_index set is incomplete")
    return {
        "path": path.relative_to(root).as_posix(),
        "source_version": version,
        "sources": mapped,
        "evaluator": "assign-system-spec-completeness-evaluator",
        "evidence_ref": evaluator_path.relative_to(root).as_posix(),
    }


def _headings(body: str) -> list[str]:
    result: list[str] = []
    fenced = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            match = re.match(r"^#{1,4}\s+(.+?)(?:\s+#+)?\s*$", line)
            if match:
                result.append(match.group(1))
    return result


def _validate_rendered_body(body: str, kind: str, subtypes: list[str], contract: dict[str, Any], templates: Path) -> None:
    if not body.endswith("\n"):
        raise ContractError(f"rendered_body for {kind} must end with a newline")
    if "<" in body or any(token in body for token in ("TBD", "TODO", "未定")):
        raise ContractError(f"rendered_body for {kind} contains a template placeholder token")
    headings = _headings(body)
    required = ((contract.get("artifacts") or {}).get(kind) or {}).get("required_sections")
    if not isinstance(required, list):
        raise ContractError(f"template contract omits required_sections for {kind}")
    missing = [heading for heading in required if heading not in headings]
    if missing:
        raise ContractError(f"rendered_body for {kind} misses required sections: {missing}")
    if kind == "specification" and "api" in subtypes:
        api_template = templates / "api-contract.md"
        overlay = _headings(api_template.read_text(encoding="utf-8"))
        required_api = [heading for heading in overlay if not heading.startswith("API:")]
        if not any(heading.startswith("API:") for heading in headings):
            missing.append("API: <operation-name>")
        missing.extend(heading for heading in required_api if heading not in headings)
    if kind == "architecture":
        subtype_templates = ((contract.get("artifacts") or {}).get("architecture") or {}).get("subtype_templates")
        if not isinstance(subtype_templates, dict):
            raise ContractError("template contract omits architecture subtype_templates")
        for subtype in subtypes:
            filename = subtype_templates.get(subtype)
            if not isinstance(filename, str):
                raise ContractError(f"template contract omits architecture subtype: {subtype}")
            missing.extend(
                heading for heading in _headings((templates / filename).read_text(encoding="utf-8"))
                if heading not in headings
            )
    if missing:
        raise ContractError(f"rendered_body for {kind} misses conditional sections: {sorted(set(missing))}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "artifact"


def _artifact_digest(artifact: dict[str, Any]) -> str:
    raw = json.dumps(artifact, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _graph_path_from_config(root: Path) -> tuple[Path, dict[str, Any]]:
    config = _json_object(_path(root, ".dev-graph/config.json", must_exist=True))
    local_state = config.get("local_state")
    raw = local_state.get("graph") if isinstance(local_state, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("repo config local_state.graph is required")
    return _path(root, raw, must_exist=True), config


def _tracker_mode(config: dict[str, Any]) -> str:
    tracker = config.get("execution_tracker")
    mode = tracker.get("mode") if isinstance(tracker, dict) else None
    if mode not in {"beads", "github", "both", "none"}:
        raise ContractError("repo config execution_tracker.mode is invalid")
    return mode


def _normal_binding(intent: str, mode: str) -> str:
    if intent == "none":
        return "none"
    if intent == "auto":
        # A draft cannot satisfy the schema's confirmed/pass requirement for
        # GitHub publication.  Preserve local draft semantics until C14/C03.
        return mode if mode in {"beads", "none"} else "none"
    if intent == "github":
        raise ContractError("normal draft artifacts cannot bind to github before C14 confirmation")
    if mode not in {"beads", "both"}:
        raise ContractError("beads binding is not enabled by repo config")
    return "beads"


def _resolve_title_refs(titles: list[str], title_to_id: dict[str, str], field: str) -> list[str]:
    missing = [title for title in titles if title not in title_to_id]
    if missing:
        raise ContractError(f"unresolved {field} title(s): {missing}")
    return [title_to_id[title] for title in titles]


def _new_artifact_node(
    artifact: dict[str, Any], decision: dict[str, Any], *, node_id: str, file_path: str,
    source_path: str, source_version: str | None, source_digest: str, observed_at: str,
    binding: str, title_to_id: dict[str, str], template_version: str,
    system_spec_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    kind = decision["artifact_kind"]
    attested = system_spec_evidence is not None
    return {
        "graph_node_id": node_id, "artifact_kind": kind,
        "artifact_subtypes": list(decision["artifact_subtypes"]), "title": artifact["title"],
        "project_id": decision["project_id"], "domain": decision["domain"],
        "status": "active" if attested else "draft",
        "owners": list(decision["owners"]), "tags": list(decision["tags"]),
        "priority": decision["priority"], "start_date": None, "target_date": None,
        "iteration": None, "created_at": observed_at, "updated_at": observed_at,
        "depends_on": _resolve_title_refs(decision["depends_on_titles"], title_to_id, "depends_on"),
        "related_nodes": _resolve_title_refs(decision["related_node_titles"], title_to_id, "related_nodes"),
        "resource_scope": list(decision["resource_scope"]),
        "purpose": None, "goal": None, "scope_in": [], "scope_out": [], "acceptance": [],
        "architecture_refs": _resolve_title_refs(decision["architecture_ref_titles"], title_to_id, "architecture_refs"),
        "parent_feature": None, "feature_package_id": None, "phase_ref": None,
        "file_path": file_path, "template_id": kind, "template_version": template_version,
        "confirmation_status": "confirmed" if attested else "draft",
        "evaluation_status": "pass" if attested else "pending",
        "confirmation_evidence": {
            "evaluator": system_spec_evidence["evaluator"] if attested else None,
            "evidence_ref": system_spec_evidence["evidence_ref"] if attested else None,
            "evaluated_digest": source_digest if attested else None,
        },
        "source_lineage": {
            "origin_kind": "system-spec-harness" if attested else "manual",
            "source_plugin": "system-spec-harness" if attested else None,
            "source_path": source_path,
            "source_version": source_version, "source_digest": source_digest, "imported_at": observed_at,
        },
        "classification_confidence": decision["classification_confidence"],
        "classification_reason": decision["classification_reason"],
        "classification_candidates": [
            {
                "artifact_kind": candidate["artifact_kind"], "confidence": candidate["confidence"],
                "candidate_path": f"{ROOT_BY_KIND[candidate['artifact_kind']]}/",
            }
            for candidate in decision["classification_candidates"]
        ],
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "issue_linkage": None, "tracker_binding": binding, "beads_linkage": None,
        "github_project_linkages": [], "pull_request_linkages": [], "execution_contexts": [],
        "completion_evidence": {
            "policy": "manual", "status": "not_applicable", "source": None,
            "completed_at": None, "reconciled_at": None, "evidence_refs": [],
        },
        "implementation_readiness": {"status": "complete", "missing_sections": [], "checked_at": observed_at},
    }


def _artifact_document(node: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in node.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join([*lines, "---", body.rstrip("\n"), ""])


def _update_frontmatter_fields(text: str, node: dict[str, Any], fields: tuple[str, ...]) -> str:
    if not text.startswith("---\n"):
        raise ContractError("existing artifact has no YAML frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ContractError("existing artifact frontmatter is not terminated")
    lines = text[4:marker + 1].splitlines()
    for field in fields:
        starts = [index for index, line in enumerate(lines) if line.startswith(f"{field}:")]
        if len(starts) != 1:
            raise ContractError(f"existing artifact frontmatter field must occur once: {field}")
        start = starts[0]
        end = start + 1
        while end < len(lines) and (not lines[end] or lines[end][0].isspace()):
            end += 1
        rendered = json.dumps(node[field], ensure_ascii=False, separators=(",", ":"))
        lines[start:end] = [f"{field}: {rendered}"]
    return "---\n" + "\n".join(lines) + "\n---\n" + text[marker + 5:]


def _append_sections(text: str, sections: list[dict[str, str]]) -> tuple[str, list[str]]:
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ContractError("existing artifact frontmatter is not terminated")
    body = text[marker + 5:]
    names = set(_headings(body))
    appended: list[str] = []
    for section in sections:
        name = section["heading"].lstrip("#").strip()
        if name in names:
            raise ContractError(f"append-only patch would duplicate section: {name}")
        body = body.rstrip("\n") + f"\n\n{section['heading']}\n\n{section['body'].strip()}\n"
        names.add(name)
        appended.append(section["heading"])
    return text[:marker + 5] + body, appended


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _run_c11(root: Path, graph_path: Path, feature_id: str | None = None) -> dict[str, Any]:
    argv = [
        sys.executable, str(PLUGIN_ROOT / "scripts" / "validate-graph-schema.py"),
        "--graph", str(graph_path), "--repo-root", str(root),
    ]
    if feature_id is not None:
        argv.extend(["--feature-id", feature_id])
    completed = subprocess.run(
        argv,
        capture_output=True, text=True, check=False,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"C11 returned invalid JSON: {completed.stderr.strip()}") from exc
    if completed.returncode != 0 or not isinstance(report, dict) or report.get("valid") is not True:
        raise ContractError(f"C11 validation failed: {report}")
    return report


def _stage_and_validate(root: Path, graph_path: Path, graph: dict[str, Any], documents: dict[str, str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dev-graph-c02-artifacts-") as temporary:
        staged_root = Path(temporary) / "repo"
        staged_root.mkdir()
        for node in graph["nodes"]:
            raw = node.get("file_path")
            if not isinstance(raw, str):
                raise ContractError("graph node file_path is invalid")
            if raw in documents:
                continue
            source = _path(root, raw, must_exist=True)
            target = staged_root / raw
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for raw, content in documents.items():
            target = staged_root / raw
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        relative_graph = graph_path.relative_to(root)
        staged_graph = staged_root / relative_graph
        staged_graph.parent.mkdir(parents=True, exist_ok=True)
        staged_graph.write_text(json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return _run_c11(staged_root, staged_graph)


def _write_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root or os.getcwd()).resolve(strict=True)
    input_path = _path(root, args.input, must_exist=True)
    plan_path = _path(root, args.plan, must_exist=True) if not Path(args.plan).is_absolute() else contained(Path(args.plan), root, must_exist=True)
    patch_path = None
    if args.patches:
        patch_path = _path(root, args.patches, must_exist=True) if not Path(args.patches).is_absolute() else contained(Path(args.patches), root, must_exist=True)
    payload, artifacts = _artifact_payload(input_path)
    plan = _artifact_plan(plan_path, len(artifacts))
    patches = _patch_plan(patch_path, len(artifacts))
    initial_state_path = None
    if args.initial_state:
        initial_state_path = (
            _path(root, args.initial_state, must_exist=True)
            if not Path(args.initial_state).is_absolute()
            else contained(Path(args.initial_state), root, must_exist=True)
        )
    initial_states = _initial_state_plan(initial_state_path, len(artifacts))
    system_spec_attestation_path = None
    if args.system_spec_attestation:
        system_spec_attestation_path = (
            _path(root, args.system_spec_attestation, must_exist=True)
            if not Path(args.system_spec_attestation).is_absolute()
            else contained(Path(args.system_spec_attestation), root, must_exist=True)
        )
    system_spec = _system_spec_attestation(
        root, system_spec_attestation_path, artifacts
    )
    if system_spec is not None and initial_states:
        raise ContractError("system-spec attestation cannot be combined with initial-state")
    graph_path, config = _graph_path_from_config(root)
    template_root = _path(root, ((config.get("local_state") or {}).get("templates") or ".dev-graph/templates"), must_exist=True)
    contract = _json_object(template_root / "template-contract.json")
    template_version = contract.get("template_version")
    if not isinstance(template_version, str):
        raise ContractError("template contract template_version is missing")
    root_map = ((contract.get("graph_projection") or {}).get("root_map"))
    if not isinstance(root_map, dict) or any(root_map.get(kind) != f"{root}/" for kind, root in ROOT_BY_KIND.items()):
        raise ContractError("template contract root_map differs from canonical routing")
    mode = _tracker_mode(config)
    input_relative = input_path.relative_to(root).as_posix()
    source_version = (
        system_spec["source_version"]
        if system_spec is not None
        else payload.get("batch_id") if isinstance(payload.get("batch_id"), str) else None
    )
    decisions = sorted(plan["decisions"], key=lambda row: row["input_index"])
    decisions_by_index = {decision["input_index"]: decision for decision in decisions}
    if system_spec is not None:
        invalid = [
            decision["input_index"]
            for decision in decisions
            if decision["artifact_kind"] not in {"specification", "architecture"}
            or decision["tracker_binding"] != "none"
        ]
        if invalid:
            raise ContractError(
                "system-spec attestation is limited to local-only specification/architecture artifacts: "
                f"input_index={invalid}"
            )
    for index in initial_states:
        decision = decisions_by_index[index]
        if decision["artifact_kind"] == "feature":
            raise ContractError(f"initial-state cannot target a C14-owned feature: input_index={index}")
        if decision["tracker_binding"] != "none":
            raise ContractError(
                f"closed historical import must remain local-only with tracker_binding=none: input_index={index}"
            )

    def perform() -> dict[str, Any]:
        current = _json_object(graph_path)
        existing = current.get("nodes")
        if not isinstance(existing, list) or not all(isinstance(node, dict) for node in existing):
            raise ContractError("output graph must contain nodes[] objects")
        revision_before = current.get("graph_revision", 0)
        if not isinstance(revision_before, int) or revision_before < 0:
            raise ContractError("invalid graph_revision")
        proposed = copy.deepcopy(current)
        proposed_nodes = proposed["nodes"]
        digests = [
            system_spec["sources"][index]["source_sha256"]
            if system_spec is not None
            else _artifact_digest(artifact)
            for index, artifact in enumerate(artifacts)
        ]
        matches: dict[int, dict[str, Any]] = {}
        planned_ids: dict[int, str] = {}
        planned_paths: dict[int, str] = {}
        rejected: list[dict[str, Any]] = []
        for decision in decisions:
            index = decision["input_index"]
            artifact, kind = artifacts[index], decision["artifact_kind"]
            if kind == "feature":
                rejected.append({
                    "input_index": index, "title": artifact["title"], "artifact_kind": kind,
                    "code": "c14_macro_feature_only",
                    "detail": "feature registration is owned by the C14 macro contract",
                })
                continue
            source_path = (
                system_spec["sources"][index]["source_ref"]
                if system_spec is not None
                else input_relative
            )
            candidates = [
                node for node in proposed_nodes
                if node.get("artifact_kind") == kind and node.get("title") == artifact["title"]
                and (node.get("source_lineage") or {}).get("source_path")
                in {source_path, input_relative, input_path.name}
            ]
            if len(candidates) > 1:
                raise ContractError(f"multiple durable nodes match input artifact: {artifact['title']}")
            if candidates:
                node = candidates[0]
                matches[index] = node
                planned_ids[index] = node["graph_node_id"]
                planned_paths[index] = node["file_path"]
            else:
                node_id = f"{kind}-{_slug(decision['domain'])}-{digests[index][:8]}"
                if _find_node(proposed_nodes, node_id) is not None:
                    raise ContractError(f"derived graph_node_id conflicts with an unrelated node: {node_id}")
                planned_ids[index] = node_id
                planned_paths[index] = f"{ROOT_BY_KIND[kind]}/{node_id}.md"
        title_to_id: dict[str, str] = {}
        for node in proposed_nodes:
            title = node.get("title")
            node_id = node.get("graph_node_id") or node.get("id")
            if isinstance(title, str) and isinstance(node_id, str):
                if title in title_to_id and title_to_id[title] != node_id:
                    raise ContractError(f"duplicate graph title cannot resolve semantic references: {title}")
                title_to_id[title] = node_id
        for decision in decisions:
            index = decision["input_index"]
            if decision["artifact_kind"] != "feature":
                title = artifacts[index]["title"]
                if title in title_to_id and title_to_id[title] != planned_ids[index]:
                    raise ContractError(f"input title conflicts with an existing graph node: {title}")
                title_to_id[title] = planned_ids[index]

        documents: dict[str, str] = {}
        applied: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []
        for decision in decisions:
            index = decision["input_index"]
            kind = decision["artifact_kind"]
            if kind == "feature":
                continue
            artifact, source_digest = artifacts[index], digests[index]
            source_path = (
                system_spec["sources"][index]["source_ref"]
                if system_spec is not None
                else input_relative
            )
            _validate_rendered_body(decision["rendered_body"], kind, decision["artifact_subtypes"], contract, template_root)
            existing_node = matches.get(index)
            if existing_node is None:
                if index in patches:
                    raise ContractError(f"patch cannot target a new artifact: input_index={index}")
                _artifact_target(root, planned_paths[index], durable=False)
                node = _new_artifact_node(
                    artifact, decision, node_id=planned_ids[index], file_path=planned_paths[index],
                    source_path=source_path, source_version=source_version, source_digest=source_digest,
                    observed_at=plan["observed_at"], binding=_normal_binding(decision["tracker_binding"], mode),
                    title_to_id=title_to_id, template_version=template_version,
                    system_spec_evidence=system_spec,
                )
                if index in initial_states:
                    node.update(initial_states[index])
                node_schema = _json_object(PLUGIN_ROOT / "schemas" / "graph-node.schema.json")
                _validate_schema(node, node_schema, node_schema, f"artifacts[{index}]")
                proposed_nodes.append(node)
                content = _artifact_document(node, decision["rendered_body"])
                documents[node["file_path"]] = content
                applied.append({
                    "input_index": index, "operation": "add", "graph_node_id": node["graph_node_id"],
                    "file_path": node["file_path"], "appended_sections": [], "source_digest": source_digest,
                    "initial_state": initial_states.get(index),
                })
                continue
            node = existing_node
            artifact_path = _artifact_target(root, node["file_path"], durable=True)
            if index in initial_states and any(
                node.get(key) != value for key, value in initial_states[index].items()
            ):
                raise ContractError(
                    f"initial-state differs from existing lifecycle state: input_index={index}"
                )
            lineage = node.get("source_lineage")
            if not isinstance(lineage, dict):
                raise ContractError(f"existing node has invalid source_lineage: {node.get('graph_node_id')}")
            if lineage.get("source_digest") == source_digest:
                if system_spec is not None:
                    confirmation = node.get("confirmation_evidence")
                    if (
                        node.get("status") != "active"
                        or node.get("confirmation_status") != "confirmed"
                        or node.get("evaluation_status") != "pass"
                        or lineage.get("origin_kind") != "system-spec-harness"
                        or lineage.get("source_plugin") != "system-spec-harness"
                        or lineage.get("source_path") != source_path
                        or not isinstance(confirmation, dict)
                        or confirmation.get("evaluator") != system_spec["evaluator"]
                        or confirmation.get("evaluated_digest") != source_digest
                    ):
                        raise ContractError(
                            f"existing system-spec node is not an attested confirmed import: {node.get('graph_node_id')}"
                        )
                unchanged.append({"input_index": index, "graph_node_id": node["graph_node_id"], "file_path": node["file_path"]})
                continue
            if index not in patches:
                raise ContractError(f"changed input requires an append-only patch: input_index={index}")
            original_text = artifact_path.read_text(encoding="utf-8")
            patched_text, appended = _append_sections(original_text, patches[index])
            node["updated_at"] = plan["observed_at"]
            lineage["source_path"] = source_path
            lineage["source_version"] = source_version
            lineage["source_digest"] = source_digest
            lineage["imported_at"] = plan["observed_at"]
            fields = ["updated_at", "source_lineage", "implementation_readiness"]
            if system_spec is not None:
                node["status"] = "active"
                node["confirmation_status"] = "confirmed"
                node["evaluation_status"] = "pass"
                node["confirmation_evidence"] = {
                    "evaluator": system_spec["evaluator"],
                    "evidence_ref": system_spec["evidence_ref"],
                    "evaluated_digest": source_digest,
                }
                fields.extend(
                    ["status", "confirmation_status", "evaluation_status", "confirmation_evidence"]
                )
            node["implementation_readiness"] = {
                "status": "complete", "missing_sections": [], "checked_at": plan["observed_at"],
            }
            documents[node["file_path"]] = _update_frontmatter_fields(
                patched_text, node, tuple(fields),
            )
            applied.append({
                "input_index": index, "operation": "update", "graph_node_id": node["graph_node_id"],
                "file_path": node["file_path"], "appended_sections": appended, "source_digest": source_digest,
            })
        if applied:
            proposed["graph_revision"] = revision_before + 1
        c11 = _stage_and_validate(root, graph_path, proposed, documents)
        report = {
            "schema_version": "1.0.0", "owner": "C02/run-dev-graph-node",
            "operation": "write_artifacts", "status": "dry_run" if args.dry_run else "applied",
            "dry_run": bool(args.dry_run), "input": input_relative, "plan": plan_path.relative_to(root).as_posix(),
            "applied": applied, "unchanged": unchanged, "rejected": rejected,
            "features_registered": 0, "c11_staged": c11,
            "initial_state_plan": initial_state_path.relative_to(root).as_posix() if initial_state_path else None,
            "system_spec_attestation": system_spec["path"] if system_spec is not None else None,
            "graph_revision_before": revision_before,
            "graph_revision_after": proposed.get("graph_revision", revision_before),
            "graph_digest_after": _canonical_digest(proposed),
            "write_count": 0 if args.dry_run else len(documents) + (1 if applied else 0),
            "temporary_driver": False,
        }
        if not applied and rejected and not unchanged:
            report["status"] = "rejected"
            report["write_count"] = 0
            return report
        if args.dry_run or not applied:
            return report
        backups: dict[Path, bytes | None] = {}
        graph_bytes = graph_path.read_bytes()
        try:
            for raw, content in documents.items():
                target = _path(root, raw, must_exist=False)
                backups[target] = target.read_bytes() if target.exists() else None
                _atomic_text(target, content)
            atomic_json(graph_path, proposed)
        except Exception:
            for target, original in backups.items():
                if original is None:
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    _atomic_text(target, original.decode("utf-8"))
            _atomic_text(graph_path, graph_bytes.decode("utf-8"))
            raise
        report["graph_sha256_after"] = hashlib.sha256(graph_path.read_bytes()).hexdigest()
        return report

    if args.dry_run:
        return perform()
    with _single_writer(graph_path):
        return perform()


@contextmanager
def _single_writer(output: Path) -> Iterator[None]:
    lock_path = output.with_name(f".{output.name}.register.lock")
    with lock_path.open("a+", encoding="utf-8") as stream:
        try: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ContractError(f"registration writer is already active: {output}") from exc
        yield


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _current_readiness(root: Path, system_root: Path) -> dict[str, Any]:
    validator = system_root / "scripts" / "check-implementation-readiness.py"
    if not validator.is_file():
        raise ContractError(f"implementation readiness validator missing: {validator}")
    completed = subprocess.run(
        [sys.executable, str(validator), "--repo-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"implementation readiness returned invalid JSON: {completed.stderr.strip()}") from exc
    if (
        completed.returncode != 0
        or not isinstance(report, dict)
        or report.get("status") != "complete"
        or report.get("missing_sections")
    ):
        raise ContractError(f"implementation readiness revalidation failed: {report}")
    source_digest = (report.get("source_pin") or {}).get("source_digest")
    if not isinstance(source_digest, str) or SHA256.fullmatch(source_digest) is None:
        raise ContractError("implementation readiness source digest is missing or invalid")
    return report


def _legacy_registration_evidence(
    *,
    root: Path,
    system_root: Path,
    output_path: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
    graph: dict[str, Any],
    nodes: list[dict[str, Any]],
    incoming_ids: list[str],
    package: dict[str, Any],
    evidence_schema: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    feature_id = package["parent_feature"]
    c11 = _run_c11(root, output_path, feature_id)
    c11_digest = c11.get("readiness_digest")
    expected_digest = c11_readiness_digest(nodes, feature_id)
    if (
        c11.get("implementation_readiness") != "complete"
        or c11.get("violations")
        or not isinstance(c11_digest, str)
        or SHA256.fullmatch(c11_digest) is None
        or c11_digest != expected_digest
    ):
        raise ContractError("legacy registration C11 revalidation did not match current graph readiness")
    readiness = _current_readiness(root, system_root)
    readiness_source = (readiness.get("source_pin") or {}).get("source_digest")
    graph_sha = _sha256_file(output_path)
    receipt_sha = _sha256_file(receipt_path)
    binding = {
        "immutable_receipt_sha256": receipt_sha,
        "graph_sha256": graph_sha,
        "c11_readiness_digest": c11_digest,
        "implementation_readiness_source_digest": readiness_source,
        "source_digest": receipt["source_digest"],
    }
    binding_digest = _canonical_digest(binding)
    evidence_path = receipt_path.with_name(
        f"{receipt_path.stem}.evidence-v1.{binding_digest.removeprefix('sha256:')}.json"
    )
    evidence = {
        "schema_version": "1.0.0",
        "evidence_contract": "package-registration-revalidation/v1",
        "status": "revalidated",
        "issued_at": utc_now(),
        "feature_package_id": package["feature_package_id"],
        "parent_feature": feature_id,
        "source_digest": receipt["source_digest"],
        "node_ids": incoming_ids,
        "immutable_receipt_path": receipt_path.relative_to(root).as_posix(),
        "immutable_receipt_sha256": receipt_sha,
        "output_path": output_path.relative_to(root).as_posix(),
        "graph_revision": graph.get("graph_revision"),
        "graph_sha256": graph_sha,
        "c11_readiness_digest": c11_digest,
        "implementation_readiness_status": "complete",
        "implementation_readiness_source_digest": readiness_source,
        "binding_digest": binding_digest,
    }
    _validate_schema(evidence, evidence_schema, evidence_schema, "package-registration-evidence")
    return evidence_path, evidence


def _ensure_legacy_evidence(path: Path, proposed: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not path.exists():
        _atomic_create_json(path, proposed)
        return proposed, 1
    existing = _json_object(path)
    _validate_schema(existing, schema, schema, "package-registration-evidence")
    stable_keys = set(proposed) - {"issued_at"}
    if any(existing.get(key) != proposed.get(key) for key in stable_keys):
        raise ContractError("immutable legacy registration evidence conflicts with current revalidation")
    return existing, 0


def _register(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root or os.getcwd()).resolve(strict=True)
    package_path = _path(root, args.package, must_exist=True)
    registration_path = _path(root, args.graph, must_exist=True)
    output_path = _path(root, args.output, must_exist=True)
    receipt_path = _path(root, args.receipt, must_exist=False)
    system_root = Path(args.system_planner_root).resolve(strict=True)
    preflight_contract(system_root, args.required_version, args.required_schema_version)
    package_schema = _json_object(system_root / "schemas" / "feature-execution-package.schema.json")
    registration_schema = _json_object(system_root / "schemas" / "dev-graph-registration.schema.json")
    if _schema_version(registration_schema, "dev-graph-registration.schema.json") != args.required_schema_version:
        raise ContractError("registration schema version changed after preflight")
    node_schema = _json_object(PLUGIN_ROOT / "schemas" / "graph-node.schema.json")
    receipt_schema = _json_object(PLUGIN_ROOT / "schemas" / "package-registration-receipt.schema.json")
    evidence_schema = _json_object(PACKAGE_EVIDENCE_SCHEMA)
    package = _json_object(package_path); _validate_package(package, package_schema)
    registration = _json_object(registration_path)
    incoming = _validate_registration(registration, package, node_schema)
    _promotion_matches(root, registration_path, registration)
    resolved = _resolved_nodes(incoming, registration["binding_intents"], args.tracker_mode, node_schema)

    def perform() -> dict[str, Any]:
        current = _json_object(output_path)
        existing = current.get("nodes")
        if not isinstance(existing, list) or not all(isinstance(node, dict) for node in existing):
            raise ContractError("output graph must contain nodes[] objects")
        existing_ids = [node.get("graph_node_id") or node.get("id") for node in existing]
        if len(set(existing_ids)) != len(existing_ids): raise ContractError("output graph contains duplicate node ids")
        for index, node in enumerate(existing):
            _validate_schema(node, node_schema, node_schema, f"output.nodes[{index}]")
        parent = _find_node(existing, package["parent_feature"])
        if not parent or parent.get("artifact_kind", parent.get("kind")) != "feature":
            raise ContractError(f"parent feature does not exist: {package['parent_feature']}")
        incoming_ids = [node["graph_node_id"] for node in resolved]
        present = {node_id for node_id in incoming_ids if _find_node(existing, node_id)}
        package_members = [node for node in existing if node.get("feature_package_id") == package["feature_package_id"]]
        if present and len(present) != 13: raise ContractError(f"partial registration detected: {len(present)}/13 nodes")
        if package_members and {node.get("graph_node_id") for node in package_members} != set(incoming_ids):
            raise ContractError("conflicting or partial feature_package_id already exists")
        revision_before = current.get("graph_revision", 0)
        if not isinstance(revision_before, int) or revision_before < 0: raise ContractError("invalid graph_revision")
        if len(present) == 13:
            actual = [_find_node(existing, node_id) for node_id in incoming_ids]
            if actual != resolved: raise ContractError("duplicate node ids exist with different content")
            if not receipt_path.is_file(): raise ContractError("registered nodes exist without immutable receipt")
            receipt = _json_object(receipt_path)
            _validate_schema(receipt, receipt_schema, receipt_schema, "registration-receipt")
            expected_receipt_identity = {
                "schema_version": "1.0.0", "status": "registered",
                "feature_package_id": package["feature_package_id"],
                "parent_feature": package["parent_feature"],
                "source_digest": registration["source_digest"],
                "expected_count": 13, "applied_count": 13,
                "phase_refs": PHASES, "node_ids": incoming_ids,
                "output_path": output_path.relative_to(root).as_posix(),
            }
            if any(receipt.get(key) != value for key, value in expected_receipt_identity.items()):
                raise ContractError("immutable receipt conflicts with registered package")
            expected_c11_digest = c11_readiness_digest(existing, package["parent_feature"])
            stored_c11_digest = receipt.get("c11_readiness_digest")
            if stored_c11_digest is not None and stored_c11_digest != expected_c11_digest:
                raise ContractError("immutable receipt C11 readiness digest conflicts with registered package")
            before = receipt.get("graph_revision_before")
            after = receipt.get("graph_revision_after")
            if not isinstance(before, int) or not isinstance(after, int) or after != before + 1 or after > revision_before:
                raise ContractError("immutable receipt graph revision conflicts with registered package")
            if stored_c11_digest is None:
                evidence_path, proposed_evidence = _legacy_registration_evidence(
                    root=root,
                    system_root=system_root,
                    output_path=output_path,
                    receipt_path=receipt_path,
                    receipt=receipt,
                    graph=current,
                    nodes=existing,
                    incoming_ids=incoming_ids,
                    package=package,
                    evidence_schema=evidence_schema,
                )
                if args.dry_run:
                    return {
                        **receipt,
                        "idempotent": True,
                        "dry_run": True,
                        "write_count": 0,
                        "supplemental_evidence": evidence_path.relative_to(root).as_posix(),
                        "revalidation": proposed_evidence,
                    }
                evidence, write_count = _ensure_legacy_evidence(
                    evidence_path, proposed_evidence, evidence_schema,
                )
                return {
                    **receipt,
                    "idempotent": True,
                    "dry_run": False,
                    "write_count": write_count,
                    "supplemental_evidence": evidence_path.relative_to(root).as_posix(),
                    "revalidation": evidence,
                }
            return {**receipt, "idempotent": True, "dry_run": bool(args.dry_run)}
        if receipt_path.exists(): raise ContractError("immutable receipt exists before graph registration")
        proposed = copy.deepcopy(current)
        proposed["nodes"] = [*existing, *resolved]
        proposed["graph_revision"] = revision_before + 1
        graph_digest = _canonical_digest(proposed)
        readiness_digest = c11_readiness_digest(proposed["nodes"], package["parent_feature"])
        receipt = {
            "schema_version": "1.0.0", "status": "registered", "registered_at": utc_now(),
            "feature_package_id": package["feature_package_id"], "parent_feature": package["parent_feature"],
            "source_digest": registration["source_digest"], "expected_count": 13, "applied_count": 13,
            "phase_refs": PHASES, "node_ids": incoming_ids, "graph_revision_before": revision_before,
            "graph_revision_after": revision_before + 1, "graph_digest_after": graph_digest,
            "c11_readiness_digest": readiness_digest,
            "output_path": output_path.relative_to(root).as_posix(),
        }
        _validate_schema(receipt, receipt_schema, receipt_schema, "registration-receipt")
        if args.dry_run:
            return {**receipt, "dry_run": True, "idempotent": False, "write_count": 0}
        original = copy.deepcopy(current)
        atomic_json(output_path, proposed)
        try: _atomic_create_json(receipt_path, receipt)
        except Exception:
            atomic_json(output_path, original)
            raise
        return {**receipt, "dry_run": False, "idempotent": False}

    if args.dry_run: return perform()
    with _single_writer(output_path): return perform()


def _project_execution_context(args: argparse.Namespace) -> dict[str, Any]:
    """C02-owned durable projection consumed by C27 after each lease transition."""
    root = Path(args.repo_root or ".").resolve(strict=True)
    graph_path = contained(root / args.graph if not Path(args.graph).is_absolute() else Path(args.graph), root)
    try:
        context = json.loads(args.context_json)
    except json.JSONDecodeError as exc:
        raise ContractError("execution context is invalid JSON") from exc
    if not isinstance(context, dict):
        raise ContractError("execution context must be an object")
    node_schema = load_json(PLUGIN_ROOT / "schemas" / "graph-node.schema.json")
    context_schema = node_schema.get("properties", {}).get("execution_contexts", {}).get("items")
    if not isinstance(context_schema, dict):
        raise ContractError("graph-node schema omits execution_contexts item contract")
    _validate_schema(context, context_schema, node_schema, "$.execution_contexts[0]")

    def perform() -> dict[str, Any]:
        graph = load_json(graph_path)
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
            raise ContractError("execution-context graph must contain nodes array")
        matches = [node for node in graph["nodes"] if isinstance(node, dict) and (node.get("graph_node_id") or node.get("id")) == args.graph_node_id]
        if len(matches) != 1:
            raise ContractError("execution-context target must resolve exactly one graph node")
        proposed = copy.deepcopy(graph)
        node = next(node for node in proposed["nodes"] if isinstance(node, dict) and (node.get("graph_node_id") or node.get("id")) == args.graph_node_id)
        existing = node.get("execution_contexts", [])
        if not isinstance(existing, list):
            raise ContractError("node execution_contexts must be an array")
        retained = [row for row in existing if not isinstance(row, dict) or row.get("worktree_id") != context["worktree_id"]]
        node["execution_contexts"] = [*retained, context]
        node["updated_at"] = context["last_seen_at"]
        _validate_schema(node, node_schema, node_schema, "$.nodes[target]")
        idempotent = proposed == graph
        revision_before = graph.get("graph_revision")
        if isinstance(revision_before, int) and not idempotent:
            proposed["graph_revision"] = revision_before + 1
        packed = json.dumps(proposed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        receipt = {
            "owner": "C02/run-dev-graph-node",
            "operation": "project_execution_context",
            "status": "preview" if args.dry_run else "applied",
            "graph_node_id": args.graph_node_id,
            "worktree_id": context["worktree_id"],
            "state": context["state"],
            "graph_sha256_after": hashlib.sha256(packed).hexdigest(),
            "graph_revision_before": revision_before,
            "graph_revision_after": proposed.get("graph_revision"),
            "write_count": 0 if args.dry_run or idempotent else 1,
            "idempotent": idempotent,
        }
        if not args.dry_run:
            if not idempotent:
                atomic_json(graph_path, proposed)
            receipt["graph_sha256_after"] = hashlib.sha256(graph_path.read_bytes()).hexdigest()
        return receipt

    if args.dry_run:
        return perform()
    with _single_writer(graph_path):
        return perform()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C02 normal-artifact writer, macro preview/apply, exact-13 registration, or preflight")
    sub = parser.add_subparsers(dest="command", required=True)
    artifacts = sub.add_parser("artifacts")
    artifacts.add_argument("--repo-root")
    artifacts.add_argument("--input", required=True, help="contained JSON object with artifacts[]")
    artifacts.add_argument("--plan", required=True, help="contained semantic classification/rendering plan; never a graph")
    artifacts.add_argument("--patches", help="contained append-only update patch plan")
    artifacts.add_argument(
        "--initial-state",
        help="contained explicit historical close-state plan for new local-only artifacts",
    )
    artifacts.add_argument(
        "--system-spec-attestation",
        help="contained C19 proof bundle for confirmed system-spec-harness imports",
    )
    artifacts.add_argument("--dry-run", action="store_true")
    macro = sub.add_parser("preview-macro")
    macro.add_argument("--repo-root")
    macro.add_argument("--graph", default=".dev-graph/state/graph.json")
    macro.add_argument("--request-json", required=True, help="C14 macro intent JSON; never a graph or receipt path")
    macro.add_argument("--dry-run", action="store_true")
    apply_macro = sub.add_parser("apply-macro")
    apply_macro.add_argument("--repo-root")
    apply_macro.add_argument("--graph", default=".dev-graph/state/graph.json")
    apply_macro.add_argument("--request-json", required=True, help="same C14 macro intent JSON used for preview-macro")
    apply_macro.add_argument("--expected-candidate-digest", required=True, help="candidate_graph_digest from the immediately preceding preview-macro receipt")
    apply_macro.add_argument("--receipt", required=True, help="immutable macro registration receipt output")
    register = sub.add_parser("register")
    register.add_argument("--repo-root")
    register.add_argument("--package", required=True, help="feature-execution-package JSON")
    register.add_argument("--graph", required=True, help="dev-graph-registration JSON")
    register.add_argument("--output", required=True, help="existing dev graph JSON containing parent feature")
    register.add_argument("--receipt", required=True, help="immutable registration receipt output")
    register.add_argument("--tracker-mode", choices=("beads", "github", "both", "none"), default="none")
    register.add_argument("--dry-run", action="store_true")
    register.add_argument("--system-planner-root", default=str(DEFAULT_SYSTEM_ROOT))
    register.add_argument("--required-version", default=None)
    register.add_argument("--required-schema-version", default="1.0.0")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--system-planner-root", default=str(DEFAULT_SYSTEM_ROOT))
    preflight.add_argument("--required-version", default=None)
    preflight.add_argument("--required-schema-version", default="1.0.0")
    execution = sub.add_parser("execution-context")
    execution.add_argument("--repo-root")
    execution.add_argument("--graph", required=True)
    execution.add_argument("--graph-node-id", required=True)
    execution.add_argument("--context-json", required=True)
    execution.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preflight":
            report = preflight_contract(Path(args.system_planner_root), args.required_version, args.required_schema_version)
        elif args.command == "artifacts":
            report = _write_artifacts(args)
        elif args.command == "preview-macro":
            report = _preview_macro(args)
        elif args.command == "apply-macro":
            report = _apply_macro(args)
        elif args.command == "execution-context":
            report = _project_execution_context(args)
        else: report = _register(args)
        dump(report); return 1 if report.get("status") == "rejected" else 0
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        dump({"valid": False, "error": str(exc)}); return 2


if __name__ == "__main__": raise SystemExit(main())
