from __future__ import annotations

import hashlib
import json
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "register-package.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("dev_graph_register_package", SCRIPT)
assert SPEC and SPEC.loader
RP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RP
SPEC.loader.exec_module(RP)
PHASES = [f"P{i:02d}" for i in range(1, 14)]
DIGEST = "sha256:" + "a" * 64
HEX_DIGEST = "a" * 64
NOW = "2026-07-13T00:00:00Z"


def feature_node() -> dict:
    return {
        "graph_node_id": "feature-1", "artifact_kind": "feature", "artifact_subtypes": [],
        "title": "Feature", "project_id": "project", "domain": "system", "status": "active",
        "owners": ["team"], "tags": [], "priority": None, "start_date": None, "target_date": None,
        "iteration": None, "created_at": NOW, "updated_at": NOW, "depends_on": [], "related_nodes": [],
        "resource_scope": [], "parent_feature": None, "feature_package_id": None, "phase_ref": None,
        "file_path": "features/feature-1.md", "template_id": "feature", "template_version": "1.0.0",
        "confirmation_status": "confirmed", "evaluation_status": "pass",
        "confirmation_evidence": {"evaluator": "reviewer", "evidence_ref": "evidence/feature.json", "evaluated_digest": HEX_DIGEST},
        "source_lineage": {"origin_kind": "manual", "source_plugin": None, "source_path": None,
                           "source_version": None, "source_digest": None, "imported_at": None},
        "classification_confidence": 1.0, "classification_reason": "explicit fixture", "classification_candidates": [],
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "issue_linkage": None, "tracker_binding": "none", "beads_linkage": None,
        "github_project_linkages": [], "pull_request_linkages": [], "execution_contexts": [],
        "completion_evidence": {"policy": "linked_pr_merged_all", "status": "in_progress", "source": None,
                                "completed_at": None, "reconciled_at": None, "evidence_refs": []},
        "implementation_readiness": {"status": "complete", "missing_sections": [], "checked_at": NOW},
        "purpose": "Deliver the feature", "goal": "Complete it", "scope_in": ["system"],
        "scope_out": ["unrelated"], "acceptance": ["accepted"], "architecture_refs": ["architecture/system.md"],
    }


