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
                                [--exclude-plugin PLUGIN]
                                [--dry-run]
                                [--check]
                                [--print-user-section-hash]
                                [--json]
                                [--verbose]
""",
        )

    def test_exclude_plugin_is_repeatable_and_removes_managed_source(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))
        self.plugin("beta", hooks=self.hook("python3 beta.py"))
        self.plugin("gamma", hooks=self.hook("python3 gamma.py"))

        result = self.run_cli(
            "--dry-run", "--json",
            "--exclude-plugin", "alpha",
            "--exclude-plugin", "gamma",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["plugins"], ["beta"])
        self.assertEqual(plan["excluded_plugins"], ["alpha", "gamma"])
        self.assertEqual(plan["settings"]["hooks"], [])

    def test_excluded_malformed_plugin_is_not_a_managed_source(self):
        malformed = self.plugins / "disabled"
        malformed.mkdir()
        self.plugin("enabled", hooks=self.hook("python3 enabled.py"))

        result = self.run_cli("--check", "--exclude-plugin", "disabled")

        # The valid enabled plugin still causes ordinary drift; the excluded
        # malformed directory must not turn that into invalid-layout exit 3.
        self.assertEqual(result.returncode, 1, result.stderr)

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

    def test_plugin_delivered_hooks_are_pruned_from_project_settings(self):
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))
        self.write_target(
            {
                "_build_claude_settings": {
                    "managed_hooks": [
                        {
                            "event": "PreToolUse",
                            "matcher": "Write|Edit",
                            "command": "python3 stale-plugin-hook.py",
                            "from_plugin": "alpha",
                        }
                    ],
                    "managed_permissions": [],
                },
                "permissions": {"deny": [], "ask": []},
                "hooks": {
                    "PreToolUse": [
                        self.hook("python3 stale-plugin-hook.py")["PreToolUse"][0],
                        self.hook("python3 user-hook.py", matcher="Write")["PreToolUse"][0],
                    ]
                },
            }
        )

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = MODULE.load_target(self.target)
        self.assertEqual(data["_build_claude_settings"]["managed_hooks"], [])
        commands = [
            command["command"]
            for group in data["hooks"]["PreToolUse"]
            for command in group["hooks"]
        ]
        self.assertEqual(commands, ["python3 user-hook.py"])

    def test_inv4_plugin_hooks_are_not_project_managed(self):
        self.plugin("beta", hooks=self.hook("python3 beta.py"))
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = MODULE.load_target(self.target)
        managed = data["_build_claude_settings"]["managed_hooks"]
        self.assertEqual(managed, [])

    def test_inv5_shared_plugin_hook_is_outside_project_conflict_scope(self):
        shared = self.hook("python3 shared.py")
        self.plugin("alpha", hooks=shared)
        self.plugin("beta", hooks=shared)
        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["settings"]["hooks"], [])
        self.assertEqual([c for c in plan["conflicts"] if c["type"] == "hook"], [])

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
        for root, body in ((first, "# Alpha\n"), (second, "# Beta\n")):
            skill = root / "skills" / "shared"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(body, encoding="utf-8")

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

    def test_target_unknown_hook_event_preserved(self):
        # 互換修復 (正側): target が持つ未知 hook event (この script の HOOK_EVENTS
        # allowlist に無い新しい Claude Code event) は exit3 で落とさず非破壊 preserve する。
        self.write_target(
            {
                "permissions": {"deny": [], "ask": []},
                "hooks": {
                    "FileChanged": [
                        {
                            "matcher": "SKILL.md",
                            "hooks": [
                                {"type": "command", "command": "python3 user-fc.py"}
                            ],
                        }
                    ]
                },
            }
        )
        self.plugin("alpha", hooks=self.hook("python3 alpha.py"))

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = MODULE.load_target(self.target)
        self.assertIn("FileChanged", data["hooks"])
        self.assertEqual(
            data["hooks"]["FileChanged"][0]["hooks"][0]["command"],
            "python3 user-fc.py",
        )
        # 再 check は drift なし (idempotent)。
        check = self.run_cli("--check")
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_managed_source_unknown_hook_event_blocked_exit3(self):
        # 互換修復 (負側=非対称性): managed source (plugin manifest) が未知 event を
        # 宣言したら従来どおり fail-closed で block する (target preserve に巻き込まない)。
        self.write_target({"permissions": {"deny": [], "ask": []}, "hooks": {}})
        self.plugin(
            "alpha",
            hooks={
                "FileChanged": [
                    {"hooks": [{"type": "command", "command": "python3 alpha-fc.py"}]}
                ]
            },
        )

        result = self.run_cli()

        self.assertEqual(result.returncode, 3)
        self.assertIn("unknown hook event", result.stderr)

    def test_symlink_shared_skill_is_not_conflict(self):
        # 複数 plugin が同名 skill を symlink で 1 実体から共有する場合は、
        # 名前衝突ではなく共有 (shared) として dedupe し exit2 にしない。
        alpha = self.plugin("alpha")
        real_skill = alpha / "skills" / "run-shared"
        real_skill.mkdir(parents=True)
        (real_skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
        beta = self.plugin("beta")
        (beta / "skills").mkdir(parents=True)
        os.symlink(real_skill, beta / "skills" / "run-shared")

        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual([c for c in plan["conflicts"] if c["type"] == "skill"], [])
        shared = [s for s in plan["namespace"]["skills"] if s.get("verdict") == "shared"]
        self.assertTrue(shared)

    def test_byte_identical_physical_skill_copies_are_shared(self):
        # Plugin 単独 install を自己完結させる実体コピーは shared として dedupe。
        for name in ("alpha", "beta"):
            root = self.plugin(name)
            skill = root / "skills" / "run-shared"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual([c for c in plan["conflicts"] if c["type"] == "skill"], [])

    def test_distinct_content_same_name_still_conflicts(self):
        for name, text in (("alpha", "# Alpha\n"), ("beta", "# Beta\n")):
            root = self.plugin(name)
            skill = root / "skills" / "run-shared"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(text, encoding="utf-8")

        result = self.run_cli("--json")

        self.assertEqual(result.returncode, 2)
        self.assertIn('"type": "skill"', result.stdout)

    def test_plugin_root_normalization_keeps_plugin_diagnostics_distinct(self):
        self.plugin(
            "alpha",
            hooks=self.hook("python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py", matcher="Bash"),
        )
        self.plugin(
            "beta",
            hooks=self.hook("python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py", matcher="Bash"),
        )

        plugins = MODULE.discover_plugins(self.plugins, project_root=self.root)
        commands = [hook["command"] for plugin in plugins for hook in plugin["hooks"]]
        self.assertTrue(all("CLAUDE_PLUGIN_ROOT" not in c for c in commands))
        self.assertTrue(any("${CLAUDE_PROJECT_DIR}" in c and "alpha" in c for c in commands))
        self.assertTrue(any("${CLAUDE_PROJECT_DIR}" in c and "beta" in c for c in commands))

    def test_plugin_root_expansion_is_repo_relative_and_relocatable(self):
        command = MODULE.expand_plugin_root(
            "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py",
            "plugins/alpha",
        )
        self.assertEqual(
            command,
            "python3 ${CLAUDE_PROJECT_DIR}/plugins/alpha/hooks/guard.py",
        )
        clone = self.root / "different-clone"
        expected = clone / "plugins" / "alpha" / "hooks" / "guard.py"
        expected.parent.mkdir(parents=True)
        expected.write_text("# hook\n", encoding="utf-8")
        self.assertTrue(
            Path(command.split("${CLAUDE_PROJECT_DIR}/", 1)[1].split()[0])
            == Path("plugins/alpha/hooks/guard.py")
        )
        self.assertTrue(expected.is_file())

    def test_same_plugin_inline_and_hook_file_are_not_projected(self):
        plugin = self.plugin(
            "alpha",
            hooks=self.hook("python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py", matcher="Bash"),
        )
        hooks_dir = plugin / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "hooks.json").write_text(
            MODULE.serialize(
                {"hooks": self.hook("python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py", matcher="Bash")}
            ),
            encoding="utf-8",
        )

        result = self.run_cli("--dry-run", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["settings"]["hooks"], [])

    def test_dual_root_and_claude_root_normalize_to_one_project_hook(self):
        claude = MODULE.expand_plugin_root(
            "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py",
            "plugins/alpha",
        )
        dual = MODULE.expand_plugin_root(
            "python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/guard.py",
            "plugins/alpha",
        )
        self.assertEqual(
            claude,
            "python3 ${CLAUDE_PROJECT_DIR}/plugins/alpha/hooks/guard.py",
        )
        self.assertEqual(dual, claude)


if __name__ == "__main__":
    unittest.main()
