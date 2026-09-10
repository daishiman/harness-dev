from __future__ import annotations

import importlib.util
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install-local-plugins.py"
SPEC = importlib.util.spec_from_file_location("install_local_plugins", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _write_catalogs(
    repo: Path,
    names: tuple[str, ...] = ("alpha", "beta"),
    dependencies: dict[str, list[str]] | None = None,
) -> None:
    claude_root = repo / "marketplaces" / "local"
    (claude_root / ".claude-plugin").mkdir(parents=True)
    (repo / ".agents" / "plugins").mkdir(parents=True)
    plugins = repo / "plugins"
    plugins.mkdir()
    (claude_root / "plugins").symlink_to(plugins, target_is_directory=True)
    for name in names:
        plugin = plugins / name
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".codex-plugin").mkdir()
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"}), encoding="utf-8"
        )
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"}), encoding="utf-8"
        )
        (plugin / "references").mkdir()
        (plugin / "references" / "package-contract.json").write_text(
            json.dumps({
                "plugin_name": name,
                "depends_on": (dependencies or {}).get(name, []),
            }),
            encoding="utf-8",
        )
    (claude_root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "harness-local",
                "plugins": [
                    {"name": name, "source": f"./plugins/{name}"} for name in names
                ],
            }
        ),
        encoding="utf-8",
    )
    (repo / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "harness",
                "plugins": [
                    {
                        "name": name,
                        "source": {"source": "local", "path": f"./plugins/{name}"},
                    }
                    for name in names
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_runtime_manifest(root: Path, platform: str, name: str, version="1.0.0") -> None:
    manifest_dir = root / (".claude-plugin" if platform == "claude" else ".codex-plugin")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}), encoding="utf-8"
    )


def _write_hook(root: Path, command: str = "true") -> str:
    path = root / "hooks" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}
    }).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _fake_cli_identities(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_cli_identity",
        lambda name, env: {
            "cli_path": f"/opt/{name}/bin/{name}",
            "cli_version": f"{name} test-version",
        },
        raising=False,
    )


def _bare_command(command: list[str]) -> list[str]:
    return [Path(command[0]).name, *command[1:]]


def test_catalog_uses_distinct_absolute_roots_and_equal_plugin_sets(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo)

    catalog = mod.load_catalog(repo)

    assert catalog.repo_root == repo.resolve()
    assert catalog.claude_root == (repo / "marketplaces" / "local").resolve()
    assert catalog.codex_root == repo.resolve()
    assert catalog.plugin_names == ("alpha", "beta")


def test_catalog_rejects_platform_plugin_set_drift(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo)
    codex_path = repo / ".agents" / "plugins" / "marketplace.json"
    payload = json.loads(codex_path.read_text(encoding="utf-8"))
    payload["plugins"].pop()
    codex_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(mod.InstallError, match="catalogs disagree"):
        mod.load_catalog(repo)


