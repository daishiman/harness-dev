import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-claude-symlinks.py"
SPEC = importlib.util.spec_from_file_location("build_claude_symlinks", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildClaudeSymlinksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugins = self.root / "plugins"
        self.target = self.root / ".claude"
        self.plugins.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def skill(self, plugin, name, frontmatter_name=None):
        skill_dir = self.plugins / plugin / "skills" / name
        skill_dir.mkdir(parents=True)
        header = "---\n"
        if frontmatter_name:
            header += f"name: {frontmatter_name}\n"
        header += "---\n"
        (skill_dir / "SKILL.md").write_text(header + "# Skill\n", encoding="utf-8")
        return skill_dir

    def run_cli(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--plugins-dir",
                str(self.plugins),
                "--target-dir",
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
            """usage: build-claude-symlinks.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target-dir TARGET_DIR]
                                [--kinds KINDS]
                                [--dry-run]
                                [--check]
                                [--prune]
                                [--exclude-plugin PLUGIN]
                                [--conflicts-only]
                                [--json]
""",
        )

    def test_single_plugin_single_skill_create(self):
        src = self.skill("alpha", "demo")

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        dst = self.target / "skills" / "demo"
        self.assertTrue(dst.is_symlink())
        self.assertEqual(os.readlink(dst), os.path.relpath(src, dst.parent))

    def test_existing_matching_symlink_noop(self):
        src = self.skill("alpha", "demo")
        dst = self.target / "skills" / "demo"
        dst.parent.mkdir(parents=True)
        dst.symlink_to(os.path.relpath(src, dst.parent))

        plan = MODULE.compute_plan(self.plugins, self.target, ["skills"])

        self.assertEqual(plan[0]["action"], "noop")

    def test_existing_wrong_symlink_updates(self):
        src = self.skill("alpha", "demo")
        other = self.skill("alpha", "other")
        dst = self.target / "skills" / "demo"
        dst.parent.mkdir(parents=True)
        dst.symlink_to(os.path.relpath(other, dst.parent))

        result = self.run_cli("--kinds", "skills")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(dst), os.path.relpath(src, dst.parent))

    def test_existing_wrong_symlink_is_atomically_replaced(self):
        src = self.skill("alpha", "demo")
        other = self.skill("alpha", "other")
        dst = self.target / "skills" / "demo"
        dst.parent.mkdir(parents=True)
        old_target = os.path.relpath(other, dst.parent)
        dst.symlink_to(old_target)
        plan = MODULE.compute_plan(self.plugins, self.target, ["skills"])
        real_replace = MODULE.os.replace
        observed = {}

        def inspect_replace(temp, destination):
            if Path(destination) == dst:
                observed["old_visible"] = os.readlink(destination) == old_target
                observed["temp_is_link"] = Path(temp).is_symlink()
            return real_replace(temp, destination)

        with mock.patch.object(MODULE.os, "replace", side_effect=inspect_replace):
            MODULE.apply_plan(plan)

        self.assertEqual(observed, {"old_visible": True, "temp_is_link": True})
        self.assertEqual(os.readlink(dst), os.path.relpath(src, dst.parent))
        self.assertFalse(any(".tmp." in p.name for p in dst.parent.iterdir()))

    def test_duplicate_skill_names_conflict_exit_2(self):
        self.skill("alpha", "demo")
        self.skill("beta", "demo")

        result = self.run_cli("--kinds", "skills")

        self.assertEqual(result.returncode, 2)
        self.assertIn("conflict", result.stdout)

    def test_exclude_plugin_avoids_duplicate_skill_conflict(self):
        src = self.skill("slide-report-generator", "run-slide-report-generate")
        self.skill("slide-report-generator-v2", "run-slide-report-generate")

        result = self.run_cli(
            "--kinds",
            "skills",
            "--exclude-plugin",
            "slide-report-generator-v2",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        dst = self.target / "skills" / "run-slide-report-generate"
        self.assertTrue(dst.is_symlink())
        self.assertEqual(os.readlink(dst), os.path.relpath(src, dst.parent))

    def test_conflicts_only_ignores_missing_symlink_drift(self):
        self.skill("alpha", "demo")

        result = self.run_cli("--kinds", "skills", "--check", "--conflicts-only")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("created=1", result.stdout)

    def test_duplicate_skill_frontmatter_names_conflict_exit_2(self):
        self.skill("alpha", "first", frontmatter_name="shared")
        self.skill("beta", "second", frontmatter_name="shared")

        result = self.run_cli("--kinds", "skills")

        self.assertEqual(result.returncode, 2)

    def test_existing_real_file_conflict(self):
        self.skill("alpha", "demo")
        dst = self.target / "skills" / "demo"
        dst.parent.mkdir(parents=True)
        dst.write_text("not a symlink", encoding="utf-8")

        result = self.run_cli("--kinds", "skills")

        self.assertEqual(result.returncode, 2)
        self.assertFalse(dst.is_symlink())

    def test_dry_run_does_not_change_filesystem(self):
        self.skill("alpha", "demo")

        result = self.run_cli("--kinds", "skills", "--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / "skills" / "demo").exists())
        self.assertIn('"plan"', result.stdout)
        self.assertIn('"summary"', result.stdout)

    def test_idempotent_second_run_is_noop_and_check_clean(self):
        self.skill("alpha", "demo")

        first = self.run_cli("--kinds", "skills", "--json")
        second = self.run_cli("--kinds", "skills", "--json")
        check = self.run_cli("--kinds", "skills", "--check")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('"created": 1', first.stdout)
        self.assertIn('"noop": 1', second.stdout)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_check_reports_broken_orphan_symlink_as_drift(self):
        orphan = self.target / "skills" / "gone"
        orphan.parent.mkdir(parents=True)
        orphan.symlink_to("../missing")

        result = self.run_cli("--kinds", "skills", "--check")

        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
