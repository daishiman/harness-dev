from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common
import test_build_graph_node as fixtures
import test_register_package as package_fixtures


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INIT = load_script("dev_graph_init_regression", "build-init-scaffold.py")
PROJECTS = load_script("dev_graph_projects_regression", "diff-github-project-fields.py")
ISSUES = load_script("dev_graph_issues_regression", "diff-github-issues.py")
RP = package_fixtures.RP
BGN = fixtures.BGN
STAMP = fixtures.STAMP


def github_task() -> dict:
    node = package_fixtures.task_node(0)
    node.update(parent_feature=None, feature_package_id=None, phase_ref=None,
                tracker_binding="github", priority="medium")
    node["github_publication"]["mode"] = "issue"
    return node


def project_inputs(values: tuple[str, str] = ("P1", "P3")) -> tuple[dict, dict, dict]:
    config = json.loads((PLUGIN / "templates" / "repo-config.example.json").read_text())
    projects, links = [], []
    remote = {"projects": {}}
    for index, (alias, value) in enumerate(zip(("a", "b"), values)):
        project = copy.deepcopy(fixtures.ROADMAP)
        project.update(alias=alias, default=index == 0, project_number=7 + index)
        project["field_mappings"] = project["field_mappings"][1:]
        projects.append(project)
        links.append(fixtures.roadmap_link(
            project_alias=alias, project_number=7 + index, project_id="PVT_" + alias,
            item_id="PVTI_" + alias, sync_state="synced", field_snapshot={"priority": "P2"}))
        project_remote = fixtures.roadmap_remote(priority=value)["projects"]["roadmap"]
        project_remote.update(id="PVT_" + alias, items={"PVTI_" + alias: {"Priority": value}})
        remote["projects"][alias] = project_remote
    config["github"]["projects"] = projects
    node = github_task()
    node["github_project_linkages"] = links
    return {"graph_revision": 1, "nodes": [node]}, config, remote


class SharedAtomicWriteTest(unittest.TestCase):
    def test_create_only_preserves_bytes_and_replace_updates_them_without_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            target = root / "receipt.json"
            common.atomic_json(target, {"日本語": True}, create_only=True)
            original = target.read_bytes()
            self.assertTrue(original.endswith(b"\n"))
            with self.assertRaises(FileExistsError):
                common.atomic_json(target, {"changed": True}, create_only=True)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(root.iterdir()), [target])
            common.atomic_bytes(target, b"replacement\n")
            self.assertEqual(target.read_bytes(), b"replacement\n")
            with mock.patch.object(common.os, "link", side_effect=OSError("link failure")):
                with self.assertRaisesRegex(OSError, "link failure"):
                    common.atomic_json(root / "new.json", {}, create_only=True)
            self.assertEqual(list(root.iterdir()), [target])

    def test_writer_wrappers_keep_their_domain_errors_and_immutable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "existing.json"
            target.write_bytes(b"existing bytes\n")
            with self.assertRaises(INIT.InitError) as error:
                INIT._create_file(target, b"new")
            self.assertEqual(error.exception.code, "path_appeared_during_init")
            with self.assertRaises(BGN.WriterError) as error:
                BGN._write_atomic(target, b"new", create_only=True)
            self.assertEqual(error.exception.code, "artifact_path_exists")
            with self.assertRaises(BGN.WriterError) as error:
                BGN._create_receipt(target, {})
            self.assertEqual(error.exception.code, "immutable_receipt_exists")
            with self.assertRaisesRegex(common.ContractError, "immutable receipt already exists"):
                RP._atomic_create_json(target, {})
            self.assertEqual(target.read_bytes(), b"existing bytes\n")
            self.assertEqual(list(target.parent.iterdir()), [target])


