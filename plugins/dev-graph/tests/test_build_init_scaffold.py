from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "build-init-scaffold.py"
VALIDATOR = PLUGIN / "scripts" / "validate-graph-schema.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("dev_graph_validate_graph_schema_for_init", VALIDATOR)
assert SPEC and SPEC.loader
VGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VGS)
CONFIG_SCHEMA = json.loads((PLUGIN / "schemas" / "repo-config.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((PLUGIN / "templates" / "repo-config.example.json").read_text(encoding="utf-8"))
CONTENT_KEYS = ("issues", "tasks", "specifications", "architecture", "features", "documents")


class ExampleConfigTest(unittest.TestCase):
    def test_example_config_satisfies_repo_config_schema_and_names_every_content_root(self) -> None:
        self.assertEqual(VGS.schema_findings(EXAMPLE, CONFIG_SCHEMA, 0), [])
        self.assertTrue(set(CONTENT_KEYS) <= set(EXAMPLE["content_roots"]), EXAMPLE["content_roots"])
        self.assertEqual(EXAMPLE["local_state"]["graph"], ".dev-graph/state/graph.json")


class BuildInitScaffoldTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        # C24 は HEAD から repository_id を導くので、commit の無い repo は init 前に拒否される。
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        self.env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
        self.receipts = self.root / ".dev-graph" / "state" / "receipts"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *extra: str) -> tuple[int, dict]:
        cp = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(self.root), *extra],
                            text=True, capture_output=True, env=self.env, check=False)
        return cp.returncode, json.loads(cp.stdout)

    def test_first_run_scaffolds_once_and_rerun_is_noop(self) -> None:
        code, report = self.run_cli("--dry-run")
        self.assertEqual((code, report["status"], report["write_count"]), (0, "preview", 0), report)
        self.assertFalse((self.root / ".dev-graph").exists())
        self.assertFalse(any((self.root / name).exists() for name in report["content_roots"].values()))
        code, report = self.run_cli()
        self.assertEqual((code, report["status"]), (0, "applied"), report)
        self.assertEqual(report["planned_changes"], report["write_count"])
        self.assertEqual(report["local_state"]["graph"], ".dev-graph/state/graph.json")
        for relative in [*report["content_roots"].values(), ".dev-graph/cache", ".dev-graph/locks", ".dev-graph/templates"]:
            self.assertTrue((self.root / relative).is_dir(), relative)
        config = json.loads((self.root / ".dev-graph" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(VGS.schema_findings(config, CONFIG_SCHEMA, 0), [])
        receipt = json.loads((self.root / report["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual((receipt["status"], receipt["created"], receipt["hook_source"]), ("applied", report["created"], "plugin"))
        self.assertTrue({"repository_id", "content_roots", "preserved", "migration_preview", "schema_result"} <= set(receipt))
        graph = self.root / ".dev-graph" / "state" / "graph.json"
        result = subprocess.run([sys.executable, str(VALIDATOR), "--graph", str(graph), "--repo-root", str(self.root)],
                                text=True, capture_output=True, env=self.env, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before = sorted(path.name for path in self.receipts.iterdir())
        code, again = self.run_cli()
        self.assertEqual((code, again["status"], again["planned_changes"], again["write_count"]), (0, "noop", 0, 0), again)
        self.assertEqual(again["receipt_path"], report["receipt_path"])
        self.assertEqual(sorted(path.name for path in self.receipts.iterdir()), before)

    def test_edited_template_is_kept_and_only_missing_parts_are_created(self) -> None:
        self.assertEqual(self.run_cli()[0], 0)
        template = self.root / ".dev-graph" / "templates" / "issue.md"
        template.write_text(template.read_text(encoding="utf-8") + "\n## 社内メモ\n", encoding="utf-8")
        edited = template.read_bytes()
        code, report = self.run_cli()
        self.assertEqual((code, report["status"]), (0, "noop"), report)
        self.assertEqual([item["path"] for item in report["migration_preview"]], [".dev-graph/templates/issue.md"])
        (self.root / "tasks").rmdir()
        code, report = self.run_cli()
        self.assertEqual((code, report["status"], report["created"], report["planned_changes"]), (0, "applied", ["tasks"], 2), report)
        self.assertEqual(template.read_bytes(), edited)
        self.assertEqual(len(list(self.receipts.glob("init-*.json"))), 2)

    def test_existing_config_that_fails_the_schema_stops_before_any_write(self) -> None:
        self.assertEqual(self.run_cli()[0], 0)
        config_path = self.root / ".dev-graph" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["execution_tracker"]["mode"] = "none"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (self.root / "tasks").rmdir()
        code, report = self.run_cli()
        self.assertEqual((code, report["status"], report["code"], report["write_count"]), (1, "rejected", "pre_write_validation_failed", 0))
        self.assertTrue(all(item["node"] == "repo-config" for item in report["findings"]), report["findings"])
        self.assertFalse((self.root / "tasks").exists())
        self.assertEqual(len(list(self.receipts.glob("init-*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
