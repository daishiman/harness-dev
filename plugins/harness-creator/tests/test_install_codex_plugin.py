from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install-codex-plugin.py"
SPEC = importlib.util.spec_from_file_location("install_codex_plugin", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _write_local_source(
    source: Path,
    plugins: dict[str, tuple[str, list[str]]],
) -> None:
    (source / ".agents" / "plugins").mkdir(parents=True)
    entries = []
    for name, (version, depends_on) in plugins.items():
        root = source / "plugins" / name
        (root / ".codex-plugin").mkdir(parents=True)
        (root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "version": version}), encoding="utf-8"
        )
        (root / "references").mkdir()
        (root / "references" / "package-contract.json").write_text(
            json.dumps({"plugin_name": name, "depends_on": depends_on}),
            encoding="utf-8",
        )
        entries.append({
            "name": name,
            "source": {"source": "local", "path": f"./plugins/{name}"},
        })
    (source / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps({"name": "fixture", "plugins": entries}), encoding="utf-8"
    )


def _write_runtime(root: Path, name: str, version: str) -> None:
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}), encoding="utf-8"
    )


def _copy_runtime(source_plugin: Path, root: Path) -> None:
    """Codex が source を写した runtime を作る (source と runtime の digest が一致する)。"""
    shutil.copytree(source_plugin, root)


def _write_hook(root: Path, command: str = "true") -> str:
    path = root / "hooks" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}
    }).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _fake_cli_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_cli_identity",
        lambda env: {"cli_path": "/opt/codex/bin/codex", "cli_version": "codex-cli 0.test"},
        raising=False,
    )


