from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync-plugin-platforms.py"
SPEC = importlib.util.spec_from_file_location("sync_plugin_platforms", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def make_plugin(repo: Path, name: str, *, existing_codex: bool) -> Path:
    plugin = repo / "plugins" / name
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "skills" / "run-example").mkdir(parents=True)
    (plugin / "skills" / "run-example" / "SKILL.md").write_text(
        "---\nname: run-example\ndescription: Example.\n---\n",
        encoding="utf-8",
    )
    (plugin / "hooks").mkdir()
    (plugin / "hooks" / "hooks.json").write_text('{"hooks":{}}\n', encoding="utf-8")
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": name,
            "version": "1.2.3",
            "description": "Cross-product harness plugin",
            "author": {"name": "Harness team"},
            "repository": "https://github.com/example/harness",
            "skills": "./skills/",
            "hooks": "./hooks/hooks.json",
        }),
        encoding="utf-8",
    )
    if existing_codex:
        (plugin / ".codex-plugin").mkdir()
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({
                "name": name,
                "version": "0.9.0",
                "description": "stale",
                "interface": {"displayName": "Keep My Name", "brandColor": "#123456"},
            }),
            encoding="utf-8",
        )
    return plugin


@pytest.mark.parametrize("intent,existing_codex", [("create", False), ("update", True)])
def test_create_and_update_share_one_idempotent_dual_platform_projection(
    tmp_path, intent, existing_codex
):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=existing_codex)

    report, code = mod.run(
        repo=repo,
        plugin=plugin,
        intent=intent,
        mode="apply",
        marketplace_name="fixture-marketplace",
    )

    assert code == 0
    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text())
    assert codex["name"] == "sample-plugin"
    assert codex["version"] == "1.2.3"
    assert codex["skills"] == "./skills/"
    assert codex["hooks"] == "./hooks/hooks.json"
    claude = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "hooks" not in claude
    if existing_codex:
        assert codex["interface"]["displayName"] == "Sample Plugin"
        assert "brandColor" not in codex["interface"]

    marketplace = json.loads((repo / ".agents" / "plugins" / "marketplace.json").read_text())
    assert marketplace["name"] == "fixture-marketplace"
    assert marketplace["plugins"] == [{
        "name": "sample-plugin",
        "source": {"source": "local", "path": "./plugins/sample-plugin"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Development Tools",
    }]
    assert mod.run(
        repo=repo,
        plugin=plugin,
        intent=intent,
        mode="check",
        marketplace_name="fixture-marketplace",
    )[1] == 0
    assert report["status"] == "synced"


def test_check_mode_reports_drift_without_writing(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)

    report, code = mod.run(
        repo=repo,
        plugin=plugin,
        intent="create",
        mode="check",
        marketplace_name="fixture-marketplace",
    )

    assert code == 1
    assert report["status"] == "drift"
    assert not (plugin / ".codex-plugin" / "plugin.json").exists()
    assert not (repo / ".agents" / "plugins" / "marketplace.json").exists()


def test_plugin_must_be_inside_repo_plugins_directory(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(tmp_path / "outside", "sample-plugin", existing_codex=False)

    with pytest.raises(mod.PlatformSyncError, match="plugins directory"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_cli_preserves_or_derives_marketplace_name_by_default():
    parser = mod.build_parser()
    args = parser.parse_args([
        "--repo-root", "/tmp/repo",
        "--plugin", "/tmp/repo/plugins/example",
        "--intent", "update",
    ])
    assert args.marketplace_name is None


def test_intent_is_optional_because_create_and_update_are_one_upsert():
    parser = mod.build_parser()
    args = parser.parse_args([
        "--repo-root", "/tmp/repo",
        "--plugin", "/tmp/repo/plugins/example",
    ])
    assert args.intent is None


def test_missing_marketplace_name_is_derived_from_repo_directory(tmp_path):
    repo = tmp_path / "My_Plugins"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    mod.run(
        repo=repo,
        plugin=plugin,
        intent="create",
        mode="apply",
        marketplace_name=None,
    )
    marketplace = json.loads((repo / ".agents" / "plugins" / "marketplace.json").read_text())
    assert marketplace["name"] == "my-plugins"


def test_inline_claude_hooks_are_projected_to_codex_hook_file(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["hooks"] = {
        "SessionStart": [{
            "hooks": [{
                "type": "command",
                "command": "python3 $CLAUDE_PLUGIN_ROOT/scripts/start.py",
            }]
        }]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (plugin / "hooks" / "hooks.json").unlink()

    mod.run(
        repo=repo,
        plugin=plugin,
        intent="update",
        mode="apply",
        marketplace_name="fixture-marketplace",
    )

    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text())
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text())
    assert codex["hooks"] == "./hooks/hooks.json"
    assert "hooks" not in json.loads(manifest_path.read_text())
    assert hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"] == (
        "python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/start.py"
    )


def test_existing_inline_hook_projection_is_updated_not_false_green(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["hooks"] = {"SessionStart": [{"hooks": [{"type": "command", "command": "new"}]}]}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, code = mod.run(
        repo=repo,
        plugin=plugin,
        intent="update",
        mode="check",
        marketplace_name="fixture-marketplace",
    )

    assert code == 1
    assert "plugins/sample-plugin/hooks/hooks.json" in report["paths"]
    mod.run(
        repo=repo,
        plugin=plugin,
        intent="update",
        mode="apply",
        marketplace_name="fixture-marketplace",
    )
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text())
    assert hooks == {"hooks": manifest["hooks"]}
    assert "hooks" not in json.loads(manifest_path.read_text())


def test_path_hook_commands_are_normalized_for_both_products(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    hooks_path = plugin / "hooks" / "hooks.json"
    hooks_path.write_text(
        json.dumps({
            "hooks": {
                "SessionStart": [{
                    "hooks": [{
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/start.py",
                    }]
                }]
            }
        }),
        encoding="utf-8",
    )

    mod.run(
        repo=repo,
        plugin=plugin,
        intent="update",
        mode="apply",
        marketplace_name="fixture-marketplace",
    )

    hooks = json.loads(hooks_path.read_text())
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command == "python3 ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/start.py"


def test_inline_claude_session_end_timeout_must_fit_codex_seconds_limit(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["hooks"] = {
        "SessionEnd": [{
            "hooks": [{
                "type": "command",
                "command": "true",
                "timeout": 10_000,
            }]
        }]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(mod.PlatformSyncError, match="SessionEnd timeout.*3 seconds"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="update",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_claude_only_event_survives_projection_but_typos_still_fail(tmp_path):
    # 共有 hooks/hooks.json は Claude と Codex の union。Claude 専用イベントを未知扱いで
    # reject すると Claude 固有の配線を 1 本も持てなくなるため通す。一方で綴り間違いは
    # 素通りさせると hook が黙って死ぬので、allowlist 外は従来どおり落とす。
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    hooks_path = plugin / "hooks" / "hooks.json"

    def write(event: str) -> None:
        hooks_path.write_text(
            json.dumps({
                "hooks": {
                    event: [{
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "true"}],
                    }]
                }
            }),
            encoding="utf-8",
        )

    def sync() -> None:
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="update",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )

    write("PostToolUseFailure")
    sync()

    write("PostToolUseFailrue")
    with pytest.raises(mod.PlatformSyncError, match="unsupported Codex hook event"):
        sync()


def test_codex_hook_path_rejects_handlers_codex_parses_but_does_not_run(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    (plugin / "hooks" / "hooks.json").write_text(
        json.dumps({
            "hooks": {
                "SessionStart": [{
                    "hooks": [{"type": "prompt", "prompt": "Do work"}]
                }]
            }
        }),
        encoding="utf-8",
    )

    with pytest.raises(mod.PlatformSyncError, match="only command hook handlers run"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="update",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_explicit_codex_override_is_the_only_codex_specific_input(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=True)
    (plugin / ".codex-plugin-overrides.json").write_text(
        json.dumps({"interface": {"displayName": "Explicit Name", "brandColor": "#123456"}}),
        encoding="utf-8",
    )

    mod.run(
        repo=repo,
        plugin=plugin,
        intent="update",
        mode="apply",
        marketplace_name="fixture-marketplace",
    )

    codex = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text())
    assert codex["interface"]["displayName"] == "Explicit Name"
    assert codex["interface"]["brandColor"] == "#123456"


def test_author_must_be_an_object_with_a_non_empty_name_when_present(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["author"] = "Harness team"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(mod.PlatformSyncError, match="author must be an object"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_shared_marketplace_reaches_one_fixed_point_for_multiple_plugins(tmp_path):
    repo = tmp_path / "repo"
    first = make_plugin(repo, "first-plugin", existing_codex=False)
    second = make_plugin(repo, "second-plugin", existing_codex=False)
    for plugin in (first, second):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )

    assert mod.run(
        repo=repo,
        plugin=first,
        intent="update",
        mode="check",
        marketplace_name="fixture-marketplace",
    )[1] == 0
    assert mod.run(
        repo=repo,
        plugin=second,
        intent="update",
        mode="check",
        marketplace_name="fixture-marketplace",
    )[1] == 0


def test_codex_distribution_false_is_not_added_to_marketplace(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    (plugin / "references").mkdir()
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({
            "codex_distribution": {
                "distributable": False,
                "marketplace": ".agents/plugins/marketplace.json",
                "source": "./plugins/sample-plugin",
            }
        }),
        encoding="utf-8",
    )

    with pytest.raises(mod.PlatformSyncError, match="distributable=true"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_plugin_tree_cannot_contain_symlink_escaping_distribution_root(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    (plugin / "skills" / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(mod.PlatformSyncError, match="symlink escapes plugin root"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_apply_rolls_back_earlier_outputs_when_later_write_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    original = mod._atomic_write
    calls = 0

    def fail_second(path, content):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected write failure")
        return original(path, content)

    monkeypatch.setattr(mod, "_atomic_write", fail_second)
    with pytest.raises(OSError, match="injected"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="create",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )
    assert not (plugin / ".codex-plugin" / "plugin.json").exists()
    assert not (repo / ".agents" / "plugins" / "marketplace.json").exists()


def test_all_inventory_contains_every_claude_plugin(tmp_path):
    repo = tmp_path / "repo"
    included = make_plugin(repo, "included-plugin", existing_codex=False)
    excluded = make_plugin(repo, "excluded-plugin", existing_codex=False)
    for plugin, distributable in ((included, True), (excluded, False)):
        (plugin / "references").mkdir()
        (plugin / "references" / "package-contract.json").write_text(
            json.dumps({
                "codex_distribution": {
                    "distributable": distributable,
                    "marketplace": ".agents/plugins/marketplace.json",
                    "source": f"./plugins/{plugin.name}",
                }
            }),
            encoding="utf-8",
        )

    assert mod.discover_codex_plugins(repo) == [excluded.resolve(), included.resolve()]


def test_all_fails_closed_when_any_plugin_explicitly_disables_codex(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    (plugin / "references").mkdir()
    (plugin / "references" / "package-contract.json").write_text(
        json.dumps({
            "codex_distribution": {
                "distributable": False,
                "marketplace": ".agents/plugins/marketplace.json",
                "source": "./plugins/sample-plugin",
            }
        }),
        encoding="utf-8",
    )

    with pytest.raises(mod.PlatformSyncError, match="distributable=true"):
        mod.run_all(repo=repo, mode="apply", marketplace_name="fixture-marketplace")
    assert not (plugin / ".codex-plugin" / "plugin.json").exists()
    assert not (repo / ".agents" / "plugins" / "marketplace.json").exists()


def test_all_is_one_fixed_point_and_prunes_only_stale_repo_plugin_entries(tmp_path):
    repo = tmp_path / "repo"
    first = make_plugin(repo, "first-plugin", existing_codex=False)
    second = make_plugin(repo, "second-plugin", existing_codex=False)
    marketplace = repo / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(
        json.dumps({
            "name": "fixture-marketplace",
            "plugins": [
                {
                    "name": "removed-plugin",
                    "source": {"source": "local", "path": "./plugins/removed-plugin"},
                },
                {
                    "name": "foreign-plugin",
                    "source": {"source": "git", "url": "https://example.com/plugin.git"},
                },
            ],
        }),
        encoding="utf-8",
    )

    report, code = mod.run_all(
        repo=repo,
        mode="apply",
        marketplace_name="fixture-marketplace",
    )

    assert code == 0
    assert report["status"] == "synced"
    assert [item["plugin"] for item in report["plugins"]] == [
        "first-plugin",
        "second-plugin",
    ]
    assert (first / ".codex-plugin" / "plugin.json").is_file()
    assert (second / ".codex-plugin" / "plugin.json").is_file()
    generated = json.loads(marketplace.read_text())
    assert [item["name"] for item in generated["plugins"]] == [
        "foreign-plugin",
        "first-plugin",
        "second-plugin",
    ]
    assert mod.run_all(
        repo=repo,
        mode="check",
        marketplace_name="fixture-marketplace",
    )[1] == 0


def test_component_path_cannot_escape_or_point_to_missing_asset(tmp_path):
    repo = tmp_path / "repo"
    plugin = make_plugin(repo, "sample-plugin", existing_codex=False)
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["mcpServers"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(mod.PlatformSyncError, match="mcpServers"):
        mod.run(
            repo=repo,
            plugin=plugin,
            intent="update",
            mode="apply",
            marketplace_name="fixture-marketplace",
        )


def test_repository_fleet_is_complete_self_contained_and_excludes_retired_plugins():
    repo = Path(__file__).resolve().parents[3]
    retired = {
        "company-master",
        "mf-kessai-invoice-check",
        "notion-gmail-send",
    }
    discovered = mod.discover_codex_plugins(repo)
    discovered_names = {plugin.name for plugin in discovered}
    codex_names = {
        path.parents[1].name
        for path in (repo / "plugins").glob("*/.codex-plugin/plugin.json")
    }
    marketplace = json.loads(
        (repo / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    marketplace_names = {item["name"] for item in marketplace["plugins"]}

    assert len(discovered_names) == 20
    assert discovered_names == codex_names == marketplace_names
    assert retired.isdisjoint(discovered_names)
    for plugin in discovered:
        mod._assert_plugin_symlinks_confined(plugin)


HOOKED_PLUGINS = {
    "contract-generator",
    "dev-graph",
    "extract-system-blueprint",
    "guide-doc-generator",
    "harness-creator",
    "plugin-dev-planner",
    "skill-governance-adapters",
    "skill-intake",
    "slide-report-generator",
    "spec-drift-guardian",
    "system-dev-planner",
    "system-spec-harness",
    "ubm-goal-setting",
}


def test_standard_hooks_autoload_is_claude_implicit_and_codex_explicit_for_all_hooked():
    repo = Path(__file__).resolve().parents[3]
    hooked = sorted(
        plugin
        for plugin in mod.discover_codex_plugins(repo)
        if (plugin / "hooks" / "hooks.json").is_file()
    )

    # 数だけでなく名前で固定する。数値だけだと 1 つ失って 1 つ増えた場合に緑のまま
    # 配線が消え、hook が黙って無効化されたことに気付けない。
    assert {plugin.name for plugin in hooked} == HOOKED_PLUGINS
    for plugin in hooked:
        claude = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        assert "hooks" not in claude, plugin.name
        assert codex["hooks"] in {
            "./hooks/hooks.json",
            "./codex/hooks.json",  # dev-graph filters unsupported TaskCompleted.
        }, plugin.name
