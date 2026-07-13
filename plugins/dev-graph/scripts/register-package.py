#!/usr/bin/env python3
# /// script
# name: register-package
# purpose: Validate and atomically register one promoted exact-13 system-dev-planner package in the dev graph.
# inputs: ["argv: register --package/--graph/--output/--receipt", "argv: execution-context --graph/--graph-node-id/--context-json", "argv: preflight"]
# outputs: ["stdout: JSON preview/receipt/preflight report"]
# requires-python = ">=3.10"
# dependencies: [_common.py]
# contexts: [A, B, C, E]
# network: false
# write-scope: explicitly selected dev-graph output and immutable receipt
# ///
"""C02 exact-13 package registration consumer and cross-plugin preflight."""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from _common import ContractError, atomic_json, contained, dump, load_json, utc_now

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
    "graph_revision_after", "graph_digest_after", "output_path",
}


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


def _json_object(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict): raise ContractError(f"JSON object required: {path}")
    return value


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _schema_version(schema: dict[str, Any], name: str) -> str:
    value = (((schema.get("properties") or {}).get("schema_version") or {}).get("const"))
    if not isinstance(value, str): raise ContractError(f"{name} does not pin properties.schema_version.const")
    return value


def preflight_contract(system_root: Path, required_version: str, required_schema_version: str) -> dict[str, Any]:
    root = system_root.resolve(strict=True)
    manifest = _json_object(root / ".claude-plugin" / "plugin.json")
    if manifest.get("name") != "system-dev-planner": raise ContractError("unexpected upstream plugin name")
    if manifest.get("version") != required_version:
        raise ContractError(f"system-dev-planner version mismatch: expected {required_version}, got {manifest.get('version')}")
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
    return {"valid": True, "plugin": "system-dev-planner", "version": required_version,
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


@contextmanager
def _single_writer(output: Path) -> Iterator[None]:
    lock_path = output.with_name(f".{output.name}.register.lock")
    with lock_path.open("a+", encoding="utf-8") as stream:
        try: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ContractError(f"registration writer is already active: {output}") from exc
        yield


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
            before = receipt.get("graph_revision_before")
            after = receipt.get("graph_revision_after")
            if not isinstance(before, int) or not isinstance(after, int) or after != before + 1 or after > revision_before:
                raise ContractError("immutable receipt graph revision conflicts with registered package")
            return {**receipt, "idempotent": True, "dry_run": bool(args.dry_run)}
        if receipt_path.exists(): raise ContractError("immutable receipt exists before graph registration")
        proposed = copy.deepcopy(current)
        proposed["nodes"] = [*existing, *resolved]
        proposed["graph_revision"] = revision_before + 1
        graph_digest = _canonical_digest(proposed)
        receipt = {
            "schema_version": "1.0.0", "status": "registered", "registered_at": utc_now(),
            "feature_package_id": package["feature_package_id"], "parent_feature": package["parent_feature"],
            "source_digest": registration["source_digest"], "expected_count": 13, "applied_count": 13,
            "phase_refs": PHASES, "node_ids": incoming_ids, "graph_revision_before": revision_before,
            "graph_revision_after": revision_before + 1, "graph_digest_after": graph_digest,
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
    parser = argparse.ArgumentParser(description="Register exact-13 packages or preflight system-dev-planner")
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--repo-root")
    register.add_argument("--package", required=True, help="feature-execution-package JSON")
    register.add_argument("--graph", required=True, help="dev-graph-registration JSON")
    register.add_argument("--output", required=True, help="existing dev graph JSON containing parent feature")
    register.add_argument("--receipt", required=True, help="immutable registration receipt output")
    register.add_argument("--tracker-mode", choices=("beads", "github", "both", "none"), default="none")
    register.add_argument("--dry-run", action="store_true")
    register.add_argument("--system-planner-root", default=str(DEFAULT_SYSTEM_ROOT))
    register.add_argument("--required-version", default="0.1.0")
    register.add_argument("--required-schema-version", default="1.0.0")
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--system-planner-root", default=str(DEFAULT_SYSTEM_ROOT))
    preflight.add_argument("--required-version", default="0.1.0")
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
        elif args.command == "execution-context":
            report = _project_execution_context(args)
        else: report = _register(args)
        dump(report); return 0
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        dump({"valid": False, "error": str(exc)}); return 2


if __name__ == "__main__": raise SystemExit(main())