def task_node(index: int) -> dict:
    phase = PHASES[index]
    node_id = f"task-{phase}"
    return {
        "graph_node_id": node_id, "artifact_kind": "task", "artifact_subtypes": [], "title": phase,
        "project_id": "project", "domain": "system", "status": "active", "owners": ["team"], "tags": [],
        "priority": None, "start_date": None, "target_date": None, "iteration": None,
        "created_at": NOW, "updated_at": NOW, "depends_on": [] if index == 0 else [f"task-{PHASES[index - 1]}"],
        "related_nodes": [], "resource_scope": [], "parent_feature": "feature-1",
        "feature_package_id": "feature-package/demo", "phase_ref": phase,
        "file_path": f"tasks/{phase.lower()}.md", "template_id": "task", "template_version": "1.0.0",
        "confirmation_status": "confirmed", "evaluation_status": "pass",
        "confirmation_evidence": {"evaluator": "system-dev-plan-evaluator", "evidence_ref": "plan-findings.json",
                                  "evaluated_digest": HEX_DIGEST},
        "source_lineage": {"origin_kind": "system-dev-planner", "source_plugin": "system-dev-planner",
                           "source_path": f"published/demo/task-specs/{phase}.md", "source_version": "0.1.0",
                           "source_digest": HEX_DIGEST, "imported_at": NOW},
        "classification_confidence": 1.0, "classification_reason": "exact phase", "classification_candidates": [],
        "github_publication": {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": None},
        "issue_linkage": None, "tracker_binding": "repo-config-default", "beads_linkage": None,
        "github_project_linkages": [], "pull_request_linkages": [], "execution_contexts": [],
        "completion_evidence": {"policy": "linked_pr_merged_all", "status": "in_progress", "source": None,
                                "completed_at": None, "reconciled_at": None, "evidence_refs": []},
        "implementation_readiness": {"status": "complete", "missing_sections": [], "checked_at": NOW},
    }


class RegisterPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / "feature-package.json"
        self.registration = self.root / "dev-graph-registration.json"
        self.promotion = self.root / "atomic-promotion-receipt.json"
        self.output = self.root / "graph.json"
        self.receipt = self.root / "registration-receipt.json"
        nodes = [task_node(i) for i in range(13)]
        self.write(self.package, {
            "schema_version": "1.0.0", "feature_package_id": "feature-package/demo",
            "parent_feature": "feature-1", "source_feature_digest": "sha256:" + "b" * 64,
            "task_count": 13, "phase_refs": PHASES,
            "task_spec_paths": [
                "task-specs/phase-01-requirements.md", "task-specs/phase-02-architecture.md",
                "task-specs/phase-03-design-review.md", "task-specs/phase-04-test-design.md",
                "task-specs/phase-05-implementation.md", "task-specs/phase-06-test-run.md",
                "task-specs/phase-07-acceptance.md", "task-specs/phase-08-refactoring-migration.md",
                "task-specs/phase-09-quality-assurance.md", "task-specs/phase-10-final-review.md",
                "task-specs/phase-11-evidence.md", "task-specs/phase-12-documentation-operations.md",
                "task-specs/phase-13-release-deploy.md",
            ],
            "task_node_ids": [node["graph_node_id"] for node in nodes],
        })
        self.write(self.registration, {
            "schema_version": "1.0.0", "source_digest": DIGEST,
            "promotion_receipt": self.promotion.name, "feature_package_id": "feature-package/demo",
            "parent_feature": "feature-1", "expected_count": 13, "phase_refs": PHASES,
            "binding_intents": {node["graph_node_id"]: "auto" for node in nodes}, "nodes": nodes,
        })
        self.write(self.promotion, {
            "schema_version": "1.0.0", "status": "promoted", "published_digest": DIGEST,
            "registration_manifest": self.registration.name,
        })
        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 4, "nodes": [feature_node()]})

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def write(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([
            sys.executable, str(SCRIPT), "register", "--repo-root", str(self.root),
            "--package", self.package.name, "--graph", self.registration.name,
            "--output", self.output.name, "--receipt", self.receipt.name, *extra,
        ], text=True, capture_output=True, check=False)

    def args(self, *extra: str):
        return RP._parser().parse_args([
            "register", "--repo-root", str(self.root), "--package", self.package.name,
            "--graph", self.registration.name, "--output", self.output.name,
            "--receipt", self.receipt.name, *extra,
        ])

    def test_registers_exact_13_atomically_and_is_idempotent(self) -> None:
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        graph = json.loads(self.output.read_text())
        self.assertEqual(len(graph["nodes"]), 14)
        self.assertEqual(graph["graph_revision"], 5)
        self.assertEqual({n["tracker_binding"] for n in graph["nodes"][1:]}, {"none"})
        receipt_before = self.receipt.read_bytes()
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue(json.loads(second.stdout)["idempotent"])
        self.assertEqual(self.receipt.read_bytes(), receipt_before)

    def test_projects_execution_context_through_c02_consumer(self) -> None:
        context = {
            "worktree_id": "wt_" + "1" * 16,
            "branch": "devgraph/feature-1",
            "base_branch": "main",
            "head_sha": "1" * 40,
            "state": "claimed",
            "lease_acquired_at": NOW,
            "last_seen_at": NOW,
            "released_at": None,
        }
        completed = subprocess.run([
            sys.executable, str(SCRIPT), "execution-context", "--repo-root", str(self.root),
            "--graph", self.output.name, "--graph-node-id", "feature-1",
            "--context-json", json.dumps(context),
        ], text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["owner"], "C02/run-dev-graph-node")
        self.assertEqual(receipt["status"], "applied")
        graph = json.loads(self.output.read_text())
        self.assertEqual(graph["graph_revision"], 5)
        self.assertEqual(graph["nodes"][0]["execution_contexts"], [context])
        self.assertEqual(receipt["graph_sha256_after"], hashlib.sha256(self.output.read_bytes()).hexdigest())

        before = self.output.read_bytes()
        repeated = subprocess.run([
            sys.executable, str(SCRIPT), "execution-context", "--repo-root", str(self.root),
            "--graph", self.output.name, "--graph-node-id", "feature-1",
            "--context-json", json.dumps(context),
        ], text=True, capture_output=True, check=False)
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        repeated_receipt = json.loads(repeated.stdout)
        self.assertTrue(repeated_receipt["idempotent"])
        self.assertEqual(repeated_receipt["write_count"], 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_dry_run_writes_nothing(self) -> None:
        before = json.loads(self.output.read_text())
        result = self.invoke("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.output.read_text()), before)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(json.loads(result.stdout)["write_count"], 0)

    def test_rejects_partial_registration(self) -> None:
        graph = json.loads(self.output.read_text())
        graph["nodes"].append(task_node(0))
        self.write(self.output, graph)
        before = self.output.read_bytes()
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("partial registration", result.stdout)
        self.assertEqual(self.output.read_bytes(), before)

    def test_rejects_conflicting_duplicate_registration(self) -> None:
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        graph = json.loads(self.output.read_text())
        graph["nodes"][1]["title"] = "conflicting duplicate"
        self.write(self.output, graph)
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("different content", result.stdout)

    def test_rejects_digest_mismatch(self) -> None:
        promotion = json.loads(self.promotion.read_text())
        promotion["published_digest"] = "sha256:" + "c" * 64
        self.write(self.promotion, promotion)
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("digest mismatch", result.stdout)
        self.assertFalse(self.receipt.exists())

    def test_rejects_non_forward_dependency(self) -> None:
        registration = json.loads(self.registration.read_text())
        registration["nodes"][0]["depends_on"] = ["task-P02"]
        self.write(self.registration, registration)
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-forward", result.stdout)

    def test_preflight_rejects_upstream_version_drift(self) -> None:
        result = subprocess.run([
            sys.executable, str(SCRIPT), "preflight", "--required-version", "9.9.9",
        ], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("version mismatch", result.stdout)

    def test_preflight_accepts_current_upstream_contract(self) -> None:
        result = subprocess.run([
            sys.executable, str(SCRIPT), "preflight",
        ], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])


class RegisterPackageInProcessCoverageTest(RegisterPackageTest):
    """Exercise internal fail-closed branches under coverage.py in this process."""

    def test_in_process_register_dry_run_commit_and_idempotency(self) -> None:
        preview = RP._register(self.args("--dry-run"))
        self.assertTrue(preview["dry_run"])
        first = RP._register(self.args())
        self.assertEqual(first["applied_count"], 13)
        self.assertEqual(first["graph_digest_after"], RP._canonical_digest(json.loads(self.output.read_text())))
        second = RP._register(self.args())
        self.assertTrue(second["idempotent"])

    @staticmethod
    def execution_context(*, worktree: str = "1", state: str = "claimed", seen: str = NOW) -> dict:
        return {
            "worktree_id": "wt_" + worktree * 16,
            "branch": "devgraph/feature-1", "base_branch": "main", "head_sha": "1" * 40,
            "state": state, "lease_acquired_at": NOW, "last_seen_at": seen, "released_at": None,
        }

    def execution_args(self, context, *extra: str):
        raw = context if isinstance(context, str) else json.dumps(context)
        return RP._parser().parse_args([
            "execution-context", "--repo-root", str(self.root), "--graph", self.output.name,
            "--graph-node-id", "feature-1", "--context-json", raw, *extra,
        ])

    def test_execution_context_preview_apply_replace_and_idempotent_noop(self) -> None:
        context = self.execution_context()
        before = self.output.read_bytes()
        preview = RP._project_execution_context(self.execution_args(context, "--dry-run"))
        self.assertEqual((preview["status"], preview["write_count"], preview["graph_revision_after"]), ("preview", 0, 5))
        self.assertEqual(self.output.read_bytes(), before)

        applied = RP._project_execution_context(self.execution_args(context))
        self.assertEqual((applied["status"], applied["write_count"], applied["graph_revision_after"]), ("applied", 1, 5))
        self.assertEqual(applied["graph_sha256_after"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        after = self.output.read_bytes()
        repeated = RP._project_execution_context(self.execution_args(context))
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(repeated["write_count"], 0)
        self.assertEqual(self.output.read_bytes(), after)

        changed = self.execution_context(state="in_progress", seen="2026-07-13T00:01:00Z")
        replaced = RP._project_execution_context(self.execution_args(changed))
        self.assertFalse(replaced["idempotent"])
        graph = json.loads(self.output.read_text())
        self.assertEqual(graph["graph_revision"], 6)
        self.assertEqual(graph["nodes"][0]["execution_contexts"], [changed])

    def test_execution_context_rejects_invalid_context_graph_and_target(self) -> None:
        context = self.execution_context()
        with self.assertRaisesRegex(RP.ContractError, "invalid JSON"):
            RP._project_execution_context(self.execution_args("{"))
        with self.assertRaisesRegex(RP.ContractError, "must be an object"):
            RP._project_execution_context(self.execution_args("[]"))
        invalid = dict(context); invalid.pop("last_seen_at")
        with self.assertRaisesRegex(RP.ContractError, "missing required property"):
            RP._project_execution_context(self.execution_args(invalid))

        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 4, "nodes": "invalid"})
        with self.assertRaisesRegex(RP.ContractError, "must contain nodes array"):
            RP._project_execution_context(self.execution_args(context, "--dry-run"))
        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 4, "nodes": [feature_node()]})
        missing = self.execution_args(context, "--dry-run"); missing.graph_node_id = "missing"
        with self.assertRaisesRegex(RP.ContractError, "exactly one"):
            RP._project_execution_context(missing)
        node = feature_node(); node["execution_contexts"] = {}
        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 4, "nodes": [node]})
        with self.assertRaisesRegex(RP.ContractError, "must be an array"):
            RP._project_execution_context(self.execution_args(context, "--dry-run"))

    def test_execution_context_single_writer_rejects_contention(self) -> None:
        args = self.execution_args(self.execution_context())
        with RP._single_writer(self.output):
            with self.assertRaisesRegex(RP.ContractError, "already active"):
                RP._project_execution_context(args)

    def test_idempotent_registration_rejects_conflicting_immutable_receipt(self) -> None:
        RP._register(self.args())
        receipt = json.loads(self.receipt.read_text())
        receipt["node_ids"] = list(reversed(receipt["node_ids"]))
        self.write(self.receipt, receipt)
        with self.assertRaisesRegex(RP.ContractError, "immutable receipt conflicts"):
            RP._register(self.args())

    def test_in_process_atomic_receipt_failure_rolls_graph_back(self) -> None:
        before = json.loads(self.output.read_text())
        with mock.patch.object(RP, "_atomic_create_json", side_effect=OSError("receipt disk failure")):
            with self.assertRaisesRegex(OSError, "receipt disk failure"):
                RP._register(self.args())
        self.assertEqual(json.loads(self.output.read_text()), before)
        self.assertFalse(self.receipt.exists())

    def test_in_process_lock_contention_is_fail_closed(self) -> None:
        lock_path = self.output.with_name(f".{self.output.name}.register.lock")
        with lock_path.open("a+") as stream:
            RP.fcntl.flock(stream.fileno(), RP.fcntl.LOCK_EX | RP.fcntl.LOCK_NB)
            with self.assertRaisesRegex(RP.ContractError, "already active"):
                RP._register(self.args())

    def test_in_process_contract_and_binding_failures(self) -> None:
        package = json.loads(self.package.read_text())
        registration = json.loads(self.registration.read_text())
        node_schema = json.loads((PLUGIN / "schemas" / "graph-node.schema.json").read_text())
        registration["nodes"][0]["source_lineage"]["source_digest"] = "b" * 64
        with self.assertRaisesRegex(RP.ContractError, "lineage digest mismatch"):
            RP._validate_registration(registration, package, node_schema)
        nodes = [task_node(i) for i in range(13)]
        intents = {node["graph_node_id"]: "auto" for node in nodes}
        with self.assertRaisesRegex(RP.ContractError, "both requires"):
            RP._resolved_nodes(nodes, intents, "both", node_schema)
        intents[nodes[0]["graph_node_id"]] = "github"
        with self.assertRaisesRegex(RP.ContractError, "not allowed"):
            RP._resolved_nodes(nodes, intents, "beads", node_schema)

    def test_schema_engine_covers_ref_condition_arrays_and_objects(self) -> None:
        schema = {
            "$defs": {"word": {"type": "string", "minLength": 2, "pattern": "^[a-z]+$"}},
            "type": "object", "required": ["kind", "items"], "additionalProperties": False,
            "properties": {
                "kind": {"enum": ["x"]},
                "items": {"type": "array", "minItems": 1, "maxItems": 2, "uniqueItems": True,
                          "items": {"$ref": "#/$defs/word"}, "contains": {"const": "ok"}},
                "count": {"type": "integer", "minimum": 1, "maximum": 2},
            },
            "if": {"properties": {"kind": {"const": "x"}}},
            "then": {"required": ["count"]},
        }
        RP._validate_schema({"kind": "x", "items": ["ok"], "count": 1}, schema, schema, "$fixture")
        bad_values = [
            ({"kind": "x", "items": [], "count": 1}, "too few"),
            ({"kind": "x", "items": ["ok", "ok"], "count": 1}, "not unique"),
            ({"kind": "x", "items": ["NO"], "count": 1}, "does not match"),
            ({"kind": "x", "items": ["ok"], "count": 3}, "above maximum"),
            ({"kind": "x", "items": ["ok"], "count": 1, "extra": True}, "unknown properties"),
        ]
        for value, message in bad_values:
            with self.subTest(message=message), self.assertRaisesRegex(RP.ContractError, message):
                RP._validate_schema(value, schema, schema, "$fixture")

    def test_atomic_create_is_immutable_and_paths_are_contained(self) -> None:
        target = self.root / "immutable.json"
        RP._atomic_create_json(target, {"ok": True})
        with self.assertRaisesRegex(RP.ContractError, "already exists"):
            RP._atomic_create_json(target, {"ok": False})
        self.assertEqual(json.loads(target.read_text()), {"ok": True})
        with self.assertRaisesRegex(RP.ContractError, "escapes authority"):
            RP._path(self.root, str(self.root.parent / "escape.json"), must_exist=False)

    def test_main_reports_contract_error_as_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = RP.main(["preflight", "--required-version", "9.9.9"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())["valid"])


if __name__ == "__main__":
    unittest.main()
