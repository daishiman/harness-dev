from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


C09 = load_module("test_sdp_context", "resolve-project-context.py")
VALIDATOR = load_module("test_sdp_validator", "validate-system-plan.py")
HANDOFF = load_module("test_sdp_handoff_runtime", "build-system-handoff.py")
LOCK = load_module("test_sdp_lock_runtime", "manage-system-plan-lock.py")
PROMOTER = load_module("test_sdp_promoter", "promote-system-plan.py")
READINESS = load_module("test_sdp_readiness_runtime", "check-implementation-readiness.py")
DEV_GRAPH_SCRIPTS = PLUGIN.parent / "dev-graph" / "scripts"
sys.path.insert(0, str(DEV_GRAPH_SCRIPTS))
_dev_spec = importlib.util.spec_from_file_location(
    "test_sdp_dev_graph_registration", DEV_GRAPH_SCRIPTS / "register-package.py"
)
DEV_REGISTER = importlib.util.module_from_spec(_dev_spec)
sys.modules[_dev_spec.name] = DEV_REGISTER
_dev_spec.loader.exec_module(DEV_REGISTER)  # type: ignore[union-attr]


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def task(index: int, package_id: str, parent: str) -> dict:
    phase = f"P{index:02d}"
    task_id = f"SYS-{phase}"
    previous = [f"SYS-P{index - 1:02d}"] if index > 1 else []
    return {
        "id": task_id, "feature_package_id": package_id, "parent_feature": parent,
        "title": f"Execute {phase}", "owners": ["team"], "tags": [phase.lower()],
        "related_nodes": [], "workstream_kind": "quality", "build_target_kind": "application-code",
        "phase_ref": phase, "depends_on": previous, "write_scope": [f"src/{phase.lower()}"],
        "deploy_unit": "application", "source_lineage": ["system-spec/index.md"],
        "classification": {"confidence": 1, "reason": "phase mapping", "candidates": [
            {"artifact_kind": "task", "confidence": 1, "candidate_path": f"tasks/{parent}/{task_id}.md"}
        ]},
        "tracker_binding_intent": "none",
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "pr_completion_policy": "linked_pr_merged_all",
        "branch_policy": {"strategy": "one-task-one-branch", "worktree_lease_required": True,
                          "completion_projection": "default-branch-reconciliation",
                          "assignment_owner": "dev-graph-scheduler"},
        "acceptance": [f"{phase} is complete"], "verification": [f"verify {phase}"],
        "rollback": f"revert {phase}",
        "implementation_readiness": {"status": "complete", "missing_sections": [],
                                     "checked_at": "2026-07-13T00:00:00Z"},
        "graph_node_registration": {"graph_node_id": task_id, "file_path": f"tasks/{parent}/{task_id}.md",
                                    "parent_feature": parent, "feature_package_id": package_id,
                                    "phase_ref": phase},
    }


def task_spec_text(phase: str) -> str:
    sections = {
        "Machine-readable registration fields": f"- phase_ref: {phase}\n- feature_package_id: feature-package/feat",
        "目的": f"Complete the single responsibility assigned to {phase}.",
        "背景": "The confirmed system specification requires this phase output.",
        "前提条件": "- Required node: FEATURE-1\n- Entry gate: dependencies complete",
        "Workstream applicability": "- Quality: applicable; verify the phase\n- Frontend: N/A: no UI change",
        "Architecture and deploy unit": "- Architecture decisions: FEATURE-1\n- Deploy unit: application",
        "成果物": f"- Produced artifacts: evidence/{phase}.json\n- Write scope: src/{phase.lower()}",
        "Tracker publication and completion": "- Tracker binding intent: none\n- Publication mode: local_only",
        "Branch and worktree execution": "- Branch: assigned by dev-graph\n- Worktree lease: required",
        "スコープ外": "- Changes outside the declared write scope.",
        "Verification and evidence": f"- Automated commands: verify {phase}\n- Required evidence: evidence/{phase}.json",
        "Rollout and rollback": f"- Rollout: publish {phase}\n- Rollback: revert {phase}",
        "Handoff": "- Executor: system build route\n- Ready when: all gates pass",
        "参照情報": "- System specification: system-spec/index.md\n- Feature: FEATURE-1",
    }
    body = [f"# {phase}"]
    for heading in VALIDATOR.REQUIRED_TASK_SPEC_SECTIONS:
        body.extend(("", f"## {heading}", "", sections[heading]))
    return "\n".join(body) + "\n"


