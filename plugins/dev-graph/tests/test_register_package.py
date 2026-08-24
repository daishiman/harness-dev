from __future__ import annotations

import hashlib
import json
import importlib.util
import io
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


def macro_request() -> dict:
    return {
        "schema_version": "1.0.0",
        "observed_at": NOW,
        "project_id": "todo-api",
        "source_digest": HEX_DIGEST,
        "architecture": {
            "graph_node_id": "architecture-todo-api",
            "title": "TODO API architecture",
            "artifact_subtypes": ["backend", "security"],
            "domain": "api",
            "resource_scope": ["architecture"],
        },
        "features": [
            {
                "graph_node_id": "feature-auth",
                "title": "Authentication",
                "domain": "auth",
                "purpose": "Protect API access",
                "goal": "Only authenticated callers access the API",
                "scope_in": ["authentication"],
                "scope_out": ["todo storage"],
                "acceptance": ["unauthenticated requests are rejected"],
                "depends_on": [],
                "resource_scope": ["features"],
            },
            {
                "graph_node_id": "feature-todo",
                "title": "TODO management",
                "domain": "todo",
                "purpose": "Manage TODO items",
                "goal": "Authenticated callers manage their TODO items",
                "scope_in": ["TODO CRUD"],
                "scope_out": ["authentication mechanism"],
                "acceptance": ["TODO CRUD works for authenticated callers"],
                "depends_on": ["feature-auth"],
                "resource_scope": ["features"],
            },
        ],
    }


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
        "file_path": f"tasks/feature-1/{phase.lower()}.md", "template_id": "task", "template_version": "1.0.0",
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

    def preview_macro(self, request: dict, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([
            sys.executable, str(SCRIPT), "preview-macro", "--repo-root", str(self.root),
            "--graph", self.output.name, "--request-json", json.dumps(request), *extra,
        ], text=True, capture_output=True, check=False)

    def reset_macro_graph(self) -> None:
        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 0, "nodes": []})
        (self.root / "architecture").mkdir(exist_ok=True)
        (self.root / "features").mkdir(exist_ok=True)

    def apply_macro(self, request: dict, digest: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([
            sys.executable, str(SCRIPT), "apply-macro", "--repo-root", str(self.root),
            "--graph", self.output.name, "--request-json", json.dumps(request),
            "--expected-candidate-digest", digest, "--receipt", "macro-receipt.json", *extra,
        ], text=True, capture_output=True, check=False)

    def test_macro_preview_is_c02_generated_and_write_free(self) -> None:
        self.reset_macro_graph()
        before = self.output.read_bytes()
        before_names = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        result = self.preview_macro(macro_request(), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["owner"], "C02/run-dev-graph-node")
        self.assertEqual(receipt["operation"], "preview_macro_decomposition")
        self.assertEqual(receipt["status"], "preview")
        self.assertTrue(receipt["dry_run"])
        self.assertEqual(receipt["write_count"], 0)
        self.assertEqual(receipt["validation"]["violations"], [])
        self.assertEqual(receipt["validation"]["authority"], "C11/validate-graph-schema.py")
        self.assertEqual([node["artifact_kind"] for node in receipt["candidate_nodes"]], ["architecture", "feature", "feature"])
        self.assertEqual({node["status"] for node in receipt["candidate_nodes"]}, {"draft"})
        self.assertEqual(receipt["candidate_nodes"][2]["depends_on"], ["feature-auth"])
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*")), before_names)

    def test_macro_preview_requires_dry_run_and_never_falls_back_to_apply(self) -> None:
        self.reset_macro_graph()
        before = self.output.read_bytes()
        result = self.preview_macro(macro_request())
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run is required", result.stdout)
        self.assertEqual(self.output.read_bytes(), before)

    def test_macro_preview_rejects_cycles_without_materializing_a_candidate(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        request["features"][0]["depends_on"] = ["feature-todo"]
        before = self.output.read_bytes()
        result = self.preview_macro(request, "--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("dependency cycle", result.stdout)
        self.assertEqual(self.output.read_bytes(), before)

    def test_macro_intent_derives_architecture_refs_and_rejects_caller_override(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        request["features"][0]["architecture_refs"] = ["caller-supplied"]
        rejected = self.preview_macro(request, "--dry-run")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("unknown properties ['architecture_refs']", rejected.stdout)

        accepted = self.preview_macro(macro_request(), "--dry-run")
        receipt = json.loads(accepted.stdout)
        expected = [macro_request()["architecture"]["graph_node_id"]]
        self.assertEqual({tuple(node["architecture_refs"]) for node in receipt["candidate_nodes"][1:]}, {tuple(expected)})

    def test_macro_preview_apply_share_digest_and_apply_is_idempotent(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        preview = self.preview_macro(request, "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        preview_receipt = json.loads(preview.stdout)

        applied = self.apply_macro(request, preview_receipt["candidate_graph_digest"])
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        receipt = json.loads(applied.stdout)
        self.assertEqual(receipt["candidate_graph_digest"], preview_receipt["candidate_graph_digest"])
        self.assertEqual(receipt["candidate_nodes_digest"], preview_receipt["candidate_nodes_digest"])
        self.assertEqual(receipt["validation"]["authority"], "C11/validate-graph-schema.py")
        self.assertEqual(receipt["validation"]["violations"], [])
        self.assertEqual(receipt["candidate_node_ids"], preview_receipt["candidate_node_ids"])
        self.assertEqual(json.loads(self.output.read_text())["nodes"], preview_receipt["candidate_nodes"])
        self.assertTrue((self.root / "architecture/architecture-todo-api.md").is_file())
        self.assertTrue((self.root / "features/feature-auth.md").is_file())
        self.assertTrue((self.root / "features/feature-todo.md").is_file())
        immutable = (self.root / "macro-receipt.json").read_bytes()

        repeated = self.apply_macro(request, preview_receipt["candidate_graph_digest"])
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        repeated_receipt = json.loads(repeated.stdout)
        self.assertTrue(repeated_receipt["idempotent"])
        self.assertEqual(repeated_receipt["write_count"], 0)
        self.assertEqual((self.root / "macro-receipt.json").read_bytes(), immutable)

    def test_macro_is_idempotent_after_unrelated_graph_growth(self) -> None:
        self.reset_macro_graph()
        first_request = macro_request()
        first_preview = self.preview_macro(first_request, "--dry-run")
        self.assertEqual(first_preview.returncode, 0, first_preview.stdout + first_preview.stderr)
        first_digest = json.loads(first_preview.stdout)["candidate_graph_digest"]
        first_apply = self.apply_macro(first_request, first_digest)
        self.assertEqual(first_apply.returncode, 0, first_apply.stdout + first_apply.stderr)
        immutable = (self.root / "macro-receipt.json").read_bytes()

        second_request = json.loads(json.dumps(first_request))
        second_request["project_id"] = "other"
        second_request["architecture"]["graph_node_id"] = "architecture-other"
        second_request["features"][0]["graph_node_id"] = "feature-other-auth"
        second_request["features"][1]["graph_node_id"] = "feature-other-todo"
        second_request["features"][1]["depends_on"] = ["feature-other-auth"]
        second_preview = self.preview_macro(second_request, "--dry-run")
        self.assertEqual(second_preview.returncode, 0, second_preview.stdout + second_preview.stderr)
        second_apply = subprocess.run([
            sys.executable, str(SCRIPT), "apply-macro", "--repo-root", str(self.root),
            "--graph", self.output.name, "--request-json", json.dumps(second_request),
            "--expected-candidate-digest", json.loads(second_preview.stdout)["candidate_graph_digest"],
            "--receipt", "macro-receipt-other.json",
        ], text=True, capture_output=True, check=False)
        self.assertEqual(second_apply.returncode, 0, second_apply.stdout + second_apply.stderr)

        repeated_preview = self.preview_macro(first_request, "--dry-run")
        self.assertEqual(repeated_preview.returncode, 0, repeated_preview.stdout + repeated_preview.stderr)
        repeated_preview_receipt = json.loads(repeated_preview.stdout)
        repeated = self.apply_macro(
            first_request, repeated_preview_receipt["candidate_graph_digest"],
        )
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        repeated_receipt = json.loads(repeated.stdout)
        self.assertTrue(repeated_receipt["idempotent"])
        self.assertEqual(repeated_receipt["write_count"], 0)
        self.assertEqual(
            repeated_receipt["candidate_graph_digest"],
            repeated_preview_receipt["candidate_graph_digest"],
        )
        self.assertEqual(
            repeated_receipt["graph_revision_after"],
            repeated_preview_receipt["graph_revision_after_preview"],
        )
        self.assertEqual((self.root / "macro-receipt.json").read_bytes(), immutable)

    def test_macro_idempotency_rejects_missing_or_tampered_intent_nodes(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        preview = self.preview_macro(request, "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        applied = self.apply_macro(request, json.loads(preview.stdout)["candidate_graph_digest"])
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        durable = json.loads(self.output.read_text(encoding="utf-8"))
        immutable = (self.root / "macro-receipt.json").read_bytes()

        tampered = json.loads(json.dumps(durable))
        tampered["nodes"][1]["title"] = "tampered"
        self.write(self.output, tampered)
        rejected_tamper = self.preview_macro(request, "--dry-run")
        self.assertEqual(rejected_tamper.returncode, 2)
        self.assertIn("different content", rejected_tamper.stdout)

        missing = json.loads(json.dumps(durable))
        missing["nodes"].pop()
        self.write(self.output, missing)
        rejected_missing = self.preview_macro(request, "--dry-run")
        self.assertEqual(rejected_missing.returncode, 2)
        self.assertIn("partial macro registration", rejected_missing.stdout)
        self.assertEqual((self.root / "macro-receipt.json").read_bytes(), immutable)

    def test_macro_idempotency_rejects_symlinked_durable_artifact_without_writes(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        preview = self.preview_macro(request, "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        digest = json.loads(preview.stdout)["candidate_graph_digest"]
        applied = self.apply_macro(request, digest)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

        target = self.root / "features/feature-auth.md"
        user_owned = self.root / "features/user-owned-feature-auth.md"
        target.replace(user_owned)
        target.symlink_to(user_owned.name)
        graph_before = self.output.read_bytes()
        receipt_before = (self.root / "macro-receipt.json").read_bytes()
        user_owned_before = user_owned.read_bytes()

        rejected_preview = self.preview_macro(request, "--dry-run")
        self.assertEqual(rejected_preview.returncode, 2, rejected_preview.stdout + rejected_preview.stderr)
        self.assertIn("must not be a symlink", rejected_preview.stdout)
        rejected_apply = self.apply_macro(request, digest)
        self.assertEqual(rejected_apply.returncode, 2, rejected_apply.stdout + rejected_apply.stderr)
        self.assertIn("must not be a symlink", rejected_apply.stdout)
        self.assertEqual(self.output.read_bytes(), graph_before)
        self.assertEqual((self.root / "macro-receipt.json").read_bytes(), receipt_before)
        self.assertTrue(target.is_symlink())
        self.assertEqual(user_owned.read_bytes(), user_owned_before)

    def test_macro_rejects_untracked_artifact_path_without_writes(self) -> None:
        self.reset_macro_graph()
        collision = self.root / "features/feature-auth.md"
        collision.write_text("user-owned\n", encoding="utf-8")
        graph_before = self.output.read_bytes()
        result = self.preview_macro(macro_request(), "--dry-run")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("artifact path already exists without durable graph node", result.stdout)
        self.assertEqual(collision.read_text(encoding="utf-8"), "user-owned\n")
        self.assertEqual(self.output.read_bytes(), graph_before)
        self.assertFalse((self.root / "macro-receipt.json").exists())

    def test_macro_apply_rejects_stale_digest_without_partial_writes(self) -> None:
        self.reset_macro_graph()
        before = self.output.read_bytes()
        result = self.apply_macro(macro_request(), "sha256:" + "0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn("candidate digest mismatch", result.stdout)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse((self.root / "macro-receipt.json").exists())
        self.assertEqual(list((self.root / "architecture").iterdir()), [])
        self.assertEqual(list((self.root / "features").iterdir()), [])

    def test_macro_apply_rejects_partial_durable_nodes_without_more_writes(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        architecture = RP._macro_node_base(request, request["architecture"], "architecture")
        self.write(self.output, {"schema_version": "1.0.0", "graph_revision": 1, "nodes": [architecture]})
        before = self.output.read_bytes()
        result = self.apply_macro(request, "sha256:" + "0" * 64)
        self.assertEqual(result.returncode, 2)
        self.assertIn("partial macro registration", result.stdout)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse((self.root / "macro-receipt.json").exists())
        self.assertEqual(list((self.root / "features").iterdir()), [])

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

    def test_legacy_receipt_gets_content_addressed_revalidation_evidence(self) -> None:
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        legacy = json.loads(self.receipt.read_text(encoding="utf-8"))
        legacy.pop("c11_readiness_digest")
        self.write(self.receipt, legacy)
        immutable = self.receipt.read_bytes()
        expected_c11 = RP.c11_readiness_digest(
            json.loads(self.output.read_text(encoding="utf-8"))["nodes"], "feature-1",
        )
        c11 = {
            "valid": True,
            "violations": [],
            "implementation_readiness": "complete",
            "readiness_digest": expected_c11,
        }
        readiness = {
            "status": "complete",
            "missing_sections": [],
            "source_pin": {"source_digest": "sha256:" + "d" * 64},
        }
        with mock.patch.object(RP, "_run_c11", return_value=c11), mock.patch.object(
            RP, "_current_readiness", return_value=readiness,
        ):
            preview = RP._register(self.args("--dry-run"))
            self.assertEqual(preview["write_count"], 0)
            self.assertFalse((self.root / preview["supplemental_evidence"]).exists())
            applied = RP._register(self.args())
            evidence_path = self.root / applied["supplemental_evidence"]
            self.assertEqual(applied["write_count"], 1)
            self.assertTrue(evidence_path.is_file())
            self.assertEqual(self.receipt.read_bytes(), immutable)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["c11_readiness_digest"], expected_c11)
            self.assertEqual(evidence["immutable_receipt_sha256"], "sha256:" + hashlib.sha256(immutable).hexdigest())
            self.assertEqual(evidence["graph_sha256"], "sha256:" + hashlib.sha256(self.output.read_bytes()).hexdigest())
            repeated = RP._register(self.args())
            self.assertEqual(repeated["write_count"], 0)
            self.assertEqual(repeated["supplemental_evidence"], applied["supplemental_evidence"])
            self.assertEqual(self.receipt.read_bytes(), immutable)

            evidence["graph_sha256"] = "sha256:" + "e" * 64
            self.write(evidence_path, evidence)
            graph_before = self.output.read_bytes()
            with self.assertRaisesRegex(RP.ContractError, "evidence conflicts"):
                RP._register(self.args())
            self.assertEqual(self.output.read_bytes(), graph_before)
            self.assertEqual(self.receipt.read_bytes(), immutable)

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
        self.assertEqual(
            first["c11_readiness_digest"],
            RP.c11_readiness_digest(json.loads(self.output.read_text())["nodes"], "feature-1"),
        )
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

    def macro_apply_args(self, request: dict, digest: str):
        return RP._parser().parse_args([
            "apply-macro", "--repo-root", str(self.root), "--graph", self.output.name,
            "--request-json", json.dumps(request), "--expected-candidate-digest", digest,
            "--receipt", "macro-receipt.json",
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

    def test_macro_receipt_failure_rolls_back_graph_and_documents(self) -> None:
        self.reset_macro_graph()
        request = macro_request()
        preview = RP._preview_macro(RP._parser().parse_args([
            "preview-macro", "--repo-root", str(self.root), "--graph", self.output.name,
            "--request-json", json.dumps(request), "--dry-run",
        ]))
        before = self.output.read_bytes()
        with mock.patch.object(RP, "_atomic_create_json", side_effect=OSError("receipt disk failure")):
            with self.assertRaisesRegex(OSError, "receipt disk failure"):
                RP._apply_macro(self.macro_apply_args(request, preview["candidate_graph_digest"]))
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse((self.root / "macro-receipt.json").exists())
        self.assertEqual(list((self.root / "architecture").iterdir()), [])
        self.assertEqual(list((self.root / "features").iterdir()), [])

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