class InitRollbackTest(unittest.TestCase):
    def context(self, root: Path) -> dict:
        example = json.loads((PLUGIN / "templates" / "repo-config.example.json").read_text())
        return {"repo_root": str(root), "repository_id": "local:sha256:" + "a" * 64,
                "content_roots": {"repository": str(root),
                                  **{key: str(root / value) for key, value in example["content_roots"].items()}},
                "local_state_paths": {"config": str(root / ".dev-graph/config.json"),
                                      **{key: str(root / value) for key, value in example["local_state"].items()}}}

    def snapshot(self, root: Path) -> dict:
        return {path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
                for path in root.rglob("*")}

    def test_receipt_failure_restores_all_created_parents_and_preserves_existing_state(self) -> None:
        for existing_state in (False, True):
            with self.subTest(existing_state=existing_state), tempfile.TemporaryDirectory() as raw:
                root = Path(raw).resolve()
                if existing_state:
                    (root / ".dev-graph/state").mkdir(parents=True)
                    (root / ".dev-graph/state/existing.txt").write_bytes(b"preserved\n")
                before = self.snapshot(root)
                original_link = common.os.link

                def fail_receipt(source, target):
                    if Path(target).name.startswith("init-"):
                        raise OSError("receipt failure")
                    return original_link(source, target)

                with mock.patch.object(INIT, "_context", return_value=self.context(root)), \
                        mock.patch.object(common.os, "link", side_effect=fail_receipt):
                    with self.assertRaisesRegex(OSError, "receipt failure"):
                        INIT.scaffold(argparse.Namespace(repo_root=str(root), config=".dev-graph/config.json",
                                                         dry_run=False, hook_source="plugin"))
                self.assertEqual(self.snapshot(root), before)

    def test_incomplete_rollback_reports_remaining_paths_instead_of_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            original_link, original_unlink = common.os.link, Path.unlink

            def fail_receipt(source, target):
                if Path(target).name.startswith("init-"):
                    raise OSError("receipt failure")
                return original_link(source, target)

            def fail_config_unlink(path, *args, **kwargs):
                if path == root / ".dev-graph/config.json":
                    raise PermissionError("config restore blocked")
                return original_unlink(path, *args, **kwargs)

            output = io.StringIO()
            with mock.patch.object(INIT, "_context", return_value=self.context(root)), \
                    mock.patch.object(common.os, "link", side_effect=fail_receipt), \
                    mock.patch.object(Path, "unlink", fail_config_unlink), redirect_stdout(output):
                code = INIT.main(["--repo-root", str(root)])
            report = json.loads(output.getvalue())
            self.assertEqual((code, report["code"], report["write_count"]), (1, "rollback_incomplete", None))
            self.assertIn(".dev-graph/config.json", [row["node"] for row in report["findings"]])
            self.assertFalse((root / ".dev-graph/state").exists())


class ProjectImportJoinTest(unittest.TestCase):
    def test_conflicting_project_imports_are_all_conflicts_without_any_write_in_either_order(self) -> None:
        graph, config, remote = project_inputs()
        self.assertEqual(BGN.VGS.schema_findings(config, common.load_json(PLUGIN / "schemas/repo-config.schema.json"), 0), [])
        self.assertEqual(BGN.VGS.schema_findings(graph["nodes"][0], common.load_json(PLUGIN / "schemas/graph-node.schema.json"), 0), [])
        first = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        graph["nodes"][0]["github_project_linkages"].reverse()
        second = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        for report in (first, second):
            self.assertEqual((report["imports"], report["exports"], report["update_input"], report["link_input"]),
                             ([], [], None, None))
            self.assertEqual([row["kind"] for row in report["conflicts"]], ["cross-project-import"] * 2)
            self.assertEqual((report["changes"], report["unresolved_count"], report["converged"]), (0, 2, False))
        self.assertEqual(first["conflicts"], second["conflicts"])

    def test_equal_project_imports_are_one_order_independent_patch_with_both_origins(self) -> None:
        graph, config, remote = project_inputs(("P1", "P1"))
        first = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        graph["nodes"][0]["github_project_linkages"].reverse()
        second = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        self.assertEqual(first["imports"], second["imports"])
        self.assertEqual(len(first["imports"]), 1)
        self.assertEqual(first["imports"][0]["source_projects"], ["a", "b"])
        self.assertEqual(first["update_input"]["updates"][0]["node_patch"], {"priority": "high"})
        self.assertEqual(first["conflicts"], [])