def make_fixture(
    root: Path,
    repository_id: str,
    relative: str = ".dev-graph/staging/run-1",
    *,
    include_handoff: bool = True,
) -> tuple[Path, str]:
    staging = root / relative
    package_id, parent = "feature-package/feat", "FEATURE-1"
    tasks = [task(i, package_id, parent) for i in range(1, 14)]
    node_ids = [item["id"] for item in tasks]
    (root / "features").mkdir(parents=True, exist_ok=True)
    feature_context = {
        "graph_node_id": parent, "artifact_kind": "feature", "purpose": "purpose", "goal": "goal",
        "scope_in": ["in"], "scope_out": ["out"], "acceptance": ["accepted"],
        "architecture_refs": ["architecture/graph.json"], "updated_at": "2026-07-13T00:00:00Z",
    }
    dump(root / "architecture/graph.json", {"nodes": [{"id": "A1"}]})
    dump(root / "features/feature.json", feature_context)
    source_feature_digest = "sha256:" + hashlib.sha256(
        (root / "features/feature.json").read_bytes()
    ).hexdigest()
    package = {
        "schema_version": "1.0.0", "feature_package_id": package_id, "parent_feature": parent,
        "source_feature_digest": source_feature_digest, "task_count": 13,
        "phase_refs": VALIDATOR.PHASES, "task_spec_paths": VALIDATOR.TASK_PATHS,
        "task_node_ids": node_ids,
    }
    dump(root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME, {
        "repository_id": repository_id,
        "run_id": "run-1",
        "session_owner": "session-1",
        "feature_id": parent,
        "feature_digest": source_feature_digest,
        "acquired_at": "2026-01-01T00:00:00Z",
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
    })
    inventory = {
        "schema_version": "1.0.0", "feature_package_id": package_id, "parent_feature": parent,
        "repo_context": {"config_path": ".dev-graph/config.json", "repo_identity": repository_id,
                         "root_resolution_source": "explicit-cli"},
        "source_lineage": {"source_plugin": "system-spec-harness", "source_version": "0.1.0",
                           "compile_entrypoint": "run-system-spec-compile",
                           "completeness_entrypoint": "assign-system-spec-completeness-evaluator",
                           "source_paths": ["system-spec/index.md"], "confirmed": True},
        "tasks": tasks,
    }
    graph = {"schema_version": "1.0.0", "nodes": [
        {"id": item["id"], "phase_ref": item["phase_ref"], "feature_package_id": package_id,
         "parent_feature": parent, "depends_on": item["depends_on"]} for item in tasks
    ]}
    dump(staging / "feature-package.json", package)
    dump(staging / "workstream-inventory.json", inventory)
    dump(staging / "task-graph.json", graph)
    for rel, phase in zip(VALIDATOR.TASK_PATHS, VALIDATOR.PHASES):
        path = staging / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(task_spec_text(phase), encoding="utf-8")
    rels = ["feature-package.json", "workstream-inventory.json", "task-graph.json", *VALIDATOR.TASK_PATHS]
    files = {rel: hashlib.sha256((staging / rel).read_bytes()).hexdigest() for rel in rels}
    digest = VALIDATOR.canonical_digest(staging, rels)
    dump(staging / "staging-manifest.json", {"files": files, "canonical_digest": digest})
    if include_handoff:
        package, inventory, graph, contents, manifest, source_manifest = HANDOFF._validate_sources(
            repo_root=root.resolve(), staging=staging.resolve(), repository_id=repository_id, validator=VALIDATOR,
        )
        handoff = HANDOFF._build_handoff(package, inventory, graph, contents, source_manifest)
        HANDOFF._schema_check(handoff, VALIDATOR)
        digest = HANDOFF._commit(staging, manifest, handoff, contents)["canonical_digest"]
    return staging, digest