def test_local_install_registers_installs_and_verifies(monkeypatch, tmp_path):
    source = tmp_path / "repo"
    _write_local_source(source, {"sample": ("1.2.3", [])})
    runtime = tmp_path / "runtime" / "sample"
    _copy_runtime(source / "plugins" / "sample", runtime)
    _fake_cli_identity(monkeypatch)
    calls = []

    def fake_run(command, *, env):
        calls.append(command)
        if command[2:5] == ["marketplace", "add", str(source.resolve())]:
            return {"marketplaceName": "fixture", "alreadyAdded": False}
        if command[2] == "add":
            return {
                "pluginId": "sample@fixture",
                "installedPath": str(runtime),
                "version": "1.2.3",
            }
        if command[2] == "list":
            return {"installed": [{
                "pluginId": "sample@fixture",
                "installed": True,
                "enabled": True,
                "version": "1.2.3",
                "source": {"source": "local", "path": str(runtime)},
            }]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    report = mod.install(source=str(source), ref=None, plugin="sample", codex_home=tmp_path / "codex")

    assert report["status"] == "installed"
    assert report["plugin_id"] == "sample@fixture"
    assert report["enabled"] is True
    assert report["hook_trust"] == "user-review-required"
    assert report["cli_path"] == "/opt/codex/bin/codex"
    assert report["cli_version"] == "codex-cli 0.test"
    assert report["source_path"] == str((source / "plugins" / "sample").resolve())
    assert report["runtime_path"] == str(runtime.resolve())
    assert report["artifact_mode"] == "copy"
    assert report["manifest_version"] == "1.2.3"
    assert len(report["source_digest"]) == 64
    assert report["runtime_digest"] == report["source_digest"]
    assert report["phase"] == "done"
    assert report["added_plugins"] == ["sample@fixture"]
    assert report["activation"] == {
        "installed": "verified",
        "enabled": "verified",
        "trust": "pending_user_gate",
        "new_session": "pending_user_gate",
        "runtime": "verified",
    }
    assert report["dependency_closure"] == []
    assert report["install_order"] == ["sample"]
    assert all("upgrade" not in command for command in calls)

    workflow = json.loads(
        (SCRIPT.parents[1] / "skills" / "run-codex-plugin-install" / "workflow-manifest.json")
        .read_text(encoding="utf-8")
    )
    required_fields = set(workflow["completion_signals"]["required_receipt_fields"])
    assert required_fields <= report.keys()
    assert "verified" in required_fields
    assert "installed" not in required_fields

    verify_phase = next(phase for phase in workflow["phases"] if phase["id"] == "verify")
    routes = verify_phase["validation_by_route"]
    assert set(routes) == {"local-all", "single-local-or-git"}
    assert any("install-local-plugins.py --all --check" in item for item in routes["local-all"])
    assert all("install-local-plugins.py --all --check" not in item for item in routes["single-local-or-git"])
    assert any("codex plugin list --json" in item for item in routes["single-local-or-git"])


def test_codex_plugin_workflows_declare_transition_gates():
    skills_root = SCRIPT.parents[1] / "skills"
    for skill in ("run-codex-plugin-install", "run-codex-plugin-package"):
        manifest = json.loads(
            (skills_root / skill / "workflow-manifest.json").read_text(encoding="utf-8")
        )
        for phase in manifest["phases"]:
            transition = phase.get("transition")
            assert isinstance(transition, dict), f"{skill}/{phase['id']}: transition missing"
            assert transition.get("gate"), f"{skill}/{phase['id']}: gate missing"
            assert transition.get("on_pass"), f"{skill}/{phase['id']}: PASS target missing"
            assert transition.get("on_fail"), f"{skill}/{phase['id']}: FAIL target missing"


def test_git_install_upgrades_snapshot_before_install(monkeypatch, tmp_path):
    snapshot = tmp_path / "git-snapshot"
    _write_local_source(snapshot, {"sample": ("2.0.0", [])})
    runtime = tmp_path / "runtime" / "sample"
    _write_runtime(runtime, "sample", "2.0.0")
    _fake_cli_identity(monkeypatch)
    calls = []

    def fake_run(command, *, env):
        calls.append(command)
        if command[2:5] == ["marketplace", "add", "owner/repo"]:
            return {"marketplaceName": "fixture", "alreadyAdded": True}
        if command[2:5] == ["marketplace", "upgrade", "fixture"]:
            return {"marketplaceName": "fixture", "status": "upgraded"}
        if command[2:5] == ["marketplace", "list", "--json"]:
            return {"marketplaces": [{"name": "fixture", "root": str(snapshot)}]}
        if command[2] == "add":
            return {
                "pluginId": "sample@fixture",
                "installedPath": str(runtime),
                "version": "2.0.0",
            }
        if command[2] == "list":
            return {"installed": [{
                "pluginId": "sample@fixture",
                "installed": True,
                "enabled": True,
                "version": "2.0.0",
                "source": {"source": "local", "path": str(runtime)},
            }]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    report = mod.install(source="owner/repo", ref="main", plugin="sample", codex_home=tmp_path / "codex")

    assert report["source_type"] == "git"
    assert report["artifact_mode"] == "git-snapshot"
    assert report["source_path"] == str((snapshot / "plugins" / "sample").resolve())
    assert "git_snapshot" in report
    assert ["codex", "plugin", "marketplace", "upgrade", "fixture", "--json"] in [
        [Path(command[0]).name, *command[1:]] for command in calls
    ]
    # branch の ref は固定しないが、snapshot から読めた commit は無いので None と書く
    assert report["resolved_revision"] is None
    assert report["approved_plugins"] is None


PINNED = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


def _write_install_metadata(snapshot: Path, revision: str) -> None:
    (snapshot / ".codex-marketplace-install.json").write_text(
        json.dumps({"source_type": "git", "ref_name": PINNED, "revision": revision}),
        encoding="utf-8",
    )


def _git_fake_cli(snapshot: Path, runtimes: dict[str, Path], *, calls: list,
                  upgrade_to: str | None = None):
    def fake_run(command, *, env):
        calls.append(command)
        if command[2:4] == ["marketplace", "add"]:
            return {"marketplaceName": "fixture", "alreadyAdded": True}
        if command[2:4] == ["marketplace", "upgrade"]:
            if upgrade_to is not None:
                _write_install_metadata(snapshot, upgrade_to)
            return {"marketplaceName": "fixture", "status": "upgraded"}
        if command[2:4] == ["marketplace", "list"]:
            return {"marketplaces": [{"name": "fixture", "root": str(snapshot)}]}
        if command[2] == "add":
            name = command[3].split("@", 1)[0]
            return {"pluginId": command[3], "version": "2.0.0",
                    "installedPath": str(runtimes[name])}
        if command[2] == "list":
            return {"installed": [
                {"pluginId": f"{name}@fixture", "installed": True, "enabled": True,
                 "version": "2.0.0", "source": {"source": "local", "path": str(path)}}
                for name, path in runtimes.items()
            ]}
        raise AssertionError(command)

    return fake_run


def _plugin_adds(calls: list) -> list:
    return [command for command in calls if command[2] == "add"]


def test_git_pinned_snapshot_already_at_sha_is_not_upgraded(monkeypatch, tmp_path):
    snapshot = tmp_path / "git-snapshot"
    _write_local_source(snapshot, {"sample": ("2.0.0", [])})
    _write_install_metadata(snapshot, PINNED)
    runtime = tmp_path / "runtime" / "sample"
    _copy_runtime(snapshot / "plugins" / "sample", runtime)
    _fake_cli_identity(monkeypatch)
    calls: list = []
    monkeypatch.setattr(mod, "_run_json", _git_fake_cli(snapshot, {"sample": runtime}, calls=calls))

    report = mod.install(source="owner/repo", ref=PINNED.upper(), plugin="sample",
                         codex_home=None, approved_plugins=["sample"])

    assert all(command[2:4] != ["marketplace", "upgrade"] for command in calls)
    assert report["status"] == "installed"
    assert report["resolved_revision"] == PINNED
    assert report["revision_evidence"]["install_metadata_revision"] == PINNED
    assert report["approved_plugins"] == ["sample"]


def test_git_pinned_snapshot_is_upgraded_then_verified(monkeypatch, tmp_path):
    snapshot = tmp_path / "git-snapshot"
    _write_local_source(snapshot, {"sample": ("2.0.0", [])})
    _write_install_metadata(snapshot, OTHER)
    runtime = tmp_path / "runtime" / "sample"
    _write_runtime(runtime, "sample", "2.0.0")
    _fake_cli_identity(monkeypatch)
    calls: list = []
    monkeypatch.setattr(mod, "_run_json", _git_fake_cli(
        snapshot, {"sample": runtime}, calls=calls, upgrade_to=PINNED,
    ))

    report = mod.install(source="owner/repo", ref=PINNED, plugin="sample",
                         codex_home=None, approved_plugins=["sample"])

    assert any(command[2:4] == ["marketplace", "upgrade"] for command in calls)
    assert report["resolved_revision"] == PINNED


def test_git_snapshot_drift_stops_before_any_plugin_add(monkeypatch, tmp_path):
    snapshot = tmp_path / "git-snapshot"
    _write_local_source(snapshot, {"sample": ("2.0.0", [])})
    _write_install_metadata(snapshot, OTHER)
    runtime = tmp_path / "runtime" / "sample"
    _write_runtime(runtime, "sample", "2.0.0")
    _fake_cli_identity(monkeypatch)
    calls: list = []
    # upgrade しても固定した SHA に来ない (CLI が pin を守らない場合)
    monkeypatch.setattr(mod, "_run_json", _git_fake_cli(
        snapshot, {"sample": runtime}, calls=calls, upgrade_to=OTHER,
    ))

    with pytest.raises(mod.InstallError, match="not at the pinned commit"):
        mod.install(source="owner/repo", ref=PINNED, plugin="sample",
                    codex_home=None, approved_plugins=["sample"])
    assert _plugin_adds(calls) == []


def test_git_closure_outside_approved_set_stops_before_any_plugin_add(monkeypatch, tmp_path):
    snapshot = tmp_path / "git-snapshot"
    # 承認の後に snapshot の closure が base を含むようになった
    _write_local_source(snapshot, {"base": ("2.0.0", []), "app": ("2.0.0", ["base"])})
    _write_install_metadata(snapshot, PINNED)
    runtimes = {}
    for name in ("base", "app"):
        runtimes[name] = tmp_path / "runtime" / name
        _write_runtime(runtimes[name], name, "2.0.0")
    _fake_cli_identity(monkeypatch)
    calls: list = []
    monkeypatch.setattr(mod, "_run_json", _git_fake_cli(snapshot, runtimes, calls=calls))

    with pytest.raises(mod.InstallError, match=r"unapproved=\['base'\]"):
        mod.install(source="owner/repo", ref=PINNED, plugin="app",
                    codex_home=None, approved_plugins=["app"])
    assert _plugin_adds(calls) == []


def test_git_approved_set_requires_pinned_sha_before_any_cli_call(monkeypatch):
    calls: list = []
    monkeypatch.setattr(mod, "_run_json", lambda command, *, env: calls.append(command))
    monkeypatch.setattr(mod, "_cli_identity", lambda env: calls.append("identity"))
    for ref in ("main", None, PINNED[:12]):
        with pytest.raises(mod.InstallError, match="40-hex commit SHA"):
            mod.install(source="owner/repo", ref=ref, plugin="sample",
                        codex_home=None, approved_plugins=["sample"])
    with pytest.raises(mod.InstallError, match="duplicate"):
        mod.install(source="owner/repo", ref=PINNED, plugin="sample",
                    codex_home=None, approved_plugins=["sample", "sample"])
    assert calls == []


def test_local_closure_outside_approved_set_stops_before_any_cli_call(monkeypatch, tmp_path):
    source = tmp_path / "repo"
    _write_local_source(source, {"base": ("1.0.0", []), "app": ("1.0.0", ["base"])})
    calls: list = []
    monkeypatch.setattr(mod, "_run_json", lambda command, *, env: calls.append(command))
    monkeypatch.setattr(mod, "_cli_identity", lambda env: calls.append("identity"))

    with pytest.raises(mod.InstallError, match=r"unapproved=\['base'\]"):
        mod.install(source=str(source), ref=None, plugin="app",
                    codex_home=None, approved_plugins=["app"])
    with pytest.raises(mod.InstallError, match=r"approved_but_not_in_closure=\['extra'\]"):
        mod.install(source=str(source), ref=None, plugin="app",
                    codex_home=None, approved_plugins=["app", "base", "extra"])
    assert calls == []


def test_snapshot_revision_reads_metadata_and_own_checkout_only(monkeypatch, tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    monkeypatch.setattr(mod, "_git_snapshot", lambda root, **kwargs: {
        "repository": str(snapshot), "commit": PINNED, "dirty": False,
    })
    assert mod._snapshot_revision(snapshot) == {
        "revision": PINNED, "install_metadata_revision": None, "git_head": PINNED,
        "git_dirty": False,
    }
    _write_install_metadata(snapshot, OTHER)
    with pytest.raises(mod.InstallError, match="revision disagrees"):
        mod._snapshot_revision(snapshot)
    # snapshot root より上の repository の HEAD は使わない
    monkeypatch.setattr(mod, "_git_snapshot", lambda root, **kwargs: {
        "repository": str(tmp_path), "commit": PINNED, "dirty": True,
    })
    outer = mod._snapshot_revision(snapshot)
    assert outer["revision"] == OTHER
    # 外側の repository の dirty は snapshot の dirty として扱わない
    assert outer["git_dirty"] is None


def test_ref_is_rejected_for_local_source(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    with pytest.raises(mod.InstallError, match="--ref"):
        mod.install(source=str(source), ref="main", plugin="sample", codex_home=None)


def test_codex_same_hook_multi_activation_is_pending_and_enumerated(
    monkeypatch, tmp_path
):
    source = tmp_path / "repo"
    _write_local_source(source, {"sample": ("1.2.3", [])})
    current = tmp_path / "runtime" / "current"
    stale = tmp_path / "runtime" / "stale"
    for runtime in (current, stale):
        _write_runtime(runtime, "sample", "1.2.3")
    digest = _write_hook(current)
    assert _write_hook(stale) == digest
    _fake_cli_identity(monkeypatch)
    calls = []

    def fake_run(command, *, env):
        calls.append(command)
        if command[2] == "marketplace":
            return {"marketplaceName": "fixture", "alreadyAdded": False}
        if command[2] == "add":
            return {
                "pluginId": "sample@fixture", "installedPath": str(current),
                "version": "1.2.3",
            }
        if command[2] == "list":
            return {"installed": [
                {
                    "pluginId": "sample@fixture", "installed": True, "enabled": True,
                    "version": "1.2.3", "scope": "user-global",
                    "source": {"source": "local", "path": str(current)},
                },
                {
                    "pluginId": "sample@old-market", "installed": True, "enabled": True,
                    "version": "1.2.3", "scope": "project",
                    "source": {"source": "local", "path": str(stale)},
                },
            ]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    report = mod.install(
        source=str(source), ref=None, plugin="sample", codex_home=None
    )

    assert report["status"] == "pending_user_gate"
    assert report["verified"] is False
    assert report["same_hook_multiple_activation"] is True
    assert {item["marketplace"] for item in report["activation_collisions"]} == {
        "fixture", "old-market",
    }
    assert {item["hook_digest"] for item in report["activation_collisions"]} == {digest}
    assert not any("disable" in command for command in calls)


@pytest.mark.parametrize(
    ("installed_patch", "message"),
    [
        ({"enabled": False}, "not enabled"),
        ({"source": {"source": "local", "path": "/missing/runtime"}}, "runtime path"),
        ({"version": "9.9.9"}, "version mismatch"),
    ],
)
def test_single_installer_fails_closed_on_invalid_runtime_identity(
    monkeypatch, tmp_path, installed_patch, message
):
    source = tmp_path / "repo"
    _write_local_source(source, {"sample": ("1.2.3", [])})
    runtime = tmp_path / "runtime" / "sample"
    _write_runtime(runtime, "sample", "1.2.3")
    _fake_cli_identity(monkeypatch)

    installed = {
        "pluginId": "sample@fixture",
        "installed": True,
        "enabled": True,
        "version": "1.2.3",
        "source": {"source": "local", "path": str(runtime)},
    }
    installed.update(installed_patch)

    def fake_run(command, *, env):
        if command[2] == "marketplace":
            return {"marketplaceName": "fixture", "alreadyAdded": False}
        if command[2] == "add":
            return {"pluginId": "sample@fixture", "version": "1.2.3", "installedPath": str(runtime)}
        if command[2] == "list":
            return {"installed": [installed]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    with pytest.raises(mod.InstallError, match=message):
        mod.install(source=str(source), ref=None, plugin="sample", codex_home=None)


def test_dependency_closure_is_installed_topologically_from_same_marketplace(
    monkeypatch, tmp_path
):
    source = tmp_path / "repo"
    _write_local_source(
        source,
        {
            "base": ("1.0.0", []),
            "middle": ("1.1.0", ["base"]),
            "app": ("2.0.0", ["middle"]),
        },
    )
    runtimes = {}
    for name, version in (("base", "1.0.0"), ("middle", "1.1.0"), ("app", "2.0.0")):
        runtime = tmp_path / "runtime" / name
        _write_runtime(runtime, name, version)
        runtimes[name] = runtime
    _fake_cli_identity(monkeypatch)
    added = []

    def fake_run(command, *, env):
        if command[2] == "marketplace":
            return {"marketplaceName": "fixture", "alreadyAdded": False}
        if command[2] == "add":
            name = command[3].split("@", 1)[0]
            added.append(name)
            version = {"base": "1.0.0", "middle": "1.1.0", "app": "2.0.0"}[name]
            return {"pluginId": command[3], "version": version, "installedPath": str(runtimes[name])}
        if command[2] == "list":
            return {"installed": [
                {
                    "pluginId": f"{name}@fixture",
                    "installed": True,
                    "enabled": True,
                    "version": version,
                    "source": {"source": "local", "path": str(runtimes[name])},
                }
                for name, version in (("base", "1.0.0"), ("middle", "1.1.0"), ("app", "2.0.0"))
            ]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    report = mod.install(source=str(source), ref=None, plugin="app", codex_home=None)

    assert added == ["base", "middle", "app"]
    assert report["dependency_closure"] == ["base", "middle"]
    assert report["install_order"] == ["base", "middle", "app"]
    assert [item["plugin"] for item in report["artifacts"]] == added
    assert report["cycle_groups"] == []
    assert all(item["scc_members"] == [item["plugin"]] for item in report["artifacts"])


def test_dependency_cycle_is_installed_as_a_deterministic_scc(monkeypatch, tmp_path):
    source = tmp_path / "repo"
    _write_local_source(
        source,
        {
            "alpha": ("1.0.0", ["beta"]),
            "beta": ("1.0.0", ["alpha"]),
        },
    )
    runtimes = {}
    for name in ("alpha", "beta"):
        runtime = tmp_path / "runtime" / name
        _write_runtime(runtime, name, "1.0.0")
        runtimes[name] = runtime
    _fake_cli_identity(monkeypatch)
    added = []

    def fake_run(command, *, env):
        if command[2] == "marketplace":
            return {"marketplaceName": "fixture", "alreadyAdded": False}
        if command[2] == "add":
            name = command[3].split("@", 1)[0]
            added.append(name)
            return {
                "pluginId": command[3],
                "version": "1.0.0",
                "installedPath": str(runtimes[name]),
            }
        if command[2] == "list":
            return {"installed": [
                {
                    "pluginId": f"{name}@fixture",
                    "installed": True,
                    "enabled": True,
                    "version": "1.0.0",
                    "source": {"source": "local", "path": str(runtimes[name])},
                }
                for name in ("alpha", "beta")
            ]}
        raise AssertionError(command)

    monkeypatch.setattr(mod, "_run_json", fake_run)
    report = mod.install(source=str(source), ref=None, plugin="beta", codex_home=None)

    assert added == ["alpha", "beta"]
    assert report["dependency_closure"] == ["alpha"]
    assert report["cycle_groups"] == [["alpha", "beta"]]
    assert [item["scc_members"] for item in report["artifacts"]] == [
        ["alpha", "beta"],
        ["alpha", "beta"],
    ]


def test_cli_process_helpers_and_identity_fail_closed(monkeypatch, tmp_path):
    # subprocess.run は text=False で走らせるので、stdout と stderr は bytes で返る
    success = SimpleNamespace(returncode=0, stdout=b'{"ok": true}\n', stderr=b"")
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: success)
    assert mod._run_json(["codex", "x"], env={}) == {"ok": True}
    assert mod._run_text(["codex", "--version"], env={}) == '{"ok": true}'

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout=b"", stderr=b"bad input \xff"
        ),
    )
    with pytest.raises(mod.InstallError, match=r"command failed \(2\)"):
        mod._run_json(["codex"], env={})
    with pytest.raises(mod.InstallError, match=r"command failed \(2\)"):
        mod._run_text(["codex"], env={})

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"not-json", stderr=b""
        ),
    )
    with pytest.raises(mod.InstallError, match="did not return JSON"):
        mod._run_json(["codex"], env={})
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"[]", stderr=b""
        ),
    )
    with pytest.raises(mod.InstallError, match="must be an object"):
        mod._run_json(["codex"], env={})
    # 非 UTF-8 のバイトは traceback ではなく InstallError (exit 3) になる
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b'{"ok": "\xff"}', stderr=b""
        ),
    )
    with pytest.raises(mod.InstallError, match="not UTF-8"):
        mod._run_json(["codex"], env={})
    # 深すぎる JSON の RecursionError も InstallError になる
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"[" * 100000, stderr=b""
        ),
    )
    with pytest.raises(mod.InstallError, match="did not return JSON"):
        mod._run_json(["codex"], env={})

    def null_argument(*args, **kwargs):
        raise ValueError("embedded null byte")

    monkeypatch.setattr(mod.subprocess, "run", null_argument)
    with pytest.raises(mod.InstallError, match="cannot execute"):
        mod._run_json(["codex"], env={})

    def unavailable(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr(mod.subprocess, "run", unavailable)
    with pytest.raises(mod.InstallError, match="cannot execute"):
        mod._run_json(["codex"], env={})
    with pytest.raises(mod.InstallError, match="cannot execute"):
        mod._run_text(["codex"], env={})

    executable = tmp_path / "bin" / "codex"
    executable.parent.mkdir()
    shim_target = executable.parent / "volta-shim"
    shim_target.touch()
    executable.symlink_to(shim_target)
    monkeypatch.setattr(mod.shutil, "which", lambda name, path=None: str(executable))
    monkeypatch.setattr(mod, "_run_text", lambda command, *, env: "codex-cli 1.2\nextra")
    assert mod._cli_identity({"PATH": str(executable.parent)}) == {
        "cli_path": str(executable.absolute()),
        "cli_version": "codex-cli 1.2",
    }
    monkeypatch.setattr(mod.shutil, "which", lambda name, path=None: None)
    with pytest.raises(mod.InstallError, match="not available"):
        mod._cli_identity({})
    monkeypatch.setattr(mod.shutil, "which", lambda name, path=None: str(executable))
    monkeypatch.setattr(mod, "_run_text", lambda command, *, env: "")
    with pytest.raises(mod.InstallError, match="empty version"):
        mod._cli_identity({})


def test_source_catalog_and_dependency_validation_fail_closed(tmp_path):
    with pytest.raises(mod.InstallError, match="does not exist"):
        mod._classify_source("./missing-marketplace")
    with pytest.raises(mod.InstallError, match="existing local"):
        mod._classify_source("not a source")

    source = tmp_path / "repo"
    _write_local_source(source, {"sample": ("1.0.0", ["external"])})
    with pytest.raises(mod.InstallError, match="same marketplace/source"):
        mod._load_catalog(source)

    plugins = {
        "alpha": {"dependencies": ("beta",)},
        "beta": {"dependencies": ("alpha",)},
    }
    order, closure, cycle_groups = mod._resolve_dependency_order(plugins, "alpha")
    assert order == ("alpha", "beta")
    assert closure == ("beta",)
    assert cycle_groups == (("alpha", "beta"),)
    with pytest.raises(mod.InstallError, match="not exposed"):
        mod._resolve_dependency_order(plugins, "missing")


def test_snapshot_root_and_artifact_details_fail_closed(tmp_path):
    with pytest.raises(mod.InstallError, match=r"marketplaces\[\]"):
        mod._marketplace_snapshot_root({}, marketplace_name="fixture")
    with pytest.raises(mod.InstallError, match="not registered"):
        mod._marketplace_snapshot_root(
            {"marketplaces": []}, marketplace_name="fixture"
        )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    assert mod._marketplace_snapshot_root(
        {
            "marketplaces": [{
                "name": "fixture",
                "marketplaceSource": {"source": str(snapshot)},
            }]
        },
        marketplace_name="fixture",
    ) == snapshot.resolve()

    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    other = tmp_path / "other"
    _write_runtime(source, "sample", "1.0.0")
    _write_runtime(runtime, "sample", "1.0.0")
    _write_runtime(other, "sample", "1.0.0")
    metadata = {"root": source, "version": "1.0.0"}
    installed = {
        "installed": True,
        "enabled": True,
        "version": "1.0.0",
        "source": {"path": str(runtime)},
    }
    with pytest.raises(mod.InstallError, match="post-install"):
        mod._artifact_receipt(
            name="sample", marketplace_name="fixture", metadata=metadata,
            installed={**installed, "installed": False}, install_result={},
            source_type="local",
        )
    with pytest.raises(mod.InstallError, match="runtime path mismatch"):
        mod._artifact_receipt(
            name="sample", marketplace_name="fixture", metadata=metadata,
            installed=installed,
            install_result={"installedPath": str(other), "version": "1.0.0"},
            source_type="local",
        )
    with pytest.raises(mod.InstallError, match="installed version is missing"):
        mod._artifact_receipt(
            name="sample", marketplace_name="fixture", metadata=metadata,
            installed={**installed, "version": None}, install_result={},
            source_type="local",
        )
    with pytest.raises(mod.InstallError, match="version mismatch"):
        mod._artifact_receipt(
            name="sample", marketplace_name="fixture", metadata=metadata,
            installed=installed, install_result={"version": "2.0.0"},
            source_type="local",
        )
    live = mod._artifact_receipt(
        name="sample",
        marketplace_name="fixture",
        metadata=metadata,
        installed={**installed, "source": {"path": str(source)}},
        install_result={"installedPath": str(source), "version": "1.0.0"},
        source_type="local",
    )
    assert live["artifact_mode"] == "live-source"


def test_main_prints_success_and_fail_closed_receipts(monkeypatch, capsys):
    seen = []

    def installed(**kwargs):
        seen.append(kwargs)
        return {"status": "installed"}

    monkeypatch.setattr(mod, "install", installed)
    assert mod.main(["--source", "owner/repo", "--plugin", "sample"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "installed"
    assert seen[-1]["approved_plugins"] is None
    assert mod.main([
        "--source", "owner/repo", "--ref", PINNED, "--plugin", "app",
        "--approved-plugin", "base", "--approved-plugin", "app",
    ]) == 0
    capsys.readouterr()
    assert seen[-1]["approved_plugins"] == ["base", "app"]

    def invalid(**kwargs):
        raise mod.InstallError("broken")

    monkeypatch.setattr(mod, "install", invalid)
    assert mod.main(["--source", "owner/repo", "--plugin", "sample"]) == 3
    assert json.loads(capsys.readouterr().out) == {
        "status": "invalid",
        "error": "broken",
    }
