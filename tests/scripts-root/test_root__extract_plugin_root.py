"""scripts/extract-plugin-root.py の検査。

`${PLUGIN_ROOT}/../<plugin>` は repo の plugins/ でしか兄弟に届かない。install 先は
`<cache>/<marketplace>/<plugin>/<version>/` なので、`..` の先は同じ plugin の別 version 群になる。
本テストは repo / Claude cache / Codex cache の各配置で、resolver が
「同じ marketplace の現行 install」を返し、名前の違う dir や他プロジェクト専用 install を拾わないことを固定する。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "extract-plugin-root.py"


def _load():
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load()


def _plugin(root: pathlib.Path, name: str, host: str = ".claude-plugin") -> pathlib.Path:
    (root / host).mkdir(parents=True, exist_ok=True)
    (root / host / "plugin.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return root


@pytest.fixture
def homes(tmp_path, monkeypatch):
    claude = tmp_path / "claude-home"
    codex = tmp_path / "codex-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("CODEX_HOME", str(codex))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return claude, codex


def _installed(claude: pathlib.Path, plugins: dict) -> None:
    path = claude / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8")


def test_repo_layout_resolves_sibling(tmp_path, homes):
    me = _plugin(tmp_path / "plugins" / "dev-graph", "dev-graph")
    guard = _plugin(tmp_path / "plugins" / "skill-governance-adapters", "skill-governance-adapters")
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == guard.resolve()


def test_own_name_returns_self(tmp_path, homes):
    me = _plugin(tmp_path / "plugins" / "skill-governance-adapters", "skill-governance-adapters")
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == me.resolve()


def test_claude_cache_prefers_same_marketplace_over_newer_other_marketplace(tmp_path, homes):
    claude, _ = homes
    cache = claude / "plugins" / "cache"
    me = _plugin(cache / "harness-local" / "dev-graph" / "0.1.14", "dev-graph")
    ours = _plugin(cache / "harness-local" / "skill-governance-adapters" / "0.1.10", "skill-governance-adapters")
    _plugin(cache / "harness-hub" / "skill-governance-adapters" / "9.9.9", "skill-governance-adapters")
    # `<root>/..` は同じ plugin の version 群なので、兄弟としては見つからない。
    assert not (me.parent / "skill-governance-adapters").exists()
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == ours.resolve()


def test_installed_plugins_json_beats_highest_cached_version(tmp_path, homes):
    claude, _ = homes
    cache = claude / "plugins" / "cache"
    me = _plugin(cache / "harness-local" / "dev-graph" / "0.1.14", "dev-graph")
    current = _plugin(cache / "harness-local" / "skill-governance-adapters" / "0.1.9", "skill-governance-adapters")
    _plugin(cache / "harness-local" / "skill-governance-adapters" / "0.1.10", "skill-governance-adapters")
    _installed(claude, {
        "skill-governance-adapters@harness-local": [
            {"scope": "user", "installPath": str(current), "version": "0.1.9"},
        ],
    })
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == current.resolve()


def test_other_project_install_is_ignored_and_own_project_wins(tmp_path, homes):
    claude, _ = homes
    cache = claude / "plugins" / "cache"
    me = _plugin(cache / "harness-local" / "dev-graph" / "0.1.14", "dev-graph")
    elsewhere = _plugin(tmp_path / "elsewhere" / "sga", "skill-governance-adapters")
    mine = _plugin(tmp_path / "mine" / "sga", "skill-governance-adapters")
    user = _plugin(tmp_path / "user" / "sga", "skill-governance-adapters")
    project = tmp_path / "work"
    (project / "sub").mkdir(parents=True)
    _installed(claude, {
        "skill-governance-adapters@harness-local": [
            {"scope": "project", "projectPath": str(tmp_path / "other"), "installPath": str(elsewhere)},
            {"scope": "user", "installPath": str(user)},
            {"scope": "project", "projectPath": str(project), "installPath": str(mine)},
        ],
    })
    assert MOD.resolve("skill-governance-adapters", me, project / "sub") == mine.resolve()
    assert MOD.resolve("skill-governance-adapters", me, tmp_path / "other-cwd") == user.resolve()


@pytest.mark.parametrize("scope", ["project", "local"])
@pytest.mark.parametrize("market", ["harness-local", "other-market"])
def test_other_project_cache_is_not_reselected(tmp_path, homes, scope, market):
    claude, _ = homes
    cache = claude / "plugins" / "cache"
    me = _plugin(cache / "harness-local" / "dev-graph" / "0.1.14", "dev-graph")
    private = _plugin(cache / market / "skill-governance-adapters" / "1.0.0", "skill-governance-adapters")
    _installed(claude, {
        f"skill-governance-adapters@{market}": [{
            "scope": scope, "projectPath": str(tmp_path / "other-project"),
            "installPath": str(private),
        }],
    })
    assert MOD.resolve("skill-governance-adapters", me, tmp_path / "current-project") is None
    assert MOD.resolve("skill-governance-adapters", me, tmp_path / "other-project") == private.resolve()


def test_cache_shared_with_user_registration_remains_available(tmp_path, homes):
    claude, _ = homes
    cache = claude / "plugins" / "cache" / "harness-local"
    me = _plugin(cache / "dev-graph" / "0.1.14", "dev-graph")
    shared = _plugin(cache / "skill-governance-adapters" / "1.0.0", "skill-governance-adapters")
    _installed(claude, {
        "skill-governance-adapters@harness-local": [
            {"scope": "project", "projectPath": str(tmp_path / "other-project"), "installPath": str(shared)},
            {"scope": "user", "installPath": str(shared)},
        ],
    })
    assert MOD.resolve("skill-governance-adapters", me, tmp_path / "current-project") == shared.resolve()


def test_codex_cache_layout_resolves_same_marketplace(tmp_path, homes):
    _, codex = homes
    cache = codex / "plugins" / "cache" / "harness-dev"
    me = _plugin(cache / "dev-graph" / "0.1.14", "dev-graph", host=".codex-plugin")
    guard = _plugin(cache / "skill-governance-adapters" / "0.1.10", "skill-governance-adapters", host=".codex-plugin")
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == guard.resolve()


def test_falls_back_to_other_marketplace_when_own_lacks_it(tmp_path, homes):
    claude, _ = homes
    cache = claude / "plugins" / "cache"
    me = _plugin(cache / "harness-local" / "dev-graph" / "0.1.14", "dev-graph")
    _plugin(cache / "harness-hub" / "skill-governance-adapters" / "0.1.0", "skill-governance-adapters")
    newest = _plugin(cache / "skills" / "skill-governance-adapters" / "0.2.0", "skill-governance-adapters")
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) == newest.resolve()


def test_directory_with_wrong_manifest_name_is_not_accepted(tmp_path, homes):
    me = _plugin(tmp_path / "plugins" / "dev-graph", "dev-graph")
    _plugin(tmp_path / "plugins" / "skill-governance-adapters", "something-else")
    assert MOD.resolve("skill-governance-adapters", me, tmp_path) is None


def test_cli_exit_codes(tmp_path, homes, capsys):
    me = _plugin(tmp_path / "plugins" / "dev-graph", "dev-graph")
    guard = _plugin(tmp_path / "plugins" / "skill-governance-adapters", "skill-governance-adapters")
    assert MOD.main(["skill-governance-adapters", "--from", str(me)]) == 0
    assert capsys.readouterr().out.strip() == str(guard.resolve())
    assert MOD.main(["missing-plugin", "--from", str(me)]) == 1
    assert "plugin not found: missing-plugin" in capsys.readouterr().err
    assert MOD.main(["../escape", "--from", str(me)]) == 2


def test_vendored_copy_resolves_from_its_own_plugin(tmp_path, homes):
    """vendor した複製は `--from` なしで自 plugin を起点にする (scripts/ の親が plugin root)。"""
    me = _plugin(tmp_path / "plugins" / "dev-graph", "dev-graph")
    guard = _plugin(tmp_path / "plugins" / "skill-governance-adapters", "skill-governance-adapters")
    (me / "scripts").mkdir()
    copy = me / "scripts" / "extract-plugin-root.py"
    copy.write_bytes(SCRIPT.read_bytes())
    import subprocess

    env = dict(os.environ)
    done = subprocess.run(
        [sys.executable, str(copy), "skill-governance-adapters"],
        capture_output=True, text=True, env=env, cwd=tmp_path, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == str(guard.resolve())


@pytest.mark.parametrize("host_space", [False, True])
def test_workflow_resolver_commands_quote_paths_and_stop_when_missing(tmp_path, homes, host_space):
    claude, _ = homes
    host = _plugin(tmp_path / ("host path" if host_space else "host"), "harness-creator")
    (host / "scripts").mkdir()
    (host / "scripts" / "extract-plugin-root.py").write_bytes(SCRIPT.read_bytes())
    provider = _plugin(tmp_path / "provider path", "skill-governance-automation")
    (provider / "scripts").mkdir()
    checker = provider / "scripts" / "build-manifest-registration-plan.py"
    checker.write_text("print('CHECKER_EXECUTED')\n", encoding="utf-8")
    _installed(claude, {"skill-governance-automation@market": [{"scope": "user", "installPath": str(provider)}]})
    manifest = json.loads((ROOT / "plugins/harness-creator/skills/run-skill-create/workflow-manifest.json").read_text())
    phase = next(p for p in manifest["phases"] if p["id"] == "manifest-register")
    env = dict(os.environ, PLUGIN_ROOT=str(host))
    done = subprocess.run(["bash", "-c", phase["command"]], env=env, cwd=tmp_path,
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "CHECKER_EXECUTED"
    _installed(claude, {})
    missing = subprocess.run(["bash", "-c", phase["command"]], env=env, cwd=tmp_path,
                             capture_output=True, text=True, check=False)
    assert missing.returncode in phase["fatal_exit_codes"]
    assert "plugin not found: skill-governance-automation" in missing.stderr
    assert "can't open file" not in missing.stderr
    assert "CHECKER_EXECUTED" not in missing.stdout