def refresh_manifest(staging: Path) -> str:
    manifest_path = staging / "staging-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rels = sorted(manifest["files"])
    manifest["files"] = {rel: hashlib.sha256((staging / rel).read_bytes()).hexdigest() for rel in rels}
    manifest["canonical_digest"] = VALIDATOR.canonical_digest(staging, rels)
    dump(manifest_path, manifest)
    return manifest["canonical_digest"]


def valid_findings(staging: Path, digest: str) -> dict:
    manifest = json.loads((staging / "staging-manifest.json").read_text(encoding="utf-8"))
    evaluated_paths = sorted(set(manifest["files"]) | {"staging-manifest.json"})
    return {
        "plan_dir": ".dev-graph/staging/run-1",
        "evaluator": {"name": "assign-system-dev-plan-evaluator", "version": "1.0.0", "context": "fork"},
        "evaluated_digest": digest,
        "verdict": "PASS",
        "conditions": {
            key: {"id": key, "status": "PASS", "summary": "verified", "evidence": ["gate:deterministic-validation"]}
            for key in ("C1", "C2", "C3", "C4")
        },
        "gate_results": [{
            "id": "deterministic-validation", "name": "validate-system-plan",
            "command": ["python3", "validate-system-plan.py", "--repo-root", "/caller", "--staging", ".dev-graph/staging/run-1"],
            "exit_code": 0,
            "conditions": ["C1", "C2", "C3", "C4"],
            "stdout": json.dumps({"status": "pass", "validated_digest": digest, "violations": []}),
        }],
        "evaluated_inputs": [
            {"path": rel, "sha256": hashlib.sha256((staging / rel).read_bytes()).hexdigest()}
            for rel in evaluated_paths
        ],
        "staleness_rule": "C11 recomputes every evaluated input SHA against current staging bytes",
        "findings": [],
    }


def write_readiness_sources(root: Path) -> None:
    (root / "system-spec/index.md").write_text("# Confirmed\n\nReady.\n", encoding="utf-8")
    (root / "system-spec/00-requirements-definition.md").write_text(
        "# Requirements\n\nReady.\n", encoding="utf-8"
    )
    dump(root / "architecture/graph.json", {"nodes": [{"id": "A1"}]})
    aspects = {
        "foundation_trace": ("assign-system-spec-completeness-evaluator", "C05"),
        "decision_guidance": ("assign-system-spec-completeness-evaluator", "C05"),
        "matrix_coverage": ("system-spec-matrix-auditor", "C07"),
        "design_knowledge_reflection": ("assign-system-spec-completeness-evaluator", "C05"),
        "doc_freshness": ("system-spec-doc-freshness-auditor", "C08"),
        "prompt_quality": ("assign-system-spec-completeness-evaluator", "C05"),
    }
    dump(root / "system-spec/completeness-findings.json", {
        "evaluator": {"name": "assign-system-spec-completeness-evaluator", "version": "0.1.0", "context": "fork"},
        "verdict": "PASS",
        "aspects": {key: {"verdict": "PASS", "auditor": owner, "component": component,
                           "summary": "independently verified"}
                    for key, (owner, component) in aspects.items()},
        "findings": [{"severity": "info", "bucket": "coverage", "observation": "all aspects checked"}],
        "gaps": [],
    })


def valid_readiness(root: Path, repository_id: str) -> dict:
    write_readiness_sources(root)
    context = C09.build_context(
        ["--repo-root", str(root)], {"CLAUDE_PROJECT_DIR": str(root)}
    )
    report = READINESS.build_report(
        context, "system-spec", "architecture", "system-spec/completeness-findings.json"
    )
    assert report["status"] == "complete", report
    assert report["repository_id"] == repository_id
    return report