def test_catalog_rejects_legacy_bundles_in_plugin_manifest(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    manifest = repo / "plugins" / "alpha" / ".claude-plugin" / "plugin.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["bundles"] = ["all"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(mod.InstallError, match="bundles belongs in marketplace metadata"):
        mod.load_catalog(repo)


def test_install_both_registers_absolute_roots_and_user_scope(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo)
    claude_cache = tmp_path / "claude-cache"
    codex_cache = tmp_path / "codex-cache"
    for root in (claude_cache, codex_cache):
        for name in ("alpha", "beta"):
            _write_runtime_manifest(root / name, "claude" if root == claude_cache else "codex", name)
    _fake_cli_identities(monkeypatch)
    calls: list[list[str]] = []
    state = {"claude_installed": False, "codex_installed": False}

    def fake_execute(command, *, env, expect_json):
        calls.append(command)
        bare = _bare_command(command)
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return []
        if bare[:4] == ["claude", "plugin", "marketplace", "add"]:
            assert bare[4] == str((repo / "marketplaces" / "local").resolve())
            assert bare[5:] == ["--scope", "user"]
            return "added"
        if bare[:3] == ["claude", "plugin", "install"]:
            assert bare[3:5] == ["--scope", "user"]
            assert bare[5].endswith("@harness-local")
            state["claude_installed"] = True
            return "installed"
        if bare == ["claude", "plugin", "list", "--json"]:
            if not state["claude_installed"]:
                return []
            return [
                {
                    "id": f"{name}@harness-local",
                    "scope": "user",
                    "enabled": True,
                    "installPath": str((claude_cache / name).resolve()),
                    "version": "1.0.0",
                }
                for name in ("alpha", "beta")
            ]
        if bare[:4] == ["codex", "plugin", "marketplace", "add"]:
            assert bare[4] == str(repo.resolve())
            assert bare[5:] == ["--json"]
            return {"marketplaceName": "harness", "alreadyAdded": False}
        if bare[:3] == ["codex", "plugin", "add"]:
            state["codex_installed"] = True
            name = bare[3].split("@", 1)[0]
            return {
                "pluginId": bare[3],
                "installedPath": str((codex_cache / name).resolve()),
                "version": "1.0.0",
            }
        if bare == ["codex", "plugin", "list", "--json"]:
            if not state["codex_installed"]:
                return {"installed": []}
            return {
                "installed": [
                    {
                        "pluginId": f"{name}@harness",
                        "installed": True,
                        "enabled": True,
                        "version": "1.0.0",
                        "source": {
                            "source": "local",
                            "path": str((codex_cache / name).resolve()),
                        },
                    }
                    for name in ("alpha", "beta")
                ]
            }
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report = mod.install_local_plugins(
        repo_root=repo,
        platforms=("claude", "codex"),
        requested=("alpha", "beta"),
        check=False,
        claude_config_dir=tmp_path / "claude-home",
        codex_home=tmp_path / "codex-home",
    )

    assert report["status"] == "installed"
    assert report["cwd_independent"] is True
    assert report["plugin_count"] == 2
    assert report["platforms"]["claude"]["scope"] == "user"
    assert report["platforms"]["codex"]["scope"] == "user-global"
    assert all(Path(item["installed_path"]).is_absolute() for item in report["plugins"])
    assert report["platforms"]["claude"]["cli_path"] == "/opt/claude/bin/claude"
    assert report["platforms"]["codex"]["cli_path"] == "/opt/codex/bin/codex"
    assert {item["artifact_mode"] for item in report["plugins"]} == {"copy"}
    assert all(item["source_path"] and item["runtime_path"] for item in report["plugins"])
    assert all(item["manifest_version"] == "1.0.0" for item in report["plugins"])
    assert all(len(item["source_digest"]) == 64 for item in report["plugins"])
    assert all(len(item["runtime_digest"]) == 64 for item in report["plugins"])
    assert all(item["activation"] == {
        "installed": "verified",
        "enabled": "verified",
        "trust": "pending_user_gate",
        "new_session": "pending_user_gate",
        "runtime": "verified",
    } for item in report["plugins"])
    assert report["dependency_closure"] == []
    assert report["cycle_groups"] == []
    assert all(item["scc_members"] == [item["plugin"]] for item in report["plugins"])


def test_check_mode_is_read_only_and_accepts_single_platform(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    cache = tmp_path / "cache" / "alpha"
    _write_runtime_manifest(cache, "claude", "alpha")
    _fake_cli_identities(monkeypatch)
    calls: list[list[str]] = []

    def fake_execute(command, *, env, expect_json):
        calls.append(command)
        bare = _bare_command(command)
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return [
                {
                    "name": "harness-local",
                    "source": "directory",
                    "path": str((repo / "marketplaces" / "local").resolve()),
                }
            ]
        if bare == ["claude", "plugin", "list", "--json"]:
            return [
                {
                    "id": "alpha@harness-local",
                    "scope": "user",
                    "enabled": True,
                    "installPath": str(cache.resolve()),
                    "version": "1.0.0",
                }
            ]
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report = mod.install_local_plugins(
        repo_root=repo,
        platforms=("claude",),
        requested=("alpha",),
        check=True,
        claude_config_dir=None,
        codex_home=None,
    )

    assert report["status"] == "verified"
    assert not any("add" in command or "install" in command for command in calls)


def test_claude_nonempty_list_errors_are_pending_activation_not_verified(
    monkeypatch, tmp_path
):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    cache = tmp_path / "cache" / "alpha"
    _write_runtime_manifest(cache, "claude", "alpha")
    _fake_cli_identities(monkeypatch)

    def fake_execute(command, *, env, expect_json):
        bare = _bare_command(command)
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return [{"name": "harness-local", "path": str((repo / "marketplaces/local").resolve())}]
        if bare == ["claude", "plugin", "list", "--json"]:
            return [{
                "id": "alpha@harness-local",
                "scope": "user",
                "enabled": True,
                "installPath": str(cache),
                "version": "1.0.0",
                "errors": ["hook trust is required"],
            }]
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report = mod.install_local_plugins(
        repo_root=repo,
        platforms=("claude",),
        requested=("alpha",),
        check=True,
        claude_config_dir=None,
        codex_home=None,
    )

    assert report["status"] == "pending_user_gate"
    assert report["verified"] is False
    plugin = report["plugins"][0]
    assert plugin["verification_status"] == "not_verified"
    assert plugin["activation"]["runtime"] == "failed"
    assert plugin["activation_errors"] == ["hook trust is required"]


def test_same_hook_multi_activation_is_enumerated_and_never_auto_disabled(
    monkeypatch, tmp_path
):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    current = tmp_path / "cache" / "current"
    stale = tmp_path / "cache" / "stale"
    for runtime in (current, stale):
        _write_runtime_manifest(runtime, "claude", "alpha")
    digest = _write_hook(current)
    assert _write_hook(stale) == digest
    _fake_cli_identities(monkeypatch)
    calls = []

    def fake_execute(command, *, env, expect_json):
        calls.append(_bare_command(command))
        bare = calls[-1]
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return [{"name": "harness-local", "path": str((repo / "marketplaces/local").resolve())}]
        if bare == ["claude", "plugin", "list", "--json"]:
            return [
                {
                    "id": "alpha@harness-local", "scope": "user", "enabled": True,
                    "installPath": str(current), "version": "1.0.0", "errors": [],
                },
                {
                    "id": "alpha@old-market", "scope": "project", "enabled": True,
                    "installPath": str(stale), "version": "1.0.0", "errors": [],
                },
            ]
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report = mod.install_local_plugins(
        repo_root=repo,
        platforms=("claude",),
        requested=("alpha",),
        check=True,
        claude_config_dir=None,
        codex_home=None,
    )

    plugin = report["plugins"][0]
    assert report["status"] == "pending_user_gate"
    assert report["verified"] is False
    assert plugin["same_hook_multiple_activation"] is True
    assert {item["scope"] for item in plugin["activation_collisions"]} == {"user", "project"}
    assert {item["marketplace"] for item in plugin["activation_collisions"]} == {
        "harness-local", "old-market",
    }
    assert {item["runtime_path"] for item in plugin["activation_collisions"]} == {
        str(current.resolve()), str(stale.resolve()),
    }
    assert {item["hook_digest"] for item in plugin["activation_collisions"]} == {digest}
    assert not any("disable" in command for command in calls)


def test_wrong_existing_marketplace_source_fails_closed(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))

    _fake_cli_identities(monkeypatch)

    def fake_execute(command, *, env, expect_json):
        bare = _bare_command(command)
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return [
                {
                    "name": "harness-local",
                    "source": "directory",
                    "path": str((tmp_path / "different").resolve()),
                }
            ]
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    with pytest.raises(mod.InstallError, match="different source"):
        mod.install_local_plugins(
            repo_root=repo,
            platforms=("claude",),
            requested=("alpha",),
            check=False,
            claude_config_dir=None,
            codex_home=None,
        )


def test_cli_path_preference_is_independent_from_shell_cwd(tmp_path):
    local_bin = tmp_path / ".local" / "bin"
    volta_bin = tmp_path / ".volta" / "bin"
    local_bin.mkdir(parents=True)
    volta_bin.mkdir(parents=True)

    value = mod._preferred_cli_path(tmp_path, "/opt/homebrew/bin:/usr/bin")

    assert value.split(":")[:2] == [str(local_bin), str(volta_bin)]
    assert value.endswith("/opt/homebrew/bin:/usr/bin")


def test_cli_identity_preserves_executable_shim_path(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / "volta-shim"
    target.touch()
    executable = bin_dir / "codex"
    executable.symlink_to(target)
    commands = []
    monkeypatch.setattr(mod.shutil, "which", lambda name, path=None: str(executable))
    monkeypatch.setattr(
        mod,
        "_execute",
        lambda command, *, env, expect_json: commands.append(command) or "codex 1.0",
    )

    identity = mod._cli_identity("codex", {"PATH": str(bin_dir)})

    assert identity["cli_path"] == str(executable.absolute())
    assert commands == [[str(executable.absolute()), "--version"]]


def test_execute_parses_json_and_reports_cli_failures(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout='{"ok": true}\n', stderr=""
        ),
    )
    assert mod._execute(["tool", "x"], env={}, expect_json=True) == {"ok": True}
    assert mod._execute(["tool", "x"], env={}, expect_json=False) == '{"ok": true}'

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout="", stderr="bad input"
        ),
    )
    with pytest.raises(mod.InstallError, match=r"command failed \(2\)"):
        mod._execute(["tool", "x"], env={}, expect_json=True)


