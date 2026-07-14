#!/usr/bin/env python3
# /// script
# name: validate-system-plan
# purpose: staged feature package/exact 13 task specs/inventory/DAG を決定論検証する。
# inputs: argv --repo-root/--staging/--config
# outputs: stdout validation report JSON
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [resolve-project-context.py]
# requires-python: ">=3.10"
# ///
"""C12 deterministic promotion gate."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASES = [f"P{i:02d}" for i in range(1, 14)]
TASK_PATHS = [
    "task-specs/phase-01-requirements.md", "task-specs/phase-02-architecture.md",
    "task-specs/phase-03-design-review.md", "task-specs/phase-04-test-design.md",
    "task-specs/phase-05-implementation.md", "task-specs/phase-06-test-run.md",
    "task-specs/phase-07-acceptance.md", "task-specs/phase-08-refactoring-migration.md",
    "task-specs/phase-09-quality-assurance.md", "task-specs/phase-10-final-review.md",
    "task-specs/phase-11-evidence.md", "task-specs/phase-12-documentation-operations.md",
    "task-specs/phase-13-release-deploy.md",
]
BASE_DIGEST_FILES = ["feature-package.json", "workstream-inventory.json", "task-graph.json", *TASK_PATHS]
HANDOFF_PATH = "system-build-handoff.json"
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD)\b|__PLACEHOLDER__|<[^>]+>", re.I)
SCHEMAS = HERE.parent / "schemas"
TASK_SPEC_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
REQUIRED_TASK_SPEC_SECTIONS = (
    "Machine-readable registration fields",
    "目的",
    "背景",
    "前提条件",
    "Workstream applicability",
    "Architecture and deploy unit",
    "成果物",
    "Tracker publication and completion",
    "Branch and worktree execution",
    "スコープ外",
    "Verification and evidence",
    "Rollout and rollback",
    "Handoff",
    "参照情報",
)


def _resolver():
    spec = importlib.util.spec_from_file_location("sdp_context", HERE / "resolve-project-context.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def canonical_digest(root: Path, relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(relative_paths):
        path = root / rel
        digest.update(rel.encode()); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _type_matches(value: object, expected: object) -> bool:
    choices = expected if isinstance(expected, list) else [expected]
    mapping = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    return any(kind in mapping and mapping[kind](value) for kind in choices)


def _resolve_local_ref(root_schema: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported non-local schema ref: {ref}")
    value: object = root_schema
    for raw in ref[2:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"unresolved local schema ref: {ref}")
        value = value[key]
    if not isinstance(value, dict):
        raise ValueError(f"schema ref does not resolve to object: {ref}")
    return value


def schema_violations(value: object, schema: dict, path: str = "$", root_schema: dict | None = None) -> list[str]:
    """Validate the JSON-Schema subset used by the bundled runtime schemas.

    Supported constraints intentionally include every keyword used by
    feature-execution-package and workstream-inventory: local refs, type,
    required, properties/additionalProperties, const/enum/pattern, bounds,
    array prefix/items/uniqueness, allOf and if/then.
    """
    root = root_schema or schema
    if "$ref" in schema:
        return schema_violations(value, _resolve_local_ref(root, schema["$ref"]), path, root)
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _type_matches(value, expected):
        return [f"{path}: type must be {expected!r}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside enum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append(f"{path}: invalid date-time")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: required property missing: {key}")
        properties = schema.get("properties", {})
        for key, child in properties.items():
            if key in value:
                errors.extend(schema_violations(value[key], child, f"{path}.{key}", root))
        extras = set(value) - set(properties)
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for key in sorted(extras):
                errors.append(f"{path}: additional property forbidden: {key}")
        elif isinstance(additional, dict):
            for key in sorted(extras):
                errors.extend(schema_violations(value[key], additional, f"{path}.{key}", root))
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errors.append(f"{path}: fewer than minProperties")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(f"{path}: more than maxProperties")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items are not unique")
        prefix = schema.get("prefixItems", [])
        for index, child in enumerate(prefix[:len(value)]):
            errors.extend(schema_violations(value[index], child, f"{path}[{index}]", root))
        items = schema.get("items")
        start = len(prefix) if prefix else 0
        if items is False and len(value) > start:
            errors.append(f"{path}: additional array items forbidden")
        elif isinstance(items, dict):
            for index in range(start, len(value)):
                errors.extend(schema_violations(value[index], items, f"{path}[{index}]", root))
    for child in schema.get("allOf", []):
        errors.extend(schema_violations(value, child, path, root))
    condition = schema.get("if")
    if isinstance(condition, dict) and not schema_violations(value, condition, path, root):
        then = schema.get("then")
        if isinstance(then, dict):
            errors.extend(schema_violations(value, then, path, root))
    return errors


def _load_schema(name: str) -> dict:
    value = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"schema must be object: {name}")
    return value


def task_spec_violations(text: str) -> list[tuple[str, str]]:
    """Return structural violations against the canonical task overlay.

    The template's prose says every standard section must be populated and
    names seven sections as the minimum readiness gate.  Treating all standard
    sections as required keeps C12 fail-closed and prevents a title plus one
    sentence from being promoted as an executable task specification.
    """
    headings = list(TASK_SPEC_HEADING.finditer(text))
    by_name: dict[str, list[int]] = {}
    for index, heading in enumerate(headings):
        by_name.setdefault(heading.group(1).strip(), []).append(index)

    errors: list[tuple[str, str]] = []
    for name in REQUIRED_TASK_SPEC_SECTIONS:
        occurrences = by_name.get(name, [])
        if not occurrences:
            errors.append(("task-spec-section-missing", name))
            continue
        if len(occurrences) > 1:
            errors.append(("task-spec-section-duplicate", name))
            continue
        heading_index = occurrences[0]
        start = headings[heading_index].end()
        end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        if not body:
            errors.append(("task-spec-section-empty", name))
    return errors


def validate(staging: Path, repository_id: str) -> dict:
    violations: list[dict] = []
    def fail(code: str, path: str, detail: str) -> None:
        violations.append({"code": code, "path": path, "detail": detail})
    def safe_path(rel: str) -> Path | None:
        candidate = staging / rel
        try:
            relative = candidate.relative_to(staging)
        except ValueError:
            fail("path-containment", rel, "path escapes staging")
            return None
        cursor = staging
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                fail("path-symlink", rel, f"symlink component forbidden: {cursor.name}")
                return None
        try:
            candidate.resolve(strict=False).relative_to(staging.resolve(strict=True))
        except (OSError, ValueError):
            fail("path-containment", rel, "resolved path escapes staging")
            return None
        return candidate
    def load(rel: str):
        p = safe_path(rel)
        if p is None:
            return None
        if not p.is_file():
            fail("missing-file", rel, "required file is absent"); return None
        try: return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc: fail("invalid-json", rel, str(exc)); return None

    package = load("feature-package.json")
    inventory = load("workstream-inventory.json")
    graph = load("task-graph.json")
    handoff = load(HANDOFF_PATH)
    manifest = load("staging-manifest.json")
    if not all(isinstance(x, dict) for x in (package, inventory, graph, handoff, manifest)):
        return {"status": "fail", "violations": violations, "validated_digest": None}
    package_id, parent = package.get("feature_package_id"), package.get("parent_feature")
    for detail in schema_violations(package, _load_schema("feature-execution-package.schema.json")):
        fail("package-schema", "feature-package.json", detail)
    for detail in schema_violations(inventory, _load_schema("workstream-inventory.schema.json")):
        fail("inventory-schema", "workstream-inventory.json", detail)
    for detail in schema_violations(handoff, _load_schema("system-build-handoff.schema.json")):
        fail("handoff-schema", HANDOFF_PATH, detail)
    if package.get("task_count") != 13 or package.get("phase_refs") != PHASES:
        fail("package-exact-set", "feature-package.json", "task_count=13 and ordered P01..P13 required")
    if package.get("task_spec_paths") != TASK_PATHS:
        fail("task-path-exact-set", "feature-package.json", "canonical 13 task paths required")
    tasks = inventory.get("tasks") if isinstance(inventory.get("tasks"), list) else []
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    if len(tasks) != 13: fail("inventory-count", "workstream-inventory.json", f"expected 13, got {len(tasks)}")
    if len(nodes) != 13: fail("graph-count", "task-graph.json", f"expected 13, got {len(nodes)}")
    task_phases = [t.get("phase_ref") for t in tasks]
    node_phases = [n.get("phase_ref") for n in nodes]
    if task_phases != PHASES: fail("inventory-phase-exact-set", "workstream-inventory.json", repr(task_phases))
    if node_phases != PHASES: fail("graph-phase-exact-set", "task-graph.json", repr(node_phases))
    if inventory.get("feature_package_id") != package_id or inventory.get("parent_feature") != parent:
        fail("inventory-package-mismatch", "workstream-inventory.json", "common package/parent required")
    handoff_identity = handoff.get("identity") if isinstance(handoff.get("identity"), dict) else {}
    expected_handoff_identity = {
        "repository_id": repository_id,
        "feature_id": parent,
        "feature_package_id": package_id,
        "parent_feature": parent,
        "source_feature_digest": package.get("source_feature_digest"),
    }
    if handoff_identity != expected_handoff_identity:
        fail("handoff-identity", HANDOFF_PATH, "repository/feature/package/source digest identity mismatch")
    ids = [str(t.get("id", "")) for t in tasks]
    node_ids = [str(n.get("id", n.get("graph_node_id", ""))) for n in nodes]
    if len(set(ids)) != 13 or any(not x for x in ids): fail("task-id-set", "workstream-inventory.json", "13 unique ids required")
    if len(set(node_ids)) != 13 or any(not x for x in node_ids): fail("node-id-set", "task-graph.json", "13 unique ids required")
    if package.get("task_node_ids") != node_ids:
        fail("package-node-id-exact-set", "feature-package.json", "task_node_ids must equal graph node order")
    if ids != node_ids:
        fail("inventory-node-id-parity", "workstream-inventory.json", "task ids must equal graph node ids")
    handoff_tasks = handoff.get("execution_tasks") if isinstance(handoff.get("execution_tasks"), list) else []
    if len(handoff_tasks) == 13:
        for index, entry in enumerate(handoff_tasks):
            expected = {
                "task_id": ids[index] if index < len(ids) else None,
                "phase_ref": PHASES[index],
                "task_spec_path": TASK_PATHS[index],
                "build_target_kind": tasks[index].get("build_target_kind") if index < len(tasks) else None,
                "depends_on": nodes[index].get("depends_on") if index < len(nodes) else None,
            }
            if entry != expected:
                fail("handoff-task-parity", f"{HANDOFF_PATH}#execution_tasks[{index}]", "task identity/path/dependency mismatch")
    else:
        fail("handoff-task-count", HANDOFF_PATH, f"expected 13 execution tasks, got {len(handoff_tasks)}")
    phase_by_id = {node_ids[i]: node_phases[i] for i in range(min(len(node_ids), len(node_phases)))}
    for rel in TASK_PATHS:
        p = safe_path(rel)
        if p is None:
            continue
        if not p.is_file(): fail("missing-task-spec", rel, "required exact-set member")
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
            if not text.strip(): fail("empty-task-spec", rel, "task spec is empty")
            if PLACEHOLDER.search(text): fail("placeholder", rel, "unresolved placeholder remains")
            for code, section in task_spec_violations(text):
                fail(code, rel, section)
    for i, task in enumerate(tasks):
        if task.get("feature_package_id") != package_id or task.get("parent_feature") != parent:
            fail("mixed-task-package", f"tasks[{i}]", "feature_package_id/parent_feature mismatch")
        if task.get("implementation_readiness", {}).get("status") != "complete":
            fail("not-ready", f"tasks[{i}]", "implementation_readiness must be complete")
        registration = task.get("graph_node_registration")
        file_path = registration.get("file_path") if isinstance(registration, dict) else None
        if (
            not isinstance(file_path, str)
            or re.fullmatch(r"tasks/[^/]+\.md", file_path) is None
            or ".." in Path(file_path).parts
        ):
            fail("registration-file-path", f"tasks[{i}].graph_node_registration.file_path",
                 "single-segment tasks/<node>.md repository-relative path required")
    for i, node in enumerate(nodes):
        for field in ("phase_ref", "feature_package_id", "parent_feature", "depends_on"):
            if field not in node:
                fail("graph-required-field", f"nodes[{i}]", field)
        if not isinstance(node.get("depends_on"), list) or any(not isinstance(x, str) for x in node.get("depends_on", [])):
            fail("graph-dependency-type", f"nodes[{i}].depends_on", "string[] required")
            continue
        if node.get("feature_package_id") != package_id or node.get("parent_feature") != parent:
            fail("mixed-node-package", f"nodes[{i}]", "feature_package_id/parent_feature mismatch")
        current = node.get("phase_ref")
        for dep in node.get("depends_on", []):
            if dep not in phase_by_id: fail("cross-feature-or-missing-edge", f"nodes[{i}].depends_on", str(dep))
            elif PHASES.index(phase_by_id[dep]) >= PHASES.index(current):
                fail("non-forward-edge", f"nodes[{i}].depends_on", f"{dep} -> {node_ids[i]}")
    repo_ctx = inventory.get("repo_context", {})
    if repo_ctx.get("repo_identity") != repository_id:
        fail("repo-identity", "workstream-inventory.json", "repo identity differs from C09 context")
    manifest_files = manifest.get("files")
    rels: list[str] = []
    if isinstance(manifest_files, dict): rels = sorted(manifest_files)
    elif isinstance(manifest_files, list): rels = sorted(x.get("path") for x in manifest_files if isinstance(x, dict) and isinstance(x.get("path"), str))
    required_digest_files = [*BASE_DIGEST_FILES, HANDOFF_PATH]
    if sorted(rels) != sorted(required_digest_files):
        fail("manifest-exact-set", "staging-manifest.json", "manifest must cover package/inventory/graph/exact 13 task specs/system handoff")
    for rel in rels:
        if rel not in required_digest_files:
            continue
        p = safe_path(rel)
        if p is None:
            continue
        if not p.is_file(): continue
        expected = manifest_files.get(rel) if isinstance(manifest_files, dict) else next((x.get("sha256") for x in manifest_files if x.get("path") == rel), None)
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if isinstance(expected, str): expected = expected.removeprefix("sha256:")
        if expected != actual: fail("file-digest", rel, f"expected={expected} actual={actual}")
    digest = canonical_digest(staging, rels) if sorted(rels) == sorted(required_digest_files) and all(
        safe_path(x) is not None and (staging / x).is_file() for x in rels
    ) else None
    expected_digest = manifest.get("canonical_digest") or manifest.get("staging_digest")
    if expected_digest != digest: fail("canonical-digest", "staging-manifest.json", f"expected={expected_digest} actual={digest}")
    source_inputs = handoff.get("source_inputs") if isinstance(handoff.get("source_inputs"), list) else []
    source_map = {
        entry.get("path"): entry.get("sha256")
        for entry in source_inputs if isinstance(entry, dict)
    }
    if len(source_inputs) != len(BASE_DIGEST_FILES) or set(source_map) != set(BASE_DIGEST_FILES):
        fail("handoff-source-exact-set", HANDOFF_PATH, "source_inputs must cover exact pre-handoff manifest files")
    else:
        for rel in BASE_DIGEST_FILES:
            actual = hashlib.sha256((staging / rel).read_bytes()).hexdigest()
            if source_map.get(rel) != actual:
                fail("handoff-source-digest", f"{HANDOFF_PATH}#{rel}", "source input digest mismatch")
    base_digest = canonical_digest(staging, BASE_DIGEST_FILES) if all((staging / rel).is_file() for rel in BASE_DIGEST_FILES) else None
    source_manifest = handoff.get("source_manifest") if isinstance(handoff.get("source_manifest"), dict) else {}
    if source_manifest.get("canonical_digest_before_handoff") != base_digest:
        fail("handoff-source-canonical-digest", HANDOFF_PATH, "pre-handoff canonical digest mismatch")
    contract = manifest.get("handoff_contract") if isinstance(manifest.get("handoff_contract"), dict) else {}
    handoff_sha = hashlib.sha256((staging / HANDOFF_PATH).read_bytes()).hexdigest() if (staging / HANDOFF_PATH).is_file() else None
    if (
        contract.get("schema_version") != "1.0.0"
        or contract.get("path") != HANDOFF_PATH
        or contract.get("sha256") != handoff_sha
        or contract.get("source_canonical_digest") != base_digest
        or contract.get("manifest_is_commit_point") is not True
        or contract.get("self_reference_policy") != "handoff hash and final digest are manifest-only"
    ):
        fail("handoff-manifest-contract", "staging-manifest.json", "handoff commit-point contract mismatch")
    return {"schema_version": "1.0.0", "status": "pass" if not violations else "fail",
            "validated_digest": digest, "feature_package_id": package_id, "parent_feature": parent,
            "phase_refs": PHASES, "violations": violations}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate staged system plan")
    p.add_argument("--repo-root"); p.add_argument("--config", default=".dev-graph/config.json")
    p.add_argument("--staging", required=True, help="repository-relative staging generation path")
    args = p.parse_args(argv); c09 = _resolver()
    try:
        context = c09.build_context(["--repo-root", args.repo_root, "--config", args.config] if args.repo_root else ["--config", args.config], dict(os.environ))
        staging = Path(c09.guard_relative_path(Path(context["repo_root"]), args.staging))
        report = validate(staging, context["repository_id"])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 2
    except c09.UsageError as exc: print(f"[validate] {exc}", file=sys.stderr); return 1
    except (c09.PolicyError, OSError, ValueError) as exc: print(f"[validate fail-closed] {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