def make_repo(root: Path) -> str:
    root = root.resolve()
    repository_id, _ = C09.derive_repository_id(root)
    config = json.loads((PLUGIN / "assets" / "default-project-config.json").read_text(encoding="utf-8"))
    config["repository_id"] = repository_id
    config.pop("repository_id_note", None)
    dump(root / ".dev-graph" / "config.json", config)
    for rel in (".dev-graph/staging", ".dev-graph/plans", ".dev-graph/state", ".dev-graph/cache",
                ".dev-graph/locks", "issues", "tasks", "specs", "architecture", "docs", "system-spec"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    return repository_id


class RemoteParsingTests(unittest.TestCase):
    def test_github_host_must_match_exactly(self):
        self.assertEqual(C09._parse_github_remote("git@github.com:owner/repo.git"), "github:owner/repo")
        self.assertEqual(C09._parse_github_remote("https://github.com/owner/repo.git"), "github:owner/repo")
        self.assertIsNone(C09._parse_github_remote("https://evilgithub.com/owner/repo.git"))
        self.assertIsNone(C09._parse_github_remote("ssh://git@github.com.evil/owner/repo.git"))


class SchemaValidationTests(unittest.TestCase):
    def test_required_const_pattern_and_additional_properties(self):
        schema = VALIDATOR._load_schema("feature-execution-package.schema.json")
        valid = {"schema_version": "1.0.0", "feature_package_id": "feature-package/f",
                 "parent_feature": "F", "source_feature_digest": "sha256:" + "a" * 64,
                 "task_count": 13, "phase_refs": VALIDATOR.PHASES,
                 "task_spec_paths": VALIDATOR.TASK_PATHS,
                 "task_node_ids": [f"SYS-P{i:02d}" for i in range(1, 14)]}
        self.assertEqual(VALIDATOR.schema_violations(valid, schema), [])
        for mutation in (
            lambda x: x.pop("source_feature_digest"),
            lambda x: x.update(task_count=12),
            lambda x: x.update(feature_package_id="bad"),
            lambda x: x.update(unexpected=True),
        ):
            candidate = json.loads(json.dumps(valid)); mutation(candidate)
            self.assertTrue(VALIDATOR.schema_violations(candidate, schema), candidate)

    def test_inventory_task_required_field_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, _ = make_fixture(root, repository_id)
            inventory_path = staging / "workstream-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["tasks"][0].pop("acceptance")
            inventory["tasks"][1]["unexpected"] = True
            dump(inventory_path, inventory)
            manifest_path = staging / "staging-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["workstream-inventory.json"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
            manifest["canonical_digest"] = VALIDATOR.canonical_digest(staging, sorted(manifest["files"]))
            dump(manifest_path, manifest)
            report = VALIDATOR.validate(staging, repository_id)
            self.assertEqual(report["status"], "fail")
            self.assertIn("inventory-schema", {item["code"] for item in report["violations"]})

    def test_complete_fixture_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, digest = make_fixture(root, repository_id)
            report = VALIDATOR.validate(staging, repository_id)
            self.assertEqual(report["status"], "pass", report)
            self.assertEqual(report["validated_digest"], digest)

    def test_handoff_identity_and_receipt_owner_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, _ = make_fixture(root, repository_id)
            handoff_path = staging / VALIDATOR.HANDOFF_PATH
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            handoff["identity"]["repository_id"] = "github:other/repository"
            handoff["registration_request"]["registration_receipt"]["owner"] = "system-dev-planner/C11"
            dump(handoff_path, handoff)
            refresh_manifest(staging)
            report = VALIDATOR.validate(staging, repository_id)
            codes = {item["code"] for item in report["violations"]}
            self.assertEqual(report["status"], "fail")
            self.assertIn("handoff-schema", codes)
            self.assertIn("handoff-identity", codes)

    def test_thin_duplicate_empty_and_placeholder_task_specs_fail(self):
        cases = {
            "thin": "# P01\n\nExecutable task specification.\n",
            "duplicate": task_spec_text("P01") + "\n## Handoff\n\nSecond handoff.\n",
            "empty": task_spec_text("P01").replace(
                "## Handoff\n\n- Executor: system build route\n- Ready when: all gates pass",
                "## Handoff\n",
            ),
            "placeholder": task_spec_text("P01").replace("Complete the single responsibility assigned to P01.", "TODO"),
        }
        expected_codes = {
            "thin": "task-spec-section-missing", "duplicate": "task-spec-section-duplicate",
            "empty": "task-spec-section-empty", "placeholder": "placeholder",
        }
        for name, text in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = Path(td); repository_id = make_repo(root)
                staging, _ = make_fixture(root, repository_id)
                (staging / VALIDATOR.TASK_PATHS[0]).write_text(text, encoding="utf-8")
                refresh_manifest(staging)
                report = VALIDATOR.validate(staging, repository_id)
                self.assertEqual(report["status"], "fail")
                self.assertIn(expected_codes[name], {item["code"] for item in report["violations"]})

    def test_registration_path_traversal_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, _ = make_fixture(root, repository_id)
            inventory_path = staging / "workstream-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["tasks"][0]["graph_node_registration"]["file_path"] = "tasks/../escape.md"
            dump(inventory_path, inventory)
            refresh_manifest(staging)
            report = VALIDATOR.validate(staging, repository_id)
            self.assertEqual(report["status"], "fail")
            self.assertIn("registration-file-path", {item["code"] for item in report["violations"]})


class PromotionTests(unittest.TestCase):
    def test_promoter_requires_declared_handoff_receipt_owners(self):
        valid = {
            "registration_request": {
                "path": "dev-graph-registration.json",
                "owner": "system-dev-planner/C11",
                "consumer": "dev-graph/C02",
                "status": "deferred-until-promotion",
                "promotion_receipt": {
                    "path": "atomic-promotion-receipt.json", "owner": "system-dev-planner/C11",
                    "status": "not-emitted", "produced_by_this_component": False,
                },
                "registration_receipt": {
                    "path": "dev-graph-registration-receipt.json", "owner": "dev-graph/C02",
                    "status": "not-emitted", "produced_by_this_component": False,
                },
            }
        }
        PROMOTER._validate_handoff_boundary(valid)
        for path, value in (
            (("owner",), "other"),
            (("promotion_receipt", "produced_by_this_component"), True),
            (("registration_receipt", "owner"), "system-dev-planner/C11"),
        ):
            candidate = json.loads(json.dumps(valid))
            target = candidate["registration_request"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                PROMOTER._validate_handoff_boundary(candidate)

    def test_initial_promotion_requires_exact_active_c13_lock(self):
        for case in ("absent", "wrong-owner", "expired"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as td:
                root = Path(td); repository_id = make_repo(root)
                staging, digest = make_fixture(root, repository_id)
                dump(root / ".dev-graph/state/findings.json", valid_findings(staging, digest))
                dump(root / ".dev-graph/state/readiness.json", valid_readiness(root, repository_id))
                dump(root / ".dev-graph/state/validation.json", {"status": "pass", "validated_digest": digest})
                lock_path = root / LOCK.LOCK_ROOT_REL / LOCK.LOCK_NAME
                if case == "absent":
                    lock_path.unlink()
                else:
                    lock = json.loads(lock_path.read_text(encoding="utf-8"))
                    if case == "wrong-owner":
                        lock["session_owner"] = "another-session"
                    else:
                        lock["heartbeat_at"] = "2025-01-01T00:00:00Z"
                        lock["expires_at"] = "2025-01-01T00:00:01Z"
                    dump(lock_path, lock)
                args = [
                    "--repo-root", str(root), "--feature-id", "FEATURE-1",
                    "--feature-context", "features/feature.json",
                    "--run-id", "run-1", "--session-owner", "session-1",
                    "--staging", ".dev-graph/staging/run-1",
                    "--findings", ".dev-graph/state/findings.json",
                    "--readiness", ".dev-graph/state/readiness.json",
                    "--validation", ".dev-graph/state/validation.json",
                ]
                env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
                with mock.patch.dict(os.environ, env, clear=True), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(PROMOTER.main(args), 2)
                self.assertTrue(staging.is_dir())
                self.assertFalse((root / ".dev-graph/plans/feature-package-feat").exists())
                self.assertFalse((root / ".dev-graph/state/promotion-intents").exists())

    def test_registration_node_transformation_rejects_contract_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, digest = make_fixture(root, repository_id)
            package = json.loads((staging / "feature-package.json").read_text(encoding="utf-8"))
            inventory = json.loads((staging / "workstream-inventory.json").read_text(encoding="utf-8"))
            feature_context = C09.build_context(
                ["--repo-root", str(root), "--feature-id", "FEATURE-1",
                 "--feature-context", "features/feature.json"],
                {"CLAUDE_PROJECT_DIR": str(root)},
            )
            PROMOTER._validate_feature_pin(package, feature_context)
            wrong_feature_pin = dict(package, source_feature_digest="sha256:" + "f" * 64)
            with self.assertRaises(ValueError):
                PROMOTER._validate_feature_pin(wrong_feature_pin, feature_context)
            kwargs = {
                "inventory": inventory, "package": package,
                "destination_rel": ".dev-graph/plans/feature-package-feat",
                "digest": digest,
                "findings_rel": ".dev-graph/plans/feature-package-feat/plan-findings.json",
                "promoted_at": "2026-07-13T00:00:00Z",
            }
            nodes = PROMOTER._registration_nodes(**kwargs)
            self.assertEqual(len(nodes), 13)
            for field, value in (
                ("graph_node_id", "OTHER"), ("file_path", None),
                ("file_path", "tasks/../escape.md"), ("parent_feature", "OTHER"),
            ):
                candidate = json.loads(json.dumps(inventory))
                candidate["tasks"][0]["graph_node_registration"][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    PROMOTER._registration_nodes(**dict(kwargs, inventory=candidate))

            registration = {
                "schema_version": "1.0.0", "source_digest": digest,
                "promotion_receipt": ".dev-graph/plans/feature-package-feat/atomic-promotion-receipt.json",
                "feature_package_id": package["feature_package_id"], "parent_feature": package["parent_feature"],
                "expected_count": 13, "phase_refs": VALIDATOR.PHASES,
                "binding_intents": {node["graph_node_id"]: "none" for node in nodes}, "nodes": nodes,
            }
            receipt = {
                "schema_version": "1.0.0", "status": "promoted", "promoted_at": "2026-07-13T00:00:00Z",
                "repo_identity": repository_id, "staging_digest": digest, "evaluated_digest": digest,
                "published_digest": digest, "implementation_readiness": "complete",
                "quality_conditions": {key: "PASS" for key in (
                    "no_contradiction", "no_missing", "consistent", "dependency_integrity"
                )},
                "promotion_method": "same-filesystem-atomic-rename",
                "registration_manifest": registration["promotion_receipt"].replace(
                    "atomic-promotion-receipt.json", "dev-graph-registration.json"
                ),
            }
            PROMOTER._validate_generated_artifacts(registration, receipt, VALIDATOR)
            for field, value in (
                ("unexpected", True), ("artifact_kind", "feature"), ("status", "draft"),
                ("tracker_binding", "none"), ("implementation_readiness", {"status": "incomplete"}),
            ):
                candidate = json.loads(json.dumps(registration))
                candidate["nodes"][0][field] = value
                with self.subTest(node_field=field), self.assertRaises(ValueError):
                    PROMOTER._validate_generated_artifacts(candidate, receipt, VALIDATOR)

    def test_post_rename_failure_recovers_idempotently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            _, digest = make_fixture(root, repository_id)
            dump(root / ".dev-graph/state/findings.json", valid_findings(root / ".dev-graph/staging/run-1", digest))
            dump(root / ".dev-graph/state/readiness.json", valid_readiness(root, repository_id))
            dump(root / ".dev-graph/state/validation.json", {"status": "pass", "validated_digest": digest})
            args = ["--repo-root", str(root), "--feature-id", "FEATURE-1", "--feature-context", "features/feature.json",
                    "--run-id", "run-1", "--session-owner", "session-1",
                    "--staging", ".dev-graph/staging/run-1",
                    "--findings", ".dev-graph/state/findings.json",
                    "--readiness", ".dev-graph/state/readiness.json",
                    "--validation", ".dev-graph/state/validation.json"]
            original = PROMOTER._atomic_json
            failed = False

            def fail_current(path: Path, value: dict):
                nonlocal failed
                if path.name == "current.json" and not failed:
                    failed = True
                    raise OSError("simulated current pointer failure")
                original(path, value)

            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(PROMOTER, "_atomic_json", fail_current), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                self.assertEqual(PROMOTER.main(args), 1, stderr.getvalue())
            destination = root / ".dev-graph/plans/feature-package-feat"
            self.assertTrue((destination / "atomic-promotion-receipt.json").is_file())
            self.assertTrue((destination / "dev-graph-registration.json").is_file())
            self.assertTrue((destination / "plan-findings.json").is_file())
            registration = json.loads((destination / "dev-graph-registration.json").read_text(encoding="utf-8"))
            node_schema = json.loads(
                (PLUGIN.parent / "dev-graph/schemas/graph-node.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(registration["nodes"]), 13)
            for index, node in enumerate(registration["nodes"]):
                DEV_REGISTER._validate_schema(node, node_schema, node_schema, f"nodes[{index}]")
                self.assertEqual(node["artifact_kind"], "task")
                self.assertEqual(node["source_lineage"]["source_digest"], digest.removeprefix("sha256:"))
            self.assertFalse((root / ".dev-graph/state/current.json").exists())
            task_spec = destination / VALIDATOR.TASK_PATHS[0]
            original_task_spec = task_spec.read_bytes()
            task_spec.write_text("# TAMPERED\n", encoding="utf-8")
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(PROMOTER.main(args), 2)
            self.assertFalse((root / ".dev-graph/state/current.json").exists())
            task_spec.write_bytes(original_task_spec)
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(PROMOTER.main(args), 0)
                self.assertEqual(PROMOTER.main(args), 0)
            current = json.loads((root / ".dev-graph/state/current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["published_digest"], digest)

    def test_invalid_findings_and_readiness_fail_before_any_promotion_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, digest = make_fixture(root, repository_id)
            findings_path = root / ".dev-graph/state/findings.json"
            readiness_path = root / ".dev-graph/state/readiness.json"
            validation_path = root / ".dev-graph/state/validation.json"
            dump(validation_path, {"status": "pass", "validated_digest": digest})
            args = ["--repo-root", str(root), "--feature-id", "FEATURE-1", "--feature-context", "features/feature.json",
                    "--run-id", "run-1", "--session-owner", "session-1",
                    "--staging", ".dev-graph/staging/run-1",
                    "--findings", ".dev-graph/state/findings.json",
                    "--readiness", ".dev-graph/state/readiness.json",
                    "--validation", ".dev-graph/state/validation.json"]
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            invalid_inputs = [
                ({"verdict": "PASS", "evaluated_digest": digest}, valid_readiness(root, repository_id)),
                (valid_findings(staging, digest), {"status": "complete"}),
            ]
            for findings, readiness in invalid_inputs:
                with self.subTest(findings=findings, readiness=readiness):
                    dump(findings_path, findings); dump(readiness_path, readiness)
                    with mock.patch.dict(os.environ, env, clear=True), \
                            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(PROMOTER.main(args), 2)
                    self.assertTrue(staging.is_dir())
                    self.assertFalse((root / ".dev-graph/plans/feature-package-feat").exists())
                    self.assertFalse((root / ".dev-graph/state/promotion-intents").exists())

    def test_nonzero_gate_and_high_finding_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, digest = make_fixture(root, repository_id)
            findings_path = root / ".dev-graph/state/findings.json"
            dump(root / ".dev-graph/state/readiness.json", valid_readiness(root, repository_id))
            dump(root / ".dev-graph/state/validation.json", {"status": "pass", "validated_digest": digest})
            args = ["--repo-root", str(root), "--feature-id", "FEATURE-1", "--feature-context", "features/feature.json",
                    "--run-id", "run-1", "--session-owner", "session-1",
                    "--staging", ".dev-graph/staging/run-1",
                    "--findings", ".dev-graph/state/findings.json",
                    "--readiness", ".dev-graph/state/readiness.json",
                    "--validation", ".dev-graph/state/validation.json"]
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            candidates = []
            failed_gate = valid_findings(staging, digest); failed_gate["gate_results"][0]["exit_code"] = 1
            candidates.append(failed_gate)
            high = valid_findings(staging, digest); high["findings"] = [
                {"severity": "high", "bucket": "contract", "observation": "unresolved"}
            ]
            candidates.append(high)
            fake_gate = valid_findings(staging, digest)
            fake_gate["gate_results"][0]["command"] = ["true"]
            candidates.append(fake_gate)
            fake_evidence = valid_findings(staging, digest)
            for condition in fake_evidence["conditions"].values():
                condition["evidence"] = ["self-asserted"]
            candidates.append(fake_evidence)
            for candidate in candidates:
                dump(findings_path, candidate)
                with mock.patch.dict(os.environ, env, clear=True), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(PROMOTER.main(args), 2)
                self.assertTrue(staging.is_dir())
                self.assertFalse((root / ".dev-graph/state/promotion-intents").exists())

    def test_evidence_less_findings_and_stale_readiness_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); repository_id = make_repo(root)
            staging, digest = make_fixture(root, repository_id)
            findings_path = root / ".dev-graph/state/findings.json"
            readiness_path = root / ".dev-graph/state/readiness.json"
            validation_path = root / ".dev-graph/state/validation.json"
            dump(validation_path, {"status": "pass", "validated_digest": digest})
            args = ["--repo-root", str(root), "--feature-id", "FEATURE-1", "--feature-context", "features/feature.json",
                    "--run-id", "run-1", "--session-owner", "session-1",
                    "--staging", ".dev-graph/staging/run-1",
                    "--findings", ".dev-graph/state/findings.json",
                    "--readiness", ".dev-graph/state/readiness.json",
                    "--validation", ".dev-graph/state/validation.json"]
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}

            malformed = valid_findings(staging, digest)
            malformed["conditions"]["C1"].update(id="wrong-id", summary="", evidence=[])
            malformed["gate_results"][0]["conditions"] = ["C1"]
            dump(findings_path, malformed)
            dump(readiness_path, valid_readiness(root, repository_id))
            with mock.patch.dict(os.environ, env, clear=True), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(PROMOTER.main(args), 2)

            dump(findings_path, valid_findings(staging, digest))
            readiness = valid_readiness(root, repository_id)
            dump(readiness_path, readiness)
            (root / "system-spec/index.md").write_text("# Changed\n\nNew bytes.\n", encoding="utf-8")
            with mock.patch.dict(os.environ, env, clear=True), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(PROMOTER.main(args), 2)
            self.assertTrue(staging.is_dir())
            self.assertFalse((root / ".dev-graph/state/promotion-intents").exists())


if __name__ == "__main__":
    unittest.main()