def test_execute_rejects_invalid_json_and_missing_cli(monkeypatch):
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="nope", stderr=""),
    )
    with pytest.raises(mod.InstallError, match="did not return JSON"):
        mod._execute(["tool"], env={}, expect_json=True)

    def missing(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr(mod.subprocess, "run", missing)
    with pytest.raises(mod.InstallError, match="cannot execute tool CLI"):
        mod._execute(["tool"], env={}, expect_json=False)


def test_claude_existing_user_install_is_updated(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    catalog = mod.load_catalog(repo)
    cache = tmp_path / "cache" / "alpha"
    _write_runtime_manifest(cache, "claude", "alpha")
    _fake_cli_identities(monkeypatch)
    calls = []
    list_calls = 0

    def fake_execute(command, *, env, expect_json):
        nonlocal list_calls
        calls.append(command)
        bare = _bare_command(command)
        if bare[:4] == ["claude", "plugin", "validate", "--strict"]:
            return "valid"
        if bare == ["claude", "plugin", "marketplace", "list", "--json"]:
            return [{"name": "harness-local", "path": str(catalog.claude_root)}]
        if bare == ["claude", "plugin", "marketplace", "update", "harness-local"]:
            return "updated"
        if bare == ["claude", "plugin", "list", "--json"]:
            list_calls += 1
            return [{
                "id": "alpha@harness-local",
                "scope": "user",
                "enabled": True,
                "installPath": str(cache),
                "version": "1.0.0",
            }]
        if bare == [
            "claude", "plugin", "update", "--scope", "user", "alpha@harness-local"
        ]:
            return "updated"
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report, plugins = mod._install_claude(
        catalog=catalog, requested=("alpha",), env={}, check=False
    )

    assert report["plugin_count"] == 1
    assert plugins[0]["plugin_id"] == "alpha@harness-local"
    assert list_calls == 2


def test_codex_check_verifies_marketplace_and_plugin(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    catalog = mod.load_catalog(repo)
    cache = tmp_path / "codex" / "alpha"
    _write_runtime_manifest(cache, "codex", "alpha")
    _fake_cli_identities(monkeypatch)

    def fake_execute(command, *, env, expect_json):
        bare = _bare_command(command)
        if bare == ["codex", "plugin", "marketplace", "list", "--json"]:
            return {
                "marketplaces": [{
                    "name": "harness",
                    "marketplaceSource": {
                        "sourceType": "local",
                        "source": str(repo.resolve()),
                    },
                }]
            }
        if bare == ["codex", "plugin", "list", "--json"]:
            return {
                "installed": [{
                    "pluginId": "alpha@harness",
                    "installed": True,
                    "enabled": True,
                    "version": "1.0.0",
                    "source": {"source": "local", "path": str(cache)},
                }]
            }
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    report, plugins = mod._install_codex(
        catalog=catalog, requested=("alpha",), env={}, check=True
    )
    assert report["scope"] == "user-global"
    assert plugins[0]["installed_path"] == str(cache.resolve())
    assert plugins[0]["source_path"] == str((repo / "plugins" / "alpha").resolve())
    assert plugins[0]["runtime_path"] == str(cache.resolve())
    assert plugins[0]["artifact_mode"] == "copy"
    assert plugins[0]["manifest_version"] == "1.0.0"


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"enabled": False}, "verification failed"),
        ({"version": "9.9.9"}, "version mismatch"),
        ({"source": {"source": "local", "path": "/missing/runtime"}}, "install path"),
    ],
)
def test_codex_check_rejects_disabled_mismatched_or_missing_runtime(
    monkeypatch, tmp_path, patch, message
):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    catalog = mod.load_catalog(repo)
    runtime = tmp_path / "runtime" / "alpha"
    _write_runtime_manifest(runtime, "codex", "alpha")
    _fake_cli_identities(monkeypatch)
    installed = {
        "pluginId": "alpha@harness",
        "installed": True,
        "enabled": True,
        "version": "1.0.0",
        "source": {"source": "local", "path": str(runtime)},
    }
    installed.update(patch)

    def fake_execute(command, *, env, expect_json):
        bare = _bare_command(command)
        if bare == ["codex", "plugin", "marketplace", "list", "--json"]:
            return {"marketplaces": [{
                "name": "harness",
                "marketplaceSource": {"sourceType": "local", "source": str(repo.resolve())},
            }]}
        if bare == ["codex", "plugin", "list", "--json"]:
            return {"installed": [installed]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_execute", fake_execute)
    with pytest.raises(mod.InstallError, match=message):
        mod._install_codex(catalog=catalog, requested=("alpha",), env={}, check=True)


def test_dependency_closure_expands_and_orders_selected_plugins(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(
        repo,
        ("app", "base", "middle"),
        {"app": ["middle"], "middle": ["base"]},
    )
    catalog = mod.load_catalog(repo)

    order, closure, cycle_groups = mod.resolve_dependency_order(catalog, ("app",))

    assert order == ("base", "middle", "app")
    assert closure == ("base", "middle")
    assert cycle_groups == ()


def test_dependency_cycle_is_a_deterministic_joint_install_scc(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha", "beta"), {"alpha": ["beta"], "beta": ["alpha"]})
    catalog = mod.load_catalog(repo)

    order, closure, cycle_groups = mod.resolve_dependency_order(catalog, ("beta",))

    assert order == ("alpha", "beta")
    assert closure == ("alpha",)
    assert cycle_groups == (("alpha", "beta"),)


def test_dependency_cycle_receipt_records_scc_members(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha", "beta"), {"alpha": ["beta"], "beta": ["alpha"]})

    def fake_install(*, catalog, requested, env, check):
        assert requested == ("alpha", "beta")
        return {"plugin_count": 2}, [
            {"plugin": name, "plugin_id": f"{name}@harness"} for name in requested
        ]

    monkeypatch.setattr(mod, "_install_codex", fake_install)
    report = mod.install_local_plugins(
        repo_root=repo,
        platforms=("codex",),
        requested=("beta",),
        check=True,
        claude_config_dir=None,
        codex_home=None,
    )

    assert report["cycle_groups"] == [["alpha", "beta"]]
    assert report["install_order"] == ["alpha", "beta"]
    assert [item["scc_members"] for item in report["plugins"]] == [
        ["alpha", "beta"],
        ["alpha", "beta"],
    ]


def test_dangling_dependency_remains_fail_closed(tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",), {"alpha": ["outside"]})
    catalog = mod.load_catalog(repo)

    with pytest.raises(mod.InstallError, match="same marketplace/source"):
        mod.resolve_dependency_order(catalog, ("alpha",))


@pytest.mark.parametrize(
    ("platforms", "requested", "message"),
    [
        ((), ("alpha",), "platforms"),
        (("other",), ("alpha",), "platforms"),
        (("claude",), ("missing",), "unknown local plugins"),
        (("claude",), (), "at least one plugin"),
        (("claude",), ("alpha", "alpha"), "duplicates"),
    ],
)
def test_install_request_validation(platforms, requested, message, tmp_path):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    with pytest.raises(mod.InstallError, match=message):
        mod.install_local_plugins(
            repo_root=repo,
            platforms=platforms,
            requested=requested,
            check=True,
            claude_config_dir=None,
            codex_home=None,
        )


def test_main_defaults_to_all_and_prints_receipt(monkeypatch, tmp_path, capsys):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    captured = {}

    def fake_install(**kwargs):
        captured.update(kwargs)
        return {"status": "verified"}

    monkeypatch.setattr(mod, "install_local_plugins", fake_install)
    code = mod.main([
        "--repo-root", str(repo), "--platform", "codex", "--all", "--check"
    ])

    assert code == 0
    assert captured["requested"] == ("alpha",)
    assert captured["platforms"] == ("codex",)
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


def test_main_requires_explicit_all_or_plugin(tmp_path, capsys):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))

    code = mod.main(["--repo-root", str(repo), "--platform", "codex", "--check"])

    assert code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "invalid"
    assert "--all or --plugin" in payload["error"]


def test_main_rejects_all_plus_plugin(tmp_path, capsys):
    repo = tmp_path / "repo"
    _write_catalogs(repo, ("alpha",))
    code = mod.main([
        "--repo-root", str(repo), "--all", "--plugin", "alpha"
    ])
    assert code == 3
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
