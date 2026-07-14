"""C05 + repo integration の native plugin wiring 契約テスト。"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins" / "harness-creator"
OPERATIONS = PLUGIN / "references" / "native-surface-operations.md"
CAPABILITY_BUILD = PLUGIN / "commands" / "capability-build.md"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _session_start_handler(doc: dict) -> tuple[dict, dict]:
    group = doc["hooks"]["SessionStart"][0]
    return group, group["hooks"][0]


def test_codex_manifest_uses_plugin_root_hooks_contract():
    manifest = _json(PLUGIN / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == "harness-creator"
    assert manifest.get("hooks", "./hooks/hooks.json") == "./hooks/hooks.json"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["category"] == "Internal-Tooling"


def test_dual_manifest_identity_version_and_session_start_match():
    claude = _json(PLUGIN / ".claude-plugin" / "plugin.json")
    codex = _json(PLUGIN / ".codex-plugin" / "plugin.json")
    assert (claude["name"], claude["version"]) == (codex["name"], codex["version"])
    assert codex["version"].startswith("1.3.0+codex.")

    codex_group, codex_hook = _session_start_handler(_json(PLUGIN / "hooks" / "hooks.json"))
    claude_group, claude_hook = _session_start_handler({"hooks": claude["hooks"]})
    assert codex_group["matcher"] == claude_group["matcher"] == "startup|resume|clear"
    assert codex_hook["type"] == claude_hook["type"] == "command"
    for handler in (codex_hook, claude_hook):
        assert "$CLAUDE_PLUGIN_ROOT/hooks/auto-sync-on-session-start.py" in handler["command"]
        assert handler["timeout"] > 45
        assert "dangerously-bypass-hook-trust" not in handler["command"]


def test_repo_marketplace_uses_official_local_plugin_root_source():
    marketplace = _json(ROOT / ".agents" / "plugins" / "marketplace.json")
    entry = next(p for p in marketplace["plugins"] if p["name"] == "harness-creator")
    assert entry["source"] == {
        "source": "local",
        "path": "./plugins/harness-creator",
    }
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["x_harness"]["distributable"] is False
    assert entry["x_harness"]["activation_requires"] == [
        "user-install", "user-enable", "user-hook-trust"
    ]


def test_composition_declares_c05_and_native_surface_scripts_once():
    text = (PLUGIN / "plugin-composition.yaml").read_text(encoding="utf-8")
    assert text.count('ref: "hook:SessionStart/auto-sync-on-session-start"') == 1
    for ref in (
        "scripts/check-native-surface-parity.py",
        "scripts/sync-native-surfaces.py",
        "scripts/record-task-graph-knowledge.py",
    ):
        assert text.count(f"ref: {ref}") == 1


def test_make_local_repair_and_dry_run_use_c01_only():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "native-surfaces:\n\t$(MAKE) native-surfaces-apply\n\t$(MAKE) native-surfaces-check" in makefile
    dry_run = makefile.index("native-surfaces-dry-run:")
    apply = makefile.index("native-surfaces-apply:")
    check = makefile.index("native-surfaces-check:")
    assert "sync-native-surfaces.py --repo-root . --dry-run" in makefile[dry_run:apply]
    assert "sync-native-surfaces.py --repo-root . --apply" in makefile[apply:check]
    assert "sync-native-surfaces.py --repo-root . --check" in makefile[check:]
    assert "native-surfaces-pr-ready:\n\t$(MAKE) native-surfaces-apply\n\t$(MAKE) native-surfaces-check" in makefile
    assert "git status --short -- .claude/skills .claude/agents .claude/commands" in makefile
    assert "git diff -- .claude/skills .claude/agents .claude/commands .claude/settings.json" in makefile
    assert ".codex/hooks.json .codex/config.toml .agents/plugins/marketplace.json" in makefile


def test_ci_native_surface_gate_is_check_only():
    workflow = (ROOT / ".github" / "workflows" / "governance-check.yml").read_text(
        encoding="utf-8"
    )
    step = workflow.index("check repository-native capability projections")
    end = workflow.index("- name:", step + 1)
    body = workflow[step:end]
    assert "make native-surfaces-check" in body
    assert "native-surfaces-apply" not in body
    assert "--apply" not in body
    assert "sync-skills-to-claude" not in body
    assert "git status --porcelain -- .claude" in body
    assert "build-claude-symlinks.py --check" not in workflow


def test_all_active_workflows_forbid_legacy_unfiltered_projection_checks():
    forbidden = (
        "scripts/sync-skills-to-claude.sh --check",
        "build-claude-symlinks.py --check",
        "make sync-check",
    )
    workflow_paths = sorted(
        path for path in (ROOT / ".github" / "workflows").iterdir()
        if path.suffix in {".yml", ".yaml"}
    )
    for workflow_path in workflow_paths:
        workflow = workflow_path.read_text(encoding="utf-8")
        for command in forbidden:
            assert command not in workflow, f"{workflow_path}: legacy command {command}"


def test_readme_marketplace_identity_matches_repository_ssot():
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    marketplace_name = _json(ROOT / ".claude-plugin" / "marketplace.json")["name"]
    identity = f"harness-creator@{marketplace_name}"
    assert identity in readme
    assert "harness-creator@harness" not in readme


def test_committed_claude_hook_projection_is_relocatable_and_deduped():
    settings = _json(ROOT / ".claude" / "settings.json")
    managed = settings["_build_claude_settings"]["managed_hooks"]
    for hook in managed:
        command = hook["command"]
        assert str(ROOT) not in command
        assert "${CLAUDE_PROJECT_DIR}//" not in command
        if "${CLAUDE_PROJECT_DIR}" in command:
            assert "${CLAUDE_PROJECT_DIR}/plugins/" in command

    managed_session = [
        hook for hook in managed
        if "auto-sync-on-session-start.py" in hook["command"]
    ]
    runtime_session = [
        command
        for group in settings["hooks"]["SessionStart"]
        for command in group["hooks"]
        if "auto-sync-on-session-start.py" in command["command"]
    ]
    assert len(managed_session) == 1
    assert len(runtime_session) == 1


def test_default_make_test_pipeline_does_not_mix_legacy_sync_desired_set():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    line = next(line for line in makefile.splitlines() if line.startswith("test:"))
    assert "native-surfaces-check" in line
    assert "sync-check" not in line


def test_capability_build_uses_one_c01_desired_set_for_local_repair():
    text = CAPABILITY_BUILD.read_text(encoding="utf-8")
    start = text.index("単一 desired-set の native surface deploy-sync")
    end = text.index("- **stall の外ループ合流", start)
    gate = text[start:end]
    apply = gate.index("sync-native-surfaces.py --repo-root . --apply --json")
    check = gate.index("同じ C01 の `--check --json`", apply)
    assert apply < check
    assert "(1) `bash scripts/sync-skills-to-claude.sh --apply`" not in gate
    assert "check-native-surface-parity.py --repo-root" not in gate
    assert "pending_user_gate" in gate


def test_operations_runbook_covers_dry_run_rollback_and_lifecycle_gates():
    text = OPERATIONS.read_text(encoding="utf-8")
    for required in (
        "## Part 1 — 初めて使う人向け",
        "## Part 2 — Operator / technical runbook",
        "make native-surfaces-dry-run",
        "install / enable / hook trust / re-trust / uninstall",
        "pending_user_gate",
        "unsupported/deferred",
        "C01/C05 は global state を",
        "一切変更しない",
        "### 5. State transition と current output 例",
        "### 7A. Projection rollback / managed-only restore",
        "### 7B. Release rollback / source + activation",
        "#### Release file inventory (source / gate / docs / tests)",
        "### 8. Unsupported/deferred の再評価 trigger",
        "skipped_wrong_repository",
        "hook trust pending (`pending_user_gate`)",
    ):
        assert required in text

    preflight = text.index("make native-surfaces-dry-run")
    clean_gate = text.index('test ! -s "$evidence/pre.status"', preflight)
    apply = text.index("--repo-root . --apply --json", clean_gate)
    check = text.index("--repo-root . --check --json", apply)
    rollback = text.index('git apply -R --check "$evidence/projection.patch"', check)
    created_only = text.index('done < "$evidence/created.paths"', rollback)
    evidence_cmp = text.index('cmp "$evidence/pre.status" "$evidence/rollback.status"', created_only)
    assert preflight < clean_gate < apply < check < rollback < created_only < evidence_cmp
    assert "rm -rf .claude" not in text


def test_operations_release_inventory_is_complete_for_native_surface_wave():
    text = OPERATIONS.read_text(encoding="utf-8")
    required_paths = (
        "Makefile",
        ".github/workflows/governance-check.yml",
        ".agents/plugins/marketplace.json",
        "scripts/build-claude-settings.py",
        "scripts/build-claude-symlinks.py",
        "plugins/harness-creator/.claude-plugin/plugin.json",
        "plugins/harness-creator/.codex-plugin/plugin.json",
        "plugins/harness-creator/hooks/hooks.json",
        "plugins/harness-creator/hooks/auto-sync-on-session-start.py",
        "plugins/harness-creator/scripts/sync-native-surfaces.py",
        "plugins/harness-creator/scripts/check-native-surface-parity.py",
        "plugins/harness-creator/scripts/record-task-graph-knowledge.py",
        "plugins/harness-creator/references/native-surface-contract.md",
        "plugins/harness-creator/references/native-surface-operations.md",
        "plugins/harness-creator/tests/test_auto_sync_on_session_start.py",
        "plugins/harness-creator/tests/test_native_surface_repo_integration.py",
    )
    for path in required_paths:
        assert path in text


def test_operations_state_table_separates_claude_enable_from_codex_trust():
    text = OPERATIONS.read_text(encoding="utf-8")
    start = text.index("### 5. State transition と current output 例")
    end = text.index("### 6. CI sequence", start)
    section = text[start:end]
    assert "Claude Code" in section and "project `.claude/settings.json` で enabled" in section
    assert "Codex" in section and "hook trust pending (`pending_user_gate`)" in section
    assert "manifest 実在だけで enabled/trusted" in section
