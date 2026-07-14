#!/usr/bin/env python3
# /// script
# name: build-system-handoff
# purpose: validated exact-13 staging packageからversioned system-build-handoffを決定論生成し、handoffを含むmanifestをatomic commitする。
# inputs: argv --repo-root/--staging/--config
# outputs: staging/system-build-handoff.json, updated staging-manifest.json, stdout JSON receipt
# contexts: [C, E]
# network: false
# write-scope: caller repository内の指定staging generationのみ
# dependencies: [resolve-project-context.py, schemas/system-build-handoff.schema.json]
# requires-python: ">=3.10"
# ///
"""Build the C14 system execution handoff without forging downstream receipts.

The staging manifest is the commit point.  The handoff is written first and is
not authoritative until the manifest atomically names its SHA-256.  This also
avoids an impossible digest cycle: the handoff records the *input* manifest
hash and source-package digest, while its own hash and the final canonical
digest live only in the final manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


EXIT_OK = 0
EXIT_USAGE = 1
EXIT_POLICY = 2
HERE = Path(__file__).resolve().parent
SCHEMAS = HERE.parent / "schemas"
HANDOFF_PATH = "system-build-handoff.json"
MANIFEST_PATH = "staging-manifest.json"
PHASES = [f"P{i:02d}" for i in range(1, 14)]
TASK_PATHS = [
    "task-specs/phase-01-requirements.md",
    "task-specs/phase-02-architecture.md",
    "task-specs/phase-03-design-review.md",
    "task-specs/phase-04-test-design.md",
    "task-specs/phase-05-implementation.md",
    "task-specs/phase-06-test-run.md",
    "task-specs/phase-07-acceptance.md",
    "task-specs/phase-08-refactoring-migration.md",
    "task-specs/phase-09-quality-assurance.md",
    "task-specs/phase-10-final-review.md",
    "task-specs/phase-11-evidence.md",
    "task-specs/phase-12-documentation-operations.md",
    "task-specs/phase-13-release-deploy.md",
]
SOURCE_PATHS = ["feature-package.json", "workstream-inventory.json", "task-graph.json", *TASK_PATHS]
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD)\b|__PLACEHOLDER__|<[^>]+>", re.I)
TASK_SPEC_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
REQUIRED_TASK_SPEC_SECTIONS = (
    "Machine-readable registration fields", "目的", "背景", "前提条件",
    "Workstream applicability", "Architecture and deploy unit", "成果物",
    "Tracker publication and completion", "Branch and worktree execution", "スコープ外",
    "Verification and evidence", "Rollout and rollback", "Handoff", "参照情報",
)


class UsageError(Exception):
    """Invalid CLI invocation (exit 1)."""


class PolicyError(Exception):
    """Invalid or unsafe staging package (exit 2)."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module load failed: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"invalid JSON: {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyError(f"JSON object required: {path.name}")
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_digest(contents: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(contents):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(contents[rel])
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _reject_symlink_chain(repo_root: Path, path: Path) -> None:
    """Reject every symlink component, including a not-yet-read leaf."""
    try:
        rel = path.absolute().relative_to(repo_root.absolute())
    except ValueError as exc:
        raise PolicyError(f"path escapes repository: {path}") from exc
    current = repo_root.absolute()
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise PolicyError(f"symlink path component is forbidden: {current}")


def _safe_file(repo_root: Path, staging: Path, rel: str) -> Path:
    candidate = staging / rel
    _reject_symlink_chain(repo_root, candidate)
    if not candidate.is_file():
        raise PolicyError(f"required staging input missing: {rel}")
    try:
        candidate.resolve(strict=True).relative_to(repo_root.resolve(strict=True))
    except ValueError as exc:
        raise PolicyError(f"staging input escapes repository: {rel}") from exc
    return candidate


def _manifest_files(manifest: dict) -> dict[str, str]:
    raw = manifest.get("files")
    if isinstance(raw, dict):
        pairs = raw.items()
    elif isinstance(raw, list):
        pairs = ((item.get("path"), item.get("sha256")) for item in raw if isinstance(item, dict))
    else:
        raise PolicyError("staging-manifest files must be an object or path/sha256 array")
    result: dict[str, str] = {}
    for path, digest in pairs:
        if not isinstance(path, str) or not isinstance(digest, str):
            raise PolicyError("staging-manifest files entries require string path/sha256")
        normalized = digest.removeprefix("sha256:")
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise PolicyError(f"invalid manifest sha256: {path}")
        if path in result:
            raise PolicyError(f"duplicate manifest path: {path}")
        result[path] = normalized
    return result


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
    """Standalone JSON-Schema subset so approved C14 has no C12 build dependency."""
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
        for key in schema.get("required", []):
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
    return _json(SCHEMAS / name)


def task_spec_violations(text: str) -> list[tuple[str, str]]:
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
        index = occurrences[0]
        start = headings[index].end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        if not text[start:end].strip():
            errors.append(("task-spec-section-empty", name))
    return errors


def _schema_check(handoff: dict, validator=None) -> None:
    schema = _load_schema("system-build-handoff.schema.json")
    violations = schema_violations(handoff, schema)
    if violations:
        raise PolicyError("generated handoff schema violation: " + "; ".join(violations))


def _validate_sources(
    *, repo_root: Path, staging: Path, repository_id: str, validator=None
) -> tuple[dict, dict, dict, dict[str, bytes], dict, dict]:
    manifest_file = _safe_file(repo_root, staging, MANIFEST_PATH)
    package = _json(_safe_file(repo_root, staging, "feature-package.json"))
    inventory = _json(_safe_file(repo_root, staging, "workstream-inventory.json"))
    graph = _json(_safe_file(repo_root, staging, "task-graph.json"))
    manifest = _json(manifest_file)

    package_errors = schema_violations(package, _load_schema("feature-execution-package.schema.json"))
    inventory_errors = schema_violations(inventory, _load_schema("workstream-inventory.schema.json"))
    if package_errors or inventory_errors:
        raise PolicyError("source schema violation: " + "; ".join(package_errors + inventory_errors))

    package_id = package.get("feature_package_id")
    parent = package.get("parent_feature")
    if inventory.get("feature_package_id") != package_id or inventory.get("parent_feature") != parent:
        raise PolicyError("package/inventory feature identity mismatch")
    if inventory.get("repo_context", {}).get("repo_identity") != repository_id:
        raise PolicyError("inventory repository identity differs from resolved caller repository")
    if package.get("phase_refs") != PHASES or package.get("task_spec_paths") != TASK_PATHS:
        raise PolicyError("feature package must name the exact ordered P01..P13 task paths")

    tasks = inventory.get("tasks")
    nodes = graph.get("nodes")
    if not isinstance(tasks, list) or not isinstance(nodes, list) or len(tasks) != 13 or len(nodes) != 13:
        raise PolicyError("inventory and task graph must each contain exactly 13 entries")
    task_ids = [item.get("id") for item in tasks if isinstance(item, dict)]
    node_ids = [item.get("id", item.get("graph_node_id")) for item in nodes if isinstance(item, dict)]
    task_phases = [item.get("phase_ref") for item in tasks if isinstance(item, dict)]
    node_phases = [item.get("phase_ref") for item in nodes if isinstance(item, dict)]
    if task_ids != node_ids or package.get("task_node_ids") != node_ids or len(set(task_ids)) != 13:
        raise PolicyError("package/inventory/graph task id exact-set mismatch")
    if task_phases != PHASES or node_phases != PHASES:
        raise PolicyError("inventory/graph phase exact-set mismatch")
    for index, (task, node) in enumerate(zip(tasks, nodes)):
        if not isinstance(task, dict) or not isinstance(node, dict):
            raise PolicyError(f"task/node object required at index {index}")
        for value in (task, node):
            if value.get("feature_package_id") != package_id or value.get("parent_feature") != parent:
                raise PolicyError(f"mixed feature identity at P{index + 1:02d}")
        if task.get("depends_on") != node.get("depends_on"):
            raise PolicyError(f"inventory/graph dependency mismatch at P{index + 1:02d}")

    contents = {rel: _safe_file(repo_root, staging, rel).read_bytes() for rel in SOURCE_PATHS}
    for rel, phase in zip(TASK_PATHS, PHASES):
        text = contents[rel].decode("utf-8", errors="replace")
        if not text.strip() or PLACEHOLDER.search(text):
            raise PolicyError(f"task spec empty or placeholder-bearing: {rel}")
        section_errors = task_spec_violations(text)
        if section_errors:
            raise PolicyError(f"task spec section violation ({phase}): {section_errors}")

    files = _manifest_files(manifest)
    allowed_sets = {frozenset(SOURCE_PATHS), frozenset([*SOURCE_PATHS, HANDOFF_PATH])}
    if frozenset(files) not in allowed_sets:
        raise PolicyError("manifest path exact-set must be source inputs plus optional system handoff")
    for rel in SOURCE_PATHS:
        actual = _sha(contents[rel])
        if files.get(rel) != actual:
            raise PolicyError(f"manifest digest mismatch: {rel}")
    source_digest = _canonical_digest(contents)

    existing_handoff: dict = {}
    if HANDOFF_PATH in files:
        handoff_file = _safe_file(repo_root, staging, HANDOFF_PATH)
        if files[HANDOFF_PATH] != _sha(handoff_file.read_bytes()):
            raise PolicyError("manifest digest mismatch: system-build-handoff.json")
        final_contents = dict(contents, **{HANDOFF_PATH: handoff_file.read_bytes()})
        if manifest.get("canonical_digest") != _canonical_digest(final_contents):
            raise PolicyError("final manifest canonical digest mismatch")
        existing_handoff = _json(handoff_file)
        _schema_check(existing_handoff, validator)
        source_manifest = existing_handoff.get("source_manifest")
        if not isinstance(source_manifest, dict) or source_manifest.get("canonical_digest_before_handoff") != source_digest:
            raise PolicyError("existing handoff source digest differs from current source inputs")
    else:
        if manifest.get("canonical_digest") != source_digest:
            raise PolicyError("source manifest canonical digest mismatch")
        source_manifest = {
            "path": MANIFEST_PATH,
            "sha256_before_handoff": _sha(manifest_file.read_bytes()),
            "canonical_digest_before_handoff": source_digest,
        }
    return package, inventory, graph, contents, manifest, source_manifest


def _build_handoff(
    package: dict,
    inventory: dict,
    graph: dict,
    contents: dict[str, bytes],
    source_manifest: dict,
) -> dict:
    tasks = inventory["tasks"]
    nodes = graph["nodes"]
    return {
        "schema_version": "1.0.0",
        "kind": "system-build-handoff",
        "identity": {
            "repository_id": inventory["repo_context"]["repo_identity"],
            "feature_id": package["parent_feature"],
            "feature_package_id": package["feature_package_id"],
            "parent_feature": package["parent_feature"],
            "source_feature_digest": package["source_feature_digest"],
        },
        "source_inputs": [
            {"path": rel, "sha256": _sha(contents[rel])} for rel in SOURCE_PATHS
        ],
        "source_manifest": source_manifest,
        "digest_contract": {
            "algorithm": "sha256",
            "source_digest_scope": "source_inputs only; handoff and manifest excluded",
            "handoff_digest_location": "staging-manifest.json#files/system-build-handoff.json",
            "final_manifest_digest_scope": "all manifest files including handoff; manifest itself excluded",
            "self_reference_policy": "handoff omits its own digest and final manifest digest",
        },
        "execution_tasks": [
            {
                "task_id": task["id"],
                "phase_ref": task["phase_ref"],
                "task_spec_path": TASK_PATHS[index],
                "build_target_kind": task["build_target_kind"],
                "depends_on": node["depends_on"],
            }
            for index, (task, node) in enumerate(zip(tasks, nodes))
        ],
        "registration_request": {
            "path": "dev-graph-registration.json",
            "owner": "system-dev-planner/C11",
            "consumer": "dev-graph/C02",
            "status": "deferred-until-promotion",
            "promotion_receipt": {
                "path": "atomic-promotion-receipt.json",
                "owner": "system-dev-planner/C11",
                "status": "not-emitted",
                "produced_by_this_component": False,
            },
            "registration_receipt": {
                "path": "dev-graph-registration-receipt.json",
                "owner": "dev-graph/C02",
                "status": "not-emitted",
                "produced_by_this_component": False,
            },
        },
    }


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_replace(path: Path, data: bytes) -> None:
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def _commit(staging: Path, manifest: dict, handoff: dict, source_contents: dict[str, bytes]) -> dict:
    handoff_bytes = _encoded(handoff)
    handoff_sha = _sha(handoff_bytes)
    final_contents = dict(source_contents, **{HANDOFF_PATH: handoff_bytes})
    final_digest = _canonical_digest(final_contents)
    final_manifest = {
        key: value
        for key, value in manifest.items()
        if key not in {"files", "canonical_digest", "staging_digest", "handoff_contract"}
    }
    final_manifest.update({
        "files": {rel: _sha(final_contents[rel]) for rel in sorted(final_contents)},
        "canonical_digest": final_digest,
        "handoff_contract": {
            "schema_version": "1.0.0",
            "path": HANDOFF_PATH,
            "sha256": handoff_sha,
            "source_canonical_digest": handoff["source_manifest"]["canonical_digest_before_handoff"],
            "manifest_is_commit_point": True,
            "self_reference_policy": "handoff hash and final digest are manifest-only",
        },
    })

    # A handoff not named by the manifest is uncommitted and must be ignored.
    # Therefore writing the manifest second gives the pair a single visibility
    # commit point while keeping both file replacements atomic.
    _atomic_replace(staging / HANDOFF_PATH, handoff_bytes)
    _atomic_replace(staging / MANIFEST_PATH, _encoded(final_manifest))
    return {
        "schema_version": "1.0.0",
        "status": "generated",
        "handoff_path": str(staging / HANDOFF_PATH),
        "manifest_path": str(staging / MANIFEST_PATH),
        "handoff_sha256": handoff_sha,
        "canonical_digest": final_digest,
        "input_count": len(source_contents) + 1,
        "receipt_artifacts_created": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = Parser(description="Build deterministic system-build-handoff.json")
    parser.add_argument("--repo-root")
    parser.add_argument("--config", default=".dev-graph/config.json")
    parser.add_argument("--staging", required=True, help="caller-repository-relative staging generation")
    try:
        args = parser.parse_args(argv)
        c09 = _load("sdp_handoff_context", HERE / "resolve-project-context.py")
        cargs = ["--config", args.config]
        if args.repo_root:
            cargs[:0] = ["--repo-root", args.repo_root]
        context = c09.build_context(cargs, dict(os.environ))
        repo_root = Path(context["repo_root"])
        # Inspect the caller-spelled path before C09 returns its resolved path;
        # otherwise an in-repository staging symlink would be normalized away
        # before the explicit no-symlink policy can observe it.
        _reject_symlink_chain(repo_root, repo_root / Path(args.staging))
        staging = Path(c09.guard_relative_path(repo_root, args.staging))
        _reject_symlink_chain(repo_root, staging)
        if not staging.is_dir():
            raise PolicyError("staging must be an existing directory")
        _reject_symlink_chain(repo_root, staging / HANDOFF_PATH)
        package, inventory, graph, contents, manifest, source_manifest = _validate_sources(
            repo_root=repo_root,
            staging=staging,
            repository_id=context["repository_id"],
        )
        handoff = _build_handoff(package, inventory, graph, contents, source_manifest)
        _schema_check(handoff)
        receipt = _commit(staging, manifest, handoff, contents)
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK
    except UsageError as exc:
        print(f"[system-handoff usage] {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, UnicodeError) as exc:
        print(f"[system-handoff io] {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (PolicyError, ValueError) as exc:
        print(f"[system-handoff fail-closed] {exc}", file=sys.stderr)
        return EXIT_POLICY
    except Exception as exc:
        # C09 exports its own UsageError/PolicyError classes, which cannot be
        # named statically because its hyphenated module is loaded at runtime.
        if exc.__class__.__name__ == "UsageError":
            print(f"[system-handoff usage] {exc}", file=sys.stderr)
            return EXIT_USAGE
        if exc.__class__.__name__ == "PolicyError":
            print(f"[system-handoff fail-closed] {exc}", file=sys.stderr)
            return EXIT_POLICY
        raise


if __name__ == "__main__":
    raise SystemExit(main())
