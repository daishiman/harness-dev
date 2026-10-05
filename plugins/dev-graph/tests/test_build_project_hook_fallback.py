"""C01 OUT5: plugin hook が既定で、project fallback を選んだときだけ既存 `.claude/settings.json` へ追記 merge する。

init (build-init-scaffold) で config を作った実 repo に plain symlink `.claude/dev-graph-plugin` を張り、
user/managed settings は一時 path へ差し替えて、host の実設定を読まない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
INIT = PLUGIN / "scripts" / "build-init-scaffold.py"
SCRIPT = PLUGIN / "scripts" / "build-project-hook-fallback.py"
PLUGIN_HOOKS = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
LINK = ".claude/dev-graph-plugin"
# 利用者が先に書いていた project settings。key 順と既存 hook group をそのまま残せるかを見る。
EXISTING = {
    "permissions": {"allow": ["Bash(ls:*)"]},
    "env": {"FOO": "1"},
    "hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "echo existing"}]}]},
}


def wanted() -> list[tuple[str, str | None, str]]:
    prefix = "${CLAUDE_PROJECT_DIR}/" + LINK
    return [(event, group.get("matcher"), hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", prefix))
            for event, groups in PLUGIN_HOOKS.items() for group in groups for hook in group["hooks"]]


def identities(settings: dict) -> list[tuple[str, str | None, str]]:
    return [(event, group.get("matcher"), hook["command"])
            for event, groups in settings.get("hooks", {}).items() for group in groups for hook in group["hooks"]]


class ProjectHookFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        self.env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
        self.settings = self.root / ".claude" / "settings.json"
        self.local = self.root / ".claude" / "settings.local.json"
        self.user = self.root.parent / "user-settings.json"
        self.managed = self.root.parent / "managed-settings.json"
        self.config = self.root / ".dev-graph" / "config.json"
        self.receipts = self.root / ".dev-graph" / "state" / "receipts"
        self.settings.parent.mkdir()
        self.write(self.settings, EXISTING)
        self.original = self.settings.read_bytes()
        init = subprocess.run([sys.executable, str(INIT), "--repo-root", str(self.root)], text=True,
                              capture_output=True, env=self.env, check=False)
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
        (self.root / LINK).symlink_to(PLUGIN)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def write(path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def run_cli(self, *extra: str) -> tuple[int, dict]:
        cp = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(self.root), "--user-settings", str(self.user),
                             "--managed-settings", str(self.managed), *extra],
                            text=True, capture_output=True, env=self.env, check=False)
        return cp.returncode, json.loads(cp.stdout)

    def manifests(self) -> list[str]:
        return sorted(path.name for path in self.receipts.glob("hook-fallback-*.json"))

    def test_plugin_default_then_fallback_merges_every_event_once_and_keeps_existing_hashes(self) -> None:
        # plugin hook が既定: init は settings に触れず、config は source=plugin のまま。
        self.assertEqual(self.settings.read_bytes(), self.original)
        self.assertEqual(json.loads(self.config.read_text())["claude_hooks"]["source"], "plugin")

        code, preview = self.run_cli()
        self.assertEqual((code, preview["status"], preview["write_count"]), (0, "preview", 0), preview)
        self.assertEqual(len(preview["added"]), len(wanted()))
        self.assertEqual(self.settings.read_bytes(), self.original)
        self.assertEqual(self.manifests(), [])

        code, applied = self.run_cli("--mode", "apply")
        self.assertEqual((code, applied["status"]), (0, "applied"), applied)
        self.assertEqual(applied["preserved"], {"top_level_keys": 2, "hook_groups": 1, "changed": 0,
                                                "duplicate_registrations": 0})
        merged = json.loads(self.settings.read_text())
        self.assertEqual(list(merged), list(EXISTING))
        for key in ("permissions", "env"):
            self.assertEqual(merged[key], EXISTING[key])
        self.assertEqual(merged["hooks"]["PreToolUse"][0], EXISTING["hooks"]["PreToolUse"][0])
        ids = identities(merged)
        self.assertEqual(sorted(ident for ident in ids if ident[2] != "echo existing"), sorted(wanted()))
        self.assertEqual(len(ids), len(set(ids)))
        for _, _, command in wanted():
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", command)
            script = command.split('"')[1].replace("${CLAUDE_PROJECT_DIR}", str(self.root))
            self.assertTrue(Path(script).is_file(), script)
        self.assertEqual(json.loads(self.config.read_text())["claude_hooks"]["source"], "project")
        self.assertEqual(self.manifests(), [Path(applied["manifest_path"]).name])

        code, again = self.run_cli("--mode", "apply")
        self.assertEqual((code, again["status"], again["planned_changes"], again["write_count"]), (0, "noop", 0, 0), again)
        self.assertEqual(len(again["already_present"]), len(wanted()))
        self.assertEqual(self.manifests(), [Path(applied["manifest_path"]).name])

    def test_rollback_restores_exact_bytes_is_idempotent_and_refuses_drift(self) -> None:
        config_before = self.config.read_bytes()
        code, applied = self.run_cli("--mode", "apply")
        self.assertEqual(code, 0, applied)
        code, rolled = self.run_cli("--mode", "rollback", "--manifest", applied["manifest_path"])
        self.assertEqual((code, rolled["status"], rolled["write_count"]), (0, "rolled_back", 2), rolled)
        self.assertEqual(self.settings.read_bytes(), self.original)
        self.assertEqual(self.config.read_bytes(), config_before)
        code, again = self.run_cli("--mode", "rollback", "--manifest", applied["manifest_path"])
        self.assertEqual((code, again["status"], again["write_count"]), (0, "noop", 0), again)

        code, applied = self.run_cli("--mode", "apply")
        self.assertEqual(code, 0, applied)
        drifted = {**json.loads(self.settings.read_text()), "model": "edited-after-apply"}
        self.write(self.settings, drifted)
        edited = self.settings.read_bytes()
        code, refused = self.run_cli("--mode", "rollback", "--manifest", applied["manifest_path"])
        self.assertEqual((code, refused["code"], refused["write_count"]), (1, "rollback_drift", 0), refused)
        self.assertEqual(self.settings.read_bytes(), edited)

    def test_missing_settings_is_created_and_rollback_removes_it(self) -> None:
        self.settings.unlink()
        code, applied = self.run_cli("--mode", "apply")
        self.assertEqual(code, 0, applied)
        self.assertEqual(sorted(identities(json.loads(self.settings.read_text()))), sorted(wanted()))
        code, rolled = self.run_cli("--mode", "rollback", "--manifest", applied["manifest_path"])
        self.assertEqual((code, rolled["status"]), (0, "rolled_back"), rolled)
        self.assertFalse(self.settings.exists())

    def test_plugin_disabled_managed_duplicate_and_link_conditions_reject_without_writes(self) -> None:
        link = self.root / LINK
        elsewhere = self.root.parent / "elsewhere"
        elsewhere.mkdir()
        plugin_command = PLUGIN_HOOKS["SessionStart"][0]["hooks"][0]["command"]
        stray = {**EXISTING, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": plugin_command}]}]}}

        def relink(make) -> None:
            link.unlink()
            make()

        cases = [
            ("plugin_hook_effective", lambda: self.write(self.user, {"enabledPlugins": {"dev-graph@local": True}})),
            ("hooks_disabled", lambda: self.write(self.user, {"disableAllHooks": True})),
            ("managed_hooks_only", lambda: self.write(self.managed, {"allowManagedHooksOnly": True})),
            ("duplicate_registration", lambda: self.write(self.local, {"hooks": stray["hooks"]})),
            ("duplicate_registration", lambda: self.write(self.settings, stray)),
            ("settings_invalid", lambda: self.settings.write_text("{not json", encoding="utf-8")),
            ("plugin_link_mismatch", lambda: relink(lambda: link.symlink_to(elsewhere))),
            ("plugin_link_not_symlink", lambda: relink(link.mkdir)),
        ]
        for expected, arrange in cases:
            with self.subTest(expected):
                arrange()
                settings, config = self.settings.read_bytes(), self.config.read_bytes()
                code, report = self.run_cli("--mode", "apply")
                self.assertEqual((code, report["status"], report["code"], report["write_count"]),
                                 (1, "rejected", expected, 0), report)
                self.assertEqual((self.settings.read_bytes(), self.config.read_bytes()), (settings, config))
                self.assertEqual(self.manifests(), [])
                for path in (self.user, self.managed, self.local):
                    path.unlink(missing_ok=True)
                self.settings.write_bytes(self.original)
                if link.is_dir() and not link.is_symlink():
                    link.rmdir()
                else:
                    link.unlink()
                link.symlink_to(PLUGIN)
        # 診断を外せば同じ repo で適用できる (拒否は条件そのものによる)。
        self.assertEqual(self.run_cli("--mode", "apply")[1]["status"], "applied")


if __name__ == "__main__":
    unittest.main()
