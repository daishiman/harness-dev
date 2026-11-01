#!/usr/bin/env python3
# /// script
# name: validate-system-plan
# purpose: staged feature package/exact 13 task specs/inventory/DAG を決定論検証する。
# inputs: argv --repo-root/--staging/--config
# outputs: stdout validation report JSON
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [resolve-project-context.py, validate-task-spec-contract.py, validate-json-schema-subset.py, validate-qa-semantic-coverage.py, ../assets/validation-contract-baseline.json]
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
STAGING_RUNTIME_REF = re.compile(r"(?:^|[^A-Za-z0-9_.-])\.dev-graph/staging(?:/|\b)")
SCHEMAS = HERE.parent / "schemas"

def _load_sibling(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _resolver():
    return _load_sibling("resolve-project-context.py", "sdp_context")


# 契約 version の正本は validate-task-spec-contract.py に置く (責務分離)。ここでは module
# 属性として再公開し、promoter/テストが validator 経由で契約定数を参照する既存の形を保つ。
CONTRACTS = _load_sibling("validate-task-spec-contract.py", "sdp_task_spec_contract")
CONTRACT_BASELINE_ASSET = CONTRACTS.CONTRACT_BASELINE_ASSET
TASK_SPEC_HEADING = CONTRACTS.TASK_SPEC_HEADING
P01_ENTRY_GATE_MARKER = CONTRACTS.P01_ENTRY_GATE_MARKER
METHODOLOGY_MARKER = CONTRACTS.METHODOLOGY_MARKER
GOAL_SEEK_PASS_MARKER = CONTRACTS.GOAL_SEEK_PASS_MARKER
P13_WRITEBACK_MARKER = CONTRACTS.P13_WRITEBACK_MARKER
GOAL_SEEK_SECTION = CONTRACTS.GOAL_SEEK_SECTION
REQUIRED_TASK_SPEC_SECTIONS = CONTRACTS.REQUIRED_TASK_SPEC_SECTIONS
CONTRACT_VERSION_LATEST = CONTRACTS.CONTRACT_VERSION_LATEST
CONTRACT_VERSIONS = CONTRACTS.CONTRACT_VERSIONS
TEST_STRATEGY_CONTRACT_FROM = CONTRACTS.TEST_STRATEGY_CONTRACT_FROM
TEST_STRATEGY_SECTION = CONTRACTS.TEST_STRATEGY_SECTION
TEST_STRATEGY_ITEMS = CONTRACTS.TEST_STRATEGY_ITEMS
TEST_STRATEGY_SCHEMA = CONTRACTS.TEST_STRATEGY_SCHEMA
TEST_STRATEGY_PLACEMENT = CONTRACTS.TEST_STRATEGY_PLACEMENT
RERUN_COMMAND_CONTRACT_FROM = CONTRACTS.RERUN_COMMAND_CONTRACT_FROM
RERUN_SCRIPT = CONTRACTS.RERUN_SCRIPT
_task_spec_sections = CONTRACTS._task_spec_sections
parse_test_strategy = CONTRACTS.parse_test_strategy
derive_required_layers = CONTRACTS.derive_required_layers
load_contract_baseline = CONTRACTS.load_contract_baseline
resolve_contract_version = CONTRACTS.resolve_contract_version
task_spec_violations = CONTRACTS.task_spec_violations
rerun_command_violations = CONTRACTS.rerun_command_violations

# JSON Schema サブセット検証器の正本は validate-json-schema-subset.py (責務分離)。C14 が
# 同等実装を別に持つ理由は当該 module の docstring を参照する。
SCHEMA_SUBSET = _load_sibling("validate-json-schema-subset.py", "sdp_json_schema_subset")
_type_matches = SCHEMA_SUBSET._type_matches
_resolve_local_ref = SCHEMA_SUBSET._resolve_local_ref
schema_violations = SCHEMA_SUBSET.schema_violations

# QA semantic coverage は契約 version 解決と異なる責務なので専用 module へ分離する。
# 公開定数と関数は既存テスト/利用者との互換性のため本 module から再公開する。
QA_COVERAGE = _load_sibling(
    "validate-qa-semantic-coverage.py",
    "sdp_qa_semantic_coverage",
)
QA_REF_PATTERN = QA_COVERAGE.QA_REF_PATTERN
FRONTMATTER_TAGS = QA_COVERAGE.FRONTMATTER_TAGS
GOAL_SPEC_COVERAGE_FIELDS = QA_COVERAGE.GOAL_SPEC_COVERAGE_FIELDS
QA_REQUIREMENT_HEADING = QA_COVERAGE.QA_REQUIREMENT_HEADING
SEMANTIC_COVERAGE_CONSTRAINT_ID = QA_COVERAGE.SEMANTIC_COVERAGE_CONSTRAINT_ID


def qa_semantic_violations(
    staging: Path,
    repo_root: Path,
    parent: str,
) -> list[tuple[str, str, str]]:
    return QA_COVERAGE.qa_semantic_violations(
        staging,
        repo_root,
        parent,
        TASK_PATHS,
    )


def canonical_digest(root: Path, relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(relative_paths):
        path = root / rel
        digest.update(rel.encode()); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _load_schema(name: str) -> dict:
    value = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"schema must be object: {name}")
    return value


def test_strategy_violations(text: str, *, enforced: bool) -> list[tuple[str, str]]:
    """テスト戦略 section の構造・内容・層別充足を検証する。"""
    value, errors = parse_test_strategy(text)
    if value is None:
        if not errors:
            return [("task-spec-test-strategy-missing", TEST_STRATEGY_SECTION)] if enforced else []
        return errors
    if {key for _, key in TEST_STRATEGY_ITEMS} <= set(value):
        for detail in schema_violations(value, _load_schema(TEST_STRATEGY_SCHEMA)):
            errors.append(("task-spec-test-strategy-content", detail))
        policies = value["layer_policies"]
        for layer in derive_required_layers(text):
            for marker in CONTRACTS.LAYER_MARKERS[layer]:
                if marker not in policies:
                    errors.append(("task-spec-test-strategy-layer", f"{layer}: missing marker `{marker}`"))
    return errors


def validate(
    staging: Path,
    repository_id: str,
    baseline: dict[str, str] | None = None,
    repo_root: Path | None = None,
) -> dict:
    violations: list[dict] = []
    resolved_baseline = load_contract_baseline() if baseline is None else baseline
    def fail(code: str, path: str, detail: str) -> None:
        violations.append({"code": code, "path": path, "detail": detail})
    def plain_file(rel: str) -> bool:
        """副作用なしで symlink 成分を排した実在判定を返す (契約 version 解決の前段用)。"""
        cursor = staging
        for part in Path(rel).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return False
        return (staging / rel).is_file()
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

    required_digest_files = [*BASE_DIGEST_FILES, HANDOFF_PATH]
    # 免除判定は manifest の申告値ではなく実体から再計算した digest で行う。
    # staging-manifest.json 自身は digest 対象集合の外にあり書き換え可能なため。
    actual_digest = (
        canonical_digest(staging, required_digest_files)
        if all(plain_file(rel) for rel in required_digest_files) else None
    )
    contract_version = resolve_contract_version(actual_digest, resolved_baseline)
    contract = CONTRACT_VERSIONS[contract_version]

    package = load("feature-package.json")
    inventory = load("workstream-inventory.json")
    graph = load("task-graph.json")
    handoff = load(HANDOFF_PATH)
    manifest = load("staging-manifest.json")
    if not all(isinstance(x, dict) for x in (package, inventory, graph, handoff, manifest)):
        return {"status": "fail", "violations": violations, "validated_digest": None,
                "contract_version": contract_version,
                "contract_baseline_exemption": contract_version != CONTRACT_VERSION_LATEST}
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
    expected_p01_entry_gate = {
        "selector": "parent_feature.depends_on",
        "operator": "all",
        "required_statuses": ["done", "closed"],
    }
    if inventory.get("p01_entry_gate") != expected_p01_entry_gate:
        fail(
            "p01-entry-gate",
            "workstream-inventory.json#p01_entry_gate",
            "canonical parent feature dependencies must all be done|closed",
        )
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
    if handoff.get("p01_entry_gate") != expected_p01_entry_gate:
        fail(
            "p01-entry-gate",
            f"{HANDOFF_PATH}#p01_entry_gate",
            "handoff must preserve the inventory P01 entry gate",
        )
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
            if STAGING_RUNTIME_REF.search(text):
                fail(
                    "staging-runtime-reference",
                    rel,
                    "task specs must use package-relative or canonical published paths; "
                    ".dev-graph/staging is removed by atomic promotion",
                )
            if rel == TASK_PATHS[0] and P01_ENTRY_GATE_MARKER not in text:
                fail(
                    "p01-entry-gate",
                    rel,
                    f"P01 must declare machine-verifiable gate: {P01_ENTRY_GATE_MARKER}",
                )
            for code, section in task_spec_violations(text, contract["required_sections"]):
                fail(code, rel, section)
            for code, detail in test_strategy_violations(text, enforced=contract["test_strategy"]):
                fail(code, rel, detail)
            if contract["rerun_command"]:
                # package_id が str でない場合は schema 検査が別途落とす。ここで id 一致を
                # 主張すると誤った期待値を detail に出すので、形式検査だけへ縮退させる。
                for code, detail in rerun_command_violations(
                    text, package_id if isinstance(package_id, str) else None
                ):
                    fail(code, rel, detail)
            if contract["inner_goal_seek"] and (METHODOLOGY_MARKER not in text or GOAL_SEEK_PASS_MARKER not in text):
                fail(
                    "inner-goal-seek-contract",
                    rel,
                    "portable methodology marker and rubric verdict=PASS feedback loop are required",
                )
            if contract["p13_writeback"] and rel == TASK_PATHS[-1] and P13_WRITEBACK_MARKER not in text:
                fail(
                    "p13-spec-architecture-writeback",
                    rel,
                    "P13 must write execution results, decisions, and improvement findings back to canonical specs",
                )
    for i, task in enumerate(tasks):
        if task.get("feature_package_id") != package_id or task.get("parent_feature") != parent:
            fail("mixed-task-package", f"tasks[{i}]", "feature_package_id/parent_feature mismatch")
        if task.get("implementation_readiness", {}).get("status") != "complete":
            fail("not-ready", f"tasks[{i}]", "implementation_readiness must be complete")
        registration = task.get("graph_node_registration")
        file_path = registration.get("file_path") if isinstance(registration, dict) else None
        if (
            not isinstance(file_path, str)
            or re.fullmatch(r"tasks/[A-Za-z0-9._-]+/[^/]+\.md", file_path) is None
            or ".." in Path(file_path).parts
            or not file_path.startswith(f"tasks/{parent}/")
        ):
            fail("registration-file-path", f"tasks[{i}].graph_node_registration.file_path",
                 "tasks/<parent_feature>/<node>.md repository-relative path required "
                 "(feature 単位 namespace で並列 package 生成の衝突を防ぐ)")
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
    if (
        contract["qa_semantic_coverage"]
        and repo_root is not None
        and isinstance(parent, str)
    ):
        for code, path, detail in qa_semantic_violations(staging, repo_root, parent):
            fail(code, path, detail)
    manifest_files = manifest.get("files")
    rels: list[str] = []
    if isinstance(manifest_files, dict): rels = sorted(manifest_files)
    elif isinstance(manifest_files, list): rels = sorted(x.get("path") for x in manifest_files if isinstance(x, dict) and isinstance(x.get("path"), str))
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
    # 契約 version 台帳の `contract` と別物なので名前を分ける。同名にすると後段の
    # test_strategy_contract 出力が handoff 側を引いてしまう (実際に KeyError で顕在化した)。
    handoff_contract = manifest.get("handoff_contract") if isinstance(manifest.get("handoff_contract"), dict) else {}
    handoff_sha = hashlib.sha256((staging / HANDOFF_PATH).read_bytes()).hexdigest() if (staging / HANDOFF_PATH).is_file() else None
    if (
        handoff_contract.get("schema_version") != "1.0.0"
        or handoff_contract.get("path") != HANDOFF_PATH
        or handoff_contract.get("sha256") != handoff_sha
        or handoff_contract.get("source_canonical_digest") != base_digest
        or handoff_contract.get("manifest_is_commit_point") is not True
        or handoff_contract.get("self_reference_policy") != "handoff hash and final digest are manifest-only"
    ):
        fail("handoff-manifest-contract", "staging-manifest.json", "handoff commit-point contract mismatch")
    return {"schema_version": "1.0.0", "status": "pass" if not violations else "fail",
            "validated_digest": digest, "feature_package_id": package_id, "parent_feature": parent,
            "phase_refs": PHASES, "contract_version": contract_version,
            "contract_baseline_exemption": contract_version != CONTRACT_VERSION_LATEST,
            # 適用モードを常に出力する。silent skip を許すと「検査したのか、
            # 素通りしたのか」を証跡から区別できず、緑色が意味を失う。
            "test_strategy_contract": {
                "mode": "enforced" if contract["test_strategy"] else "legacy",
                "contract_version": contract_version,
                "enforced_from": TEST_STRATEGY_CONTRACT_FROM,
            },
            "rerun_command_contract": {
                "mode": "enforced" if contract["rerun_command"] else "legacy",
                "contract_version": contract_version,
                "enforced_from": RERUN_COMMAND_CONTRACT_FROM,
            },
            "violations": violations}


def _package_slug(package_id: str) -> str:
    """promote-system-plan.py と同一規則で feature_package_id を pointer slug へ写す。"""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", package_id).strip("-")
    if not slug:
        raise ValueError("feature_package_id does not produce a stable generation slug")
    return slug


def _current_generation(c09, repo_root: Path, context: dict, package_id: str) -> str:
    """feature 別 current pointer から現行世代の published package path を解決する。

    task spec の Automated commands へ generation id を直書きすると再計画のたびに
    stale になるため、世代非依存で再実行できる解決経路を CLI 側に持たせる。
    """
    state_rel = context["plan_roots"]["state"]["relative"]
    pointer_rel = f"{state_rel}/current/{_package_slug(package_id)}.json"
    pointer_path = c09.guard_relative_path(repo_root, pointer_rel)
    if not pointer_path.is_file():
        raise ValueError(f"current pointer が無い: {pointer_path}")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("feature_package_id") != package_id:
        raise ValueError("current pointer package identity mismatch")
    published = pointer.get("published_path")
    if not isinstance(published, str) or not published:
        raise ValueError("current pointer published_path が不正")
    return published


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate staged system plan")
    p.add_argument("--repo-root"); p.add_argument("--config", default=".dev-graph/config.json")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--staging", help="repository-relative staging generation path")
    source.add_argument("--feature-package",
                        help="feature_package_id (例: feature-package/feat-example)。"
                             "feature 別 current pointer から現行世代の published package を解決する")
    args = p.parse_args(argv); c09 = _resolver()
    try:
        context = c09.build_context(["--repo-root", args.repo_root, "--config", args.config] if args.repo_root else ["--config", args.config], dict(os.environ))
        target = args.staging or _current_generation(
            c09, Path(context["repo_root"]), context, args.feature_package
        )
        staging = Path(c09.guard_relative_path(Path(context["repo_root"]), target))
        report = validate(staging, context["repository_id"], repo_root=Path(context["repo_root"]))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 2
    except c09.UsageError as exc: print(f"[validate] {exc}", file=sys.stderr); return 1
    except (c09.PolicyError, OSError, ValueError) as exc: print(f"[validate fail-closed] {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
