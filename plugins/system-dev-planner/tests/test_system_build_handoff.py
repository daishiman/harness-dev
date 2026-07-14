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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


FIXTURES = load_module("test_sdp_handoff_fixtures", Path(__file__).with_name("test_runtime.py"))
HANDOFF = load_module("test_sdp_system_handoff", PLUGIN / "scripts" / "build-system-handoff.py")


class SystemBuildHandoffTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[str, Path, str]:
        repository_id = FIXTURES.make_repo(root)
        staging, digest = FIXTURES.make_fixture(root, repository_id, include_handoff=False)
        return repository_id, staging, digest

    def call(self, root: Path, *extra: str) -> tuple[int, dict | None, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["--repo-root", str(root), "--staging", ".dev-graph/staging/run-1", *extra]
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = HANDOFF.main(argv)
        value = json.loads(stdout.getvalue()) if stdout.getvalue().strip() else None
        return rc, value, stderr.getvalue()

    def test_generates_deterministic_handoff_and_manifest_commit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repository_id, staging, source_digest = self.fixture(root)
            original_manifest = (staging / "staging-manifest.json").read_bytes()

            rc, receipt, stderr = self.call(root)
            self.assertEqual((rc, stderr), (0, ""))
            self.assertEqual(receipt["status"], "generated")
            self.assertFalse(receipt["receipt_artifacts_created"])

            handoff_path = staging / "system-build-handoff.json"
            manifest_path = staging / "staging-manifest.json"
            handoff_bytes = handoff_path.read_bytes()
            handoff = json.loads(handoff_bytes)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(handoff["identity"], {
                "repository_id": repository_id,
                "feature_id": "FEATURE-1",
                "feature_package_id": "feature-package/feat",
                "parent_feature": "FEATURE-1",
                "source_feature_digest": json.loads(
                    (staging / "feature-package.json").read_text(encoding="utf-8")
                )["source_feature_digest"],
            })
            self.assertEqual(len(handoff["source_inputs"]), 16)
            self.assertEqual(len(handoff["execution_tasks"]), 13)
            self.assertEqual(handoff["source_manifest"]["sha256_before_handoff"],
                             hashlib.sha256(original_manifest).hexdigest())
            self.assertEqual(handoff["source_manifest"]["canonical_digest_before_handoff"], source_digest)
            self.assertEqual(manifest["files"]["system-build-handoff.json"],
                             hashlib.sha256(handoff_bytes).hexdigest())
            contents = {
                rel: (staging / rel).read_bytes() for rel in manifest["files"]
            }
            self.assertEqual(manifest["canonical_digest"], HANDOFF._canonical_digest(contents))
            self.assertEqual(manifest["handoff_contract"]["source_canonical_digest"], source_digest)

    def test_rerun_is_byte_for_byte_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); self.fixture(root)
            self.assertEqual(self.call(root)[0], 0)
            staging = root / ".dev-graph/staging/run-1"
            before = {
                name: (staging / name).read_bytes()
                for name in ("system-build-handoff.json", "staging-manifest.json")
            }
            rc, _, stderr = self.call(root)
            self.assertEqual((rc, stderr), (0, ""))
            after = {name: (staging / name).read_bytes() for name in before}
            self.assertEqual(after, before)

    def test_declares_receipt_owners_without_forging_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            self.assertEqual(self.call(root)[0], 0)
            handoff = json.loads((staging / "system-build-handoff.json").read_text(encoding="utf-8"))
            request = handoff["registration_request"]
            self.assertEqual(request["owner"], "system-dev-planner/C11")
            self.assertEqual(request["promotion_receipt"]["owner"], "system-dev-planner/C11")
            self.assertEqual(request["registration_receipt"]["owner"], "dev-graph/C02")
            self.assertFalse(request["promotion_receipt"]["produced_by_this_component"])
            self.assertFalse(request["registration_receipt"]["produced_by_this_component"])
            self.assertFalse((staging / "atomic-promotion-receipt.json").exists())
            self.assertFalse((staging / "dev-graph-registration-receipt.json").exists())

    def test_repository_identity_mismatch_fails_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            inventory_path = staging / "workstream-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["repo_context"]["repo_identity"] = "local:sha256:" + "f" * 64
            FIXTURES.dump(inventory_path, inventory); FIXTURES.refresh_manifest(staging)
            rc, value, stderr = self.call(root)
            self.assertEqual(rc, 2); self.assertIsNone(value)
            self.assertIn("repository identity", stderr)
            self.assertFalse((staging / "system-build-handoff.json").exists())

    def test_package_inventory_identity_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            inventory_path = staging / "workstream-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["parent_feature"] = "OTHER-FEATURE"
            FIXTURES.dump(inventory_path, inventory); FIXTURES.refresh_manifest(staging)
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2)
            self.assertTrue("source schema violation" in stderr or "feature identity mismatch" in stderr)

    def test_manifest_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            manifest_path = staging / "staging-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["feature-package.json"] = "0" * 64
            FIXTURES.dump(manifest_path, manifest)
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2); self.assertIn("manifest digest mismatch", stderr)

    def test_leaf_symlink_is_rejected_even_when_digest_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            victim = staging / HANDOFF.TASK_PATHS[0]
            external = root / "external-task.md"
            external.write_bytes(victim.read_bytes())
            victim.unlink(); victim.symlink_to(external)
            FIXTURES.refresh_manifest(staging)
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2); self.assertIn("symlink path component", stderr)
            self.assertFalse((staging / "system-build-handoff.json").exists())

    def test_staging_directory_symlink_is_rejected_before_normalization(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            alias = root / ".dev-graph/staging/alias"
            alias.symlink_to(staging, target_is_directory=True)
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(root)}, clear=True), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = HANDOFF.main([
                    "--repo-root", str(root), "--staging", ".dev-graph/staging/alias",
                ])
            self.assertEqual(rc, 2)
            self.assertIn("symlink path component", stderr.getvalue())
            self.assertFalse((staging / "system-build-handoff.json").exists())

    def test_uncommitted_output_symlink_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            outside = root / "outside.json"
            outside.write_text('{"untouched":true}\n', encoding="utf-8")
            (staging / "system-build-handoff.json").symlink_to(outside)
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2)
            self.assertIn("symlink path component", stderr)
            self.assertEqual(json.loads(outside.read_text(encoding="utf-8")), {"untouched": True})

    def test_manifest_is_commit_point_and_rerun_recovers_uncommitted_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            original_manifest = (staging / "staging-manifest.json").read_bytes()
            replace = HANDOFF._atomic_replace

            def fail_manifest(path: Path, data: bytes) -> None:
                if path.name == "staging-manifest.json":
                    raise OSError("simulated manifest commit failure")
                replace(path, data)

            with mock.patch.object(HANDOFF, "_atomic_replace", side_effect=fail_manifest):
                rc, _, stderr = self.call(root)
            self.assertEqual(rc, 1); self.assertIn("simulated manifest commit failure", stderr)
            self.assertTrue((staging / "system-build-handoff.json").exists())
            self.assertEqual((staging / "staging-manifest.json").read_bytes(), original_manifest)
            self.assertNotIn("system-build-handoff.json", json.loads(original_manifest)["files"])
            self.assertEqual(self.call(root)[0], 0)

    def test_tampered_committed_handoff_and_usage_fail_with_stable_codes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            self.assertEqual(self.call(root)[0], 0)
            (staging / "system-build-handoff.json").write_text("{}\n", encoding="utf-8")
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2); self.assertIn("manifest digest mismatch", stderr)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = HANDOFF.main([])
        self.assertEqual(rc, 1); self.assertIn("--staging", stderr.getvalue())

    def test_low_level_parsers_fail_closed_on_malformed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            malformed = root / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(HANDOFF.PolicyError, "invalid JSON"):
                HANDOFF._json(malformed)
            malformed.write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(HANDOFF.PolicyError, "JSON object required"):
                HANDOFF._json(malformed)
            with self.assertRaisesRegex(HANDOFF.PolicyError, "escapes repository"):
                HANDOFF._reject_symlink_chain(root / "repo", root / "outside")

        listed = {"files": [{"path": "a", "sha256": "0" * 64}]}
        self.assertEqual(HANDOFF._manifest_files(listed), {"a": "0" * 64})
        for candidate, message in (
            ({"files": "bad"}, "object or path/sha256 array"),
            ({"files": [{"path": "a", "sha256": 1}]}, "string path/sha256"),
            ({"files": {"a": "xyz"}}, "invalid manifest sha256"),
            ({"files": [{"path": "a", "sha256": "0" * 64},
                         {"path": "a", "sha256": "0" * 64}]}, "duplicate manifest path"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(HANDOFF.PolicyError, message):
                HANDOFF._manifest_files(candidate)
        with self.assertRaisesRegex(HANDOFF.PolicyError, "schema violation"):
            HANDOFF._schema_check({}, FIXTURES.VALIDATOR)

    def test_graph_identity_and_dependency_drift_are_rejected(self):
        for field, value, expected in (
            ("parent_feature", "OTHER", "mixed feature identity"),
            ("depends_on", ["UNRELATED"], "dependency mismatch"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td).resolve(); _, staging, _ = self.fixture(root)
                graph_path = staging / "task-graph.json"
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                graph["nodes"][0][field] = value
                FIXTURES.dump(graph_path, graph); FIXTURES.refresh_manifest(staging)
                rc, _, stderr = self.call(root)
                self.assertEqual(rc, 2); self.assertIn(expected, stderr)

    def test_final_manifest_canonical_digest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); _, staging, _ = self.fixture(root)
            self.assertEqual(self.call(root)[0], 0)
            manifest_path = staging / "staging-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["canonical_digest"] = "sha256:" + "0" * 64
            FIXTURES.dump(manifest_path, manifest)
            rc, _, stderr = self.call(root)
            self.assertEqual(rc, 2); self.assertIn("final manifest canonical digest mismatch", stderr)


if __name__ == "__main__":
    unittest.main()