class SyncProgressTest(unittest.TestCase):
    def test_missing_conflicted_or_flagged_issues_are_not_converged(self) -> None:
        node = github_task()
        node["issue_linkage"] = {"repo": "acme/web", "issue_number": 12}
        graph = {"graph_revision": 1, "nodes": [node]}
        cases = [("missing_issues", {"issues": {}}),
                 ("conflicts", fixtures.issue_remote("new title", None)),
                 ("confirmations", fixtures.issue_remote("new title", node["updated_at"]))]
        for key, remote in cases:
            with self.subTest(key=key):
                report = ISSUES.plan(graph, {}, remote, {})
                self.assertEqual((report["changes"], report["unresolved_count"], report["converged"]), (0, 1, False))
                self.assertEqual(len(report[key]), 1)
                self.assertNotEqual(report["next"], "converged")
        report = ISSUES.plan(graph, {}, fixtures.issue_remote(node["title"], node["updated_at"]), {})
        self.assertEqual((report["converged"], report["unresolved_count"], report["next"]), (True, 0, "converged"))

    def test_missing_skipped_and_persistent_project_conflicts_are_not_converged(self) -> None:
        graph, config, remote = project_inputs()
        missing = PROJECTS.plan(graph, config["github"], {"projects": {}}, {}, STAMP)
        self.assertEqual((missing["changes"], missing["unresolved_count"], missing["converged"]), (0, 2, False))
        for link in graph["nodes"][0]["github_project_linkages"]:
            link["sync_state"] = "pending_retry"
        skipped = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        self.assertEqual((skipped["changes"], skipped["unresolved_count"], skipped["converged"]), (0, 2, False))
        graph["nodes"][0]["priority"] = "low"
        for link in graph["nodes"][0]["github_project_linkages"]:
            link["sync_state"] = "conflict"
        remote["projects"]["b"]["items"]["PVTI_b"]["Priority"] = "P1"
        conflict = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        self.assertEqual((conflict["changes"], conflict["unresolved_count"], conflict["converged"]), (0, 2, False))
        self.assertNotEqual(conflict["next"], "converged")
        graph["nodes"][0]["priority"] = "high"
        for link in graph["nodes"][0]["github_project_linkages"]:
            link.update(sync_state="synced", field_snapshot={"priority": "P1"})
        converged = PROJECTS.plan(graph, config["github"], remote, {}, STAMP)
        self.assertEqual((converged["converged"], converged["next"]), (True, "converged"))

    def test_execution_context_heartbeat_keeps_remote_newer_issue_content_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            node = github_task()
            node["issue_linkage"] = {"repo": "acme/web", "issue_number": 12,
                                     "issue_url": "https://github.com/acme/web/issues/12", "linked_at": node["updated_at"]}
            graph = {"graph_revision": 1, "nodes": [node]}
            common.atomic_json(root / "graph.json", graph)
            remote = fixtures.issue_remote("New remote title", "2026-07-13T00:01:00Z")
            before = ISSUES.plan(graph, {}, remote, {})
            context = package_fixtures.RegisterPackageInProcessCoverageTest.execution_context(
                seen="2026-07-13T00:02:00Z")
            args = RP._parser().parse_args([
                "execution-context", "--repo-root", str(root), "--graph", "graph.json",
                "--graph-node-id", node["graph_node_id"], "--context-json", json.dumps(context)])
            RP._project_execution_context(args)
            updated = common.load_json(root / "graph.json")
            after = ISSUES.plan(updated, {}, remote, {})
            self.assertEqual(updated["nodes"][0]["updated_at"], node["updated_at"])
            self.assertEqual(updated["nodes"][0]["title"], node["title"])
            self.assertEqual(updated["nodes"][0]["execution_contexts"], [context])
            self.assertEqual(updated["graph_revision"], 2)
            self.assertEqual(before["imports"], after["imports"])
            self.assertEqual(after["exports"], [])


if __name__ == "__main__":
    unittest.main()
