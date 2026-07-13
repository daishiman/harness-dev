from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import test_runtime as fx


C09 = fx.C09
VALIDATOR = fx.VALIDATOR
C08 = fx.load_module("test_sdp_readiness", "check-implementation-readiness.py")
C10 = fx.load_module("test_sdp_init", "init-project-layout.py")
HOOK = fx.load_module("test_sdp_hook", "../hooks/guard-implementation-readiness.py")


def invoke(module, args, env: dict[str, str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return module.main(args), stdout.getvalue(), stderr.getvalue()


def readiness_files(root: Path, *, placeholder: bool = False) -> None:
    text = "# Confirmed\n\nTODO\n" if placeholder else "# Confirmed\n\nReady.\n"
    (root / "system-spec").mkdir(parents=True, exist_ok=True)
    (root / "architecture").mkdir(parents=True, exist_ok=True)
    (root / "system-spec/index.md").write_text(text, encoding="utf-8")
    (root / "system-spec/00-requirements-definition.md").write_text("# Requirements\n\nReady.\n", encoding="utf-8")
    fx.dump(root / "architecture/graph.json", {"nodes": [{"id": "A1"}]})
    aspects = {
        "foundation_trace": ("assign-system-spec-completeness-evaluator", "C05"),
        "decision_guidance": ("assign-system-spec-completeness-evaluator", "C05"),
        "matrix_coverage": ("system-spec-matrix-auditor", "C07"),
        "design_knowledge_reflection": ("assign-system-spec-completeness-evaluator", "C05"),
        "doc_freshness": ("system-spec-doc-freshness-auditor", "C08"),
        "prompt_quality": ("assign-system-spec-completeness-evaluator", "C05"),
    }
    fx.dump(root / "system-spec/completeness-findings.json", {
        "evaluator": {"name": "assign-system-spec-completeness-evaluator", "version": "0.1.0", "context": "fork"},
        "verdict": "PASS",
        "aspects": {key: {"verdict": "PASS", "auditor": owner, "component": component,
                           "summary": "independently verified"}
                    for key, (owner, component) in aspects.items()},
        "findings": [{"severity": "info", "bucket": "coverage", "observation": "all aspects checked"}],
        "gaps": [],
    })


class ReadinessCoverageTests(unittest.TestCase):
    def test_main_complete_incomplete_and_policy_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); fx.make_repo(root); readiness_files(root)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            code, stdout, _ = invoke(C08, ["--repo-root", str(root)], env)
            self.assertEqual(code, 0); self.assertEqual(json.loads(stdout)["status"], "complete")
            readiness_files(root, placeholder=True)
            code, stdout, stderr = invoke(C08, ["--repo-root", str(root)], env)
            self.assertEqual(code, 1); self.assertEqual(json.loads(stdout)["status"], "incomplete")
            self.assertIn("placeholder", stderr)
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(stderr):
                with self.assertRaisesRegex(SystemExit, "2"):
                    C08.main(["--repo-root", str(root), "--system-spec-root", "../escape"])
            self.assertIn("repository", stderr.getvalue())
            for flag, value in (
                ("--system-spec-root", "safe/../../outside/system-spec"),
                ("--architecture-root", "safe/../../outside/architecture"),
                ("--completeness-report", "safe/../../outside/report.json"),
            ):
                with self.subTest(flag=flag), self.assertRaisesRegex(SystemExit, "2"):
                    C08.main(["--repo-root", str(root), flag, value])

    def test_probe_variants_and_missing_policy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = C08._probe_file(root, "missing.md")
            self.assertFalse(missing.exists)
            (root / "architecture").mkdir()
            (root / "architecture/graph.json").write_text("not json", encoding="utf-8")
            probe = C08._probe_architecture(root, "architecture")
            self.assertTrue(probe.exists); self.assertFalse(probe.non_empty)
            status, reasons = C08.evaluate_readiness({})
            self.assertEqual(status, "incomplete"); self.assertEqual(len(reasons), 5)
            no_heading = {name: C08.Probe(name, True, True, True, 0, True)
                          for name in ("system_spec_index", "requirements_definition", "architecture_graph",
                                       "completeness_evaluation", "source_plugin_manifest")}
            self.assertEqual(C08.evaluate_readiness(no_heading)[0], "incomplete")

    def test_completeness_report_is_required_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); fx.make_repo(root); readiness_files(root)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            report = root / "system-spec/completeness-findings.json"
            report.unlink()
            code, stdout, _ = invoke(C08, ["--repo-root", str(root)], env)
            self.assertEqual(code, 1)
            self.assertIn("completeness_evaluation:file-missing", json.loads(stdout)["missing_sections"])
            readiness_files(root)
            value = json.loads(report.read_text(encoding="utf-8")); value["verdict"] = "FAIL"
            fx.dump(report, value)
            code, stdout, _ = invoke(C08, ["--repo-root", str(root)], env)
            self.assertEqual(code, 1)
            self.assertIn("completeness_evaluation:producer-verification-failed",
                          json.loads(stdout)["missing_sections"])

    def test_leaf_symlink_escape_and_architecture_fallback_are_rejected(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside_td:
            root = Path(td).resolve(); fx.make_repo(root); readiness_files(root)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            outside = Path(outside_td).resolve()
            outside_index = outside / "index.md"
            outside_index.write_text("# Outside\n\nReady.\n", encoding="utf-8")
            index = root / "system-spec/index.md"
            index.unlink(); index.symlink_to(outside_index)
            with self.assertRaisesRegex(SystemExit, "2"):
                C08.main(["--repo-root", str(root)])

            index.unlink(); index.write_text("# Confirmed\n\nReady.\n", encoding="utf-8")
            graph = root / "architecture/graph.json"
            graph.unlink()
            fx.dump(root / "architecture/unrelated.json", {"nodes": [{"id": "not-canonical"}]})
            code, stdout, _ = invoke(C08, ["--repo-root", str(root)], env)
            self.assertEqual(code, 1)
            self.assertIn("architecture_graph:file-missing", json.loads(stdout)["missing_sections"])


class InitCoverageTests(unittest.TestCase):
    def test_create_idempotent_merge_and_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            code, first, _ = invoke(C10, ["--repo-root", str(root)], env)
            self.assertEqual(code, 0); self.assertIn("created", first)
            code, second, _ = invoke(C10, ["--repo-root", str(root)], env)
            self.assertEqual(code, 0); self.assertIn("skipped", second)
            config_path = root / ".dev-graph/config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["content_roots"].pop("documents")
            fx.dump(config_path, config)
            code, merged, _ = invoke(C10, ["--repo-root", str(root)], env)
            self.assertEqual(code, 0); self.assertIn("merged_missing", merged)
            config = json.loads(config_path.read_text(encoding="utf-8")); config["repository_id"] = "github:wrong/repo"
            fx.dump(config_path, config)
            code, _, stderr = invoke(C10, ["--repo-root", str(root)], env)
            self.assertEqual(code, 2); self.assertIn("mismatch", stderr)

    def test_invalid_asset_is_usage_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); asset = root / "bad.json"; asset.write_text("{", encoding="utf-8")
            code, _, _ = invoke(C10, ["--repo-root", str(root), "--asset", str(asset)],
                                {**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
            self.assertEqual(code, 1)


class HookCoverageTests(unittest.TestCase):
    def call(self, payload: dict, env: dict[str, str]) -> tuple[int, str]:
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(HOOK.sys, "stdin", io.StringIO(json.dumps(payload))), \
                contextlib.redirect_stderr(stderr):
            return HOOK.main(), stderr.getvalue()

    def test_non_gated_tool_and_unresolvable_context_pass_through(self):
        # non Bash/Task tool -> pass-through
        self.assertEqual(self.call({"tool_name": "Read"}, dict(os.environ))[0], 0)
        # gated tool but the caller repository cannot be resolved (no managed context):
        # env-independent guard has nothing to enforce, so it passes through (does NOT deny).
        env = {**os.environ, "CLAUDE_PROJECT_DIR": "/definitely/missing"}
        self.assertEqual(self.call({"tool_name": "Bash"}, env)[0], 0)

    def test_managed_context_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); fx.make_repo(root)
            config = root / ".dev-graph/config.json"
            value = json.loads(config.read_text(encoding="utf-8"))
            value["repository_id"] = "github:wrong/repository"
            fx.dump(config, value)
            code, stderr = self.call(
                {"tool_name": "Bash", "tool_input": {"command": "build"}},
                {**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
            )
            self.assertEqual(code, 2)
            self.assertIn("managed repository context is invalid", stderr)

    def test_env_independent_lock_lifecycle_and_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); fx.make_repo(root); readiness_files(root)
            # NOTE: no SYSTEM_DEV_RUN_ID / SYSTEM_DEV_SESSION_OWNER in env — the guard
            # self-discovers active locks under locks/ by scanning, proving env-independence.
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            payload = {"tool_name": "Bash", "tool_input": {"command": "build"}}
            repository_id, _ = C09.derive_repository_id(root)
            def lock_value(repo: str, expires: datetime) -> dict:
                acquired = expires - timedelta(minutes=10)
                heartbeat = expires - timedelta(minutes=5)
                return {
                    "repository_id": repo,
                    "run_id": "run-xyz",
                    "session_owner": "session-xyz",
                    "feature_id": "FEATURE-1",
                    "feature_digest": "sha256:" + "a" * 64,
                    "acquired_at": acquired.isoformat(),
                    "heartbeat_at": heartbeat.isoformat(),
                    "expires_at": expires.isoformat(),
                }
            # arbitrary run id in the filename — found by glob, not by env
            lock = root / ".dev-graph/locks/system-dev-plan-run-xyz.json"
            self.assertEqual(self.call(payload, env)[0], 0)  # no lock -> pass-through
            lock.write_text("{", encoding="utf-8")
            # malformed repository-local lock is fail-closed and cannot disable the guard.
            self.assertEqual(self.call(payload, env)[0], 2)
            # lock belongs to another repository -> ignored across the boundary
            fx.dump(lock, lock_value("other", datetime.now(timezone.utc) + timedelta(minutes=10)))
            self.assertEqual(self.call(payload, env)[0], 0)
            # our repo, bad expiry is malformed and blocks before readiness.
            malformed = lock_value(repository_id, datetime.now(timezone.utc) + timedelta(minutes=10))
            malformed["expires_at"] = "bad"
            fx.dump(lock, malformed)
            self.assertEqual(self.call(payload, env)[0], 2)
            # expired lock -> audit cleanup + pass-through
            expired = datetime.now(timezone.utc) - timedelta(minutes=1)
            fx.dump(lock, lock_value(repository_id, expired))
            self.assertEqual(self.call(payload, env)[0], 0); self.assertFalse(lock.exists())
            # active (renewed/future) lock + readiness complete -> enforce -> pass(0)
            future = datetime.now(timezone.utc) + timedelta(minutes=5)
            fx.dump(lock, lock_value(repository_id, future))
            self.assertEqual(self.call(payload, env)[0], 0)
            # active lock + readiness incomplete -> block(2)
            readiness_files(root, placeholder=True)
            code, stderr = self.call(payload, env)
            self.assertEqual(code, 2); self.assertIn("BLOCKED", stderr)


class ContextCoverageTests(unittest.TestCase):
    def test_git_helpers_env_marker_and_identity_sources(self):
        completed = __import__("subprocess").CompletedProcess([], 0, stdout="value\n", stderr="")
        with mock.patch.object(C09.subprocess, "run", return_value=completed):
            self.assertEqual(C09._git(Path("."), "x"), "value")
        with mock.patch.object(C09.subprocess, "run", side_effect=OSError("missing")):
            self.assertIsNone(C09._git(Path("."), "x"))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); (root / ".dev-graph").mkdir(); (root / ".dev-graph/config.json").write_text("{}")
            resolved, source, evidence = C09.resolve_repo_root(None, {"SYSTEM_DEV_PROJECT_ROOT": str(root)})
            self.assertEqual(resolved, root); self.assertIn("SYSTEM_DEV_PROJECT_ROOT", source)
            self.assertIsNone(evidence["host_declared"])
            self.assertEqual(C09._find_marker_upwards(root / "child"), root)
            with mock.patch.object(C09, "_git", side_effect=["git@github.com:o/r.git", None]):
                self.assertEqual(C09.derive_repository_id(root), ("github:o/r", "git-remote-origin"))
            with mock.patch.object(C09, "_git", side_effect=[None, ".git"]):
                repository_id, source = C09.derive_repository_id(root)
                self.assertTrue(repository_id.startswith("local:sha256:")); self.assertEqual(source, "local-git-dir-fingerprint")
        with mock.patch.object(C09, "_git", return_value=None), mock.patch.object(C09, "_find_marker_upwards", return_value=None):
            with self.assertRaises(C09.PolicyError): C09.resolve_repo_root(None, {})

    def test_root_resolution_and_path_guards(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            root = Path(td).resolve(); fx.make_repo(root)
            resolved, source, evidence = C09.resolve_repo_root(str(root), {"CLAUDE_PROJECT_DIR": str(root)})
            self.assertEqual(resolved, root); self.assertTrue(evidence["host_boundary_match"])
            with self.assertRaises(C09.PolicyError):
                C09.resolve_repo_root(str(root), {"CLAUDE_PROJECT_DIR": str(Path(other).resolve())})
            with self.assertRaises(C09.PolicyError): C09.resolve_repo_root("/definitely/missing", {})
            for bad in ("", "../x", "/tmp/x", "bad\x00path"):
                with self.assertRaises(C09.PolicyError): C09.guard_relative_path(root, bad)
            self.assertTrue(str(C09.guard_relative_path(root, "new/path")).startswith(str(root)))
            outside = Path(other).resolve(); (outside / "x").write_text("x", encoding="utf-8")
            (root / "escape").symlink_to(outside)
            with self.assertRaises(C09.PolicyError): C09.guard_relative_path(root, "escape/x")

    def test_config_identity_sections_and_main(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); fx.make_repo(root); env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            context = C09.build_context(["--repo-root", str(root)], env)
            self.assertEqual(context["repository_id"], C09.derive_repository_id(root)[0])
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(C09.main(["--repo-root", str(root)]), 0)
            config_path = root / ".dev-graph/config.json"; config = json.loads(config_path.read_text())
            config["repository_id"] = C09.SENTINEL_REPOSITORY_ID; fx.dump(config_path, config)
            with self.assertRaises(C09.PolicyError): C09.build_context(["--repo-root", str(root)], env)
            config["repository_id"] = C09.derive_repository_id(root)[0]; config.pop("plan_roots"); fx.dump(config_path, config)
            with self.assertRaises(C09.PolicyError): C09.build_context(["--repo-root", str(root)], env)

    def test_feature_context_is_schema_identity_and_containment_bound(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            root = Path(td).resolve(); fx.make_repo(root)
            (root / "features").mkdir(); (root / "architecture/a.md").write_text("# A\n", encoding="utf-8")
            context_path = root / "features/feature.json"
            valid = {
                "graph_node_id": "F-1", "artifact_kind": "feature",
                "purpose": "purpose", "goal": "goal", "scope_in": ["in"],
                "scope_out": ["out"], "acceptance": ["accepted"],
                "architecture_refs": ["architecture/a.md"],
                "updated_at": "2026-07-13T00:00:00Z",
            }
            fx.dump(context_path, valid)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            result = C09.build_context([
                "--repo-root", str(root), "--feature-id", "F-1",
                "--feature-context", "features/feature.json",
            ], env)
            self.assertEqual(result["feature_context"]["graph_node_id"], "F-1")
            self.assertEqual(len(result["feature_context"]["sha256"]), 64)
            with self.assertRaises(C09.PolicyError):
                C09.build_context(["--repo-root", str(root), "--feature-id", "F-2",
                                   "--feature-context", "features/feature.json"], env)
            valid["unexpected"] = True; fx.dump(context_path, valid)
            with self.assertRaises(C09.PolicyError):
                C09.build_context(["--repo-root", str(root), "--feature-id", "F-1",
                                   "--feature-context", "features/feature.json"], env)
            outside = Path(other).resolve(); (outside / "a.md").write_text("x", encoding="utf-8")
            (root / "architecture/escape").symlink_to(outside)
            valid.pop("unexpected"); valid["architecture_refs"] = ["architecture/escape/a.md"]
            fx.dump(context_path, valid)
            with self.assertRaises(C09.PolicyError):
                C09.build_context(["--repo-root", str(root), "--feature-id", "F-1",
                                   "--feature-context", "features/feature.json"], env)

    def test_missing_and_invalid_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            with self.assertRaises(C09.UsageError): C09.load_config(root, ".dev-graph/config.json")
            (root / ".dev-graph").mkdir(); (root / ".dev-graph/config.json").write_text("{", encoding="utf-8")
            with self.assertRaises(C09.UsageError): C09.load_config(root, ".dev-graph/config.json")


class ValidatorCoverageTests(unittest.TestCase):
    def test_schema_keyword_negative_branches(self):
        cases = [
            (1, {"type": "string"}),
            ("", {"type": "string", "minLength": 1}),
            ("xx", {"type": "string", "maxLength": 1}),
            ("x", {"type": "string", "pattern": "^y$"}),
            ("bad", {"type": "string", "format": "date-time"}),
            (-1, {"type": "number", "minimum": 0}),
            (2, {"type": "number", "maximum": 1}),
            ([1], {"type": "array", "minItems": 2}),
            ([1, 2], {"type": "array", "maxItems": 1}),
            ([1, 1], {"type": "array", "uniqueItems": True}),
            ({}, {"type": "object", "minProperties": 1}),
            ({"a": 1, "b": 2}, {"type": "object", "maxProperties": 1}),
        ]
        for value, schema in cases:
            self.assertTrue(VALIDATOR.schema_violations(value, schema), (value, schema))
        with self.assertRaises(ValueError): VALIDATOR.schema_violations({}, {"$ref": "other.json"})
        with self.assertRaises(ValueError): VALIDATOR._resolve_local_ref({}, "#/$defs/missing")

    def test_main_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); repository_id = fx.make_repo(root); staging, _ = fx.make_fixture(root, repository_id)
            env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
            code, stdout, _ = invoke(VALIDATOR, ["--repo-root", str(root), "--staging", ".dev-graph/staging/run-1"], env)
            self.assertEqual(code, 0); self.assertEqual(json.loads(stdout)["status"], "pass")
            (staging / "task-specs/phase-01-requirements.md").write_text("TODO", encoding="utf-8")
            code, stdout, _ = invoke(VALIDATOR, ["--repo-root", str(root), "--staging", ".dev-graph/staging/run-1"], env)
            self.assertEqual(code, 2); self.assertEqual(json.loads(stdout)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
