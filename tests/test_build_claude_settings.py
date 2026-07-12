import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-claude-settings.py"
SPEC = importlib.util.spec_from_file_location("build_claude_settings", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildClaudeSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugins = self.root / "plugins"
        self.target = self.root / ".claude" / "settings.json"
        self.plugins.mkdir()
        self.target.parent.mkdir()
        self.write_target(
            {
                "permissions": {"deny": ["Bash(git push --force*)"], "ask": []},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Write",
                            "hooks": [
                                {"type": "command", "command": "python3 user-hook.py"}
                            ],
                        }
                    ]
                },
                "unknown": {"keep": True},
            }
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write_target(self, data):
        self.target.write_text(MODULE.serialize(data), encoding="utf-8")

    def plugin(self, name, hooks=None, permissions=None):
        plugin_dir = self.plugins / name
        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        manifest = {"name": name}
        if hooks is not None:
            manifest["hooks"] = hooks
        if permissions is not None:
            manifest["permissions"] = permissions
        (manifest_dir / "plugin.json").write_text(
            MODULE.serialize(manifest), encoding="utf-8"
        )
        return plugin_dir

    def hook(self, command, matcher="Write|Edit", event="PreToolUse"):
        return {
            event: [
                {
                    "matcher": matcher,
                    "hooks": [{"type": "command", "command": command}],
                }
            ]
        }

    def run_cli(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--plugins-dir",
                str(self.plugins),
                "--target",
                str(self.target),
                *args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_help_matches_contract_usage(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            """usage: build-claude-settings.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target TARGET]
                                [--dry-run]
                                [--check]
                                [--print-user-section-hash]
                                [--json]
                                [--verbose]
""",
        )

    def test_inv1_user_section_byte_equality(self):
        before = MODULE.user_section_sha256(MODULE.load_target(self.target))
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        after = MODULE.user_section_sha256(MODULE.load_target(self.target))
        self.assertEqual(before, after)

    def test_inv2_deterministic_output(self):
        self.plugin("beta", hooks=self.hook("python3 beta.py"))
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        first = self.run_cli("--dry-run", "--json")
        second = self.run_cli("--dry-run", "--json")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_inv3_idempotent(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        first = self.run_cli()
        second = self.run_cli()
        check = self.run_cli("--check")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_inv4_plugin_name_lex_order(self):
        self.plugin("beta", hooks=self.hook("python3 beta.py"))
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = MODULE.load_target(self.target)
        managed = data["_build_claude_settings"]["managed_hooks"]
        self.assertEqual([item["from_plugin"] for item in managed], ["alpha", "beta"])

    def test_inv5_conflict_raises_exit2(self):
        shared = self.hook("python3 shared.py")
        self.plugin("alpha", hooks=shared)
        self.plugin("beta", hooks=shared)
        before = self.target.read_text(encoding="utf-8")

        result = self.run_cli("--json")

        self.assertEqual(result.returncode, 2)
        self.assertIn('"conflict"', result.stdout)
        self.assertEqual(before, self.target.read_text(encoding="utf-8"))

    def test_inv6_unknown_top_level_preserved(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(MODULE.load_target(self.target)["unknown"], {"keep": True})

    def test_inv7_json_normalization(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.target.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))
        self.assertIn('\n  "_build_claude_settings": {', content)
        self.assertEqual(json.loads(content), MODULE.load_target(self.target))

    def test_inv8_atomic_write_failure_keeps_original(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))
        original = self.target.read_text(encoding="utf-8")

        with mock.patch.object(MODULE.os, "rename", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                MODULE.atomic_write(self.target, MODULE.serialize({"changed": True}))

        self.assertEqual(original, self.target.read_text(encoding="utf-8"))

    def test_inv9_namespace_conflict_exit2(self):
        first = self.plugin("alpha")
        second = self.plugin("beta")
        for root in (first, second):
            skill = root / "skills" / "shared"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

        result = self.run_cli("--json")

        self.assertEqual(result.returncode, 2)
        self.assertIn('"type": "skill"', result.stdout)

    def test_inv10_settings_structure_validation(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = MODULE.load_target(self.target)
        self.assertIsInstance(data["permissions"], dict)
        self.assertIsInstance(data["hooks"], dict)
        for entries in data["hooks"].values():
            for entry in entries:
                self.assertIsInstance(entry["hooks"], list)

    def test_inv11_permissions_dedupe_and_conflict(self):
        self.plugin("alpha", permissions={"deny": ["Bash(rm -rf*)"]})
        self.plugin("beta", permissions={"deny": ["Bash(rm -rf*)"]})

        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"dedupe": 1', result.stdout)

        self.tearDown()
        self.setUp()
        self.plugin("alpha", permissions={"deny": ["Bash(rm -rf*)"]})
        self.plugin("beta", permissions={"ask": ["Bash(rm -rf*)"]})
        conflict = self.run_cli("--json")
        self.assertEqual(conflict.returncode, 2)

    def test_inv12_plan_completeness(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        for key in ("namespace", "settings", "conflicts", "invariants_checked"):
            self.assertIn(key, plan)
        self.assertEqual(plan["invariants_checked"], MODULE.INVARIANTS)

    def test_check_reports_drift_exit1(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli("--check")

        self.assertEqual(result.returncode, 1)

    def test_print_user_section_hash(self):
        result = self.run_cli("--print-user-section-hash")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.strip()), 64)

    def test_invalid_plugin_layout_exit3(self):
        (self.plugins / "broken").mkdir()

        result = self.run_cli()

        self.assertEqual(result.returncode, 3)


if __name__ == "__main__":
    unittest.main()
