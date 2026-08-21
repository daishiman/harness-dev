from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync-codex-project-settings.py"
SPEC = importlib.util.spec_from_file_location("sync_codex_project_settings", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

PROJECTOR_SCRIPT = SCRIPT.with_name("sync-plugin-platforms.py")
PROJECTOR_SPEC = importlib.util.spec_from_file_location("sync_plugin_platforms", PROJECTOR_SCRIPT)
projector = importlib.util.module_from_spec(PROJECTOR_SPEC)
PROJECTOR_SPEC.loader.exec_module(projector)


def fixture(tmp_path, *, delivery="plugin", products=None):
    # delivery=plugin の hook は Codex に届かない (plugin_hooks が removed)。
    # 既定の products を delivery から導き、fixture 自体が到達不能な主張を
    # 持たないようにする。契約違反そのものを試す test だけが products を明示する。
    products = products if products is not None else (
        ["claude"] if delivery == "plugin" else ["codex"]
    )
    products = json.dumps(products)
    repo = tmp_path / "repo"
    (repo / ".codex").mkdir(parents=True)
    beads = {"hooks": {"SessionStart": [{"matcher": "startup|resume|clear", "hooks": [
        {"type": "command", "command": "bd codex-hook SessionStart"}
    ]}]}}
    (repo / ".codex" / "hooks.json").write_text(json.dumps(beads, indent=2) + "\n")
    (repo / ".codex" / "config.toml").write_text("model = \"test\"\n\n[features]\nhooks = false\n")
    plugin = repo / "plugins" / "harness-creator" / ".codex-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"name":"harness-creator"}\n')
    discovery = repo / ".agents" / "plugins"
    discovery.mkdir(parents=True)
    (discovery / "marketplace.json").write_text(json.dumps({"plugins": [{
        "name": "harness-creator", "source": {"source": "local", "path": "./plugins/harness-creator"}
    }]}))
    contract = repo / "native-surfaces.toml"
    contract.write_text(f'''schema_version = 1
[activation]
codex_discovery = ".agents/plugins/marketplace.json"
[codex]
hooks_file = ".codex/hooks.json"
config_file = ".codex/config.toml"
features_hooks = true
[discovery]
marketplace_name = "fixture-marketplace"
plugin_name = "harness-creator"
source_path = "./plugins/harness-creator"
installation = "AVAILABLE"
authentication = "ON_INSTALL"
category = "Internal-Tooling"
distributable = false
scope = "repo-internal"
activation_requires = ["user-install", "user-enable", "user-hook-trust"]
[[hooks]]
id = "sync"
owner = "harness-creator"
event = "SessionStart"
matcher = "startup|resume|clear"
command = "python3 $CLAUDE_PLUGIN_ROOT/hooks/auto-sync.py"
delivery = "{delivery}"
products = {products}
''')
    return repo, contract


def test_plugin_delivery_preserves_beads_and_does_not_duplicate_project_hook(tmp_path):
    repo, contract = fixture(tmp_path)
    report, code = mod.run(repo, contract, "apply")
    assert code == 0 and report["delivery"] == {"sync": "plugin"}
    hooks = json.loads((repo / ".codex" / "hooks.json").read_text())
    commands = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
    assert commands == ["bd codex-hook SessionStart"]
    config = (repo / ".codex" / "config.toml").read_text()
    assert 'model = "test"' in config and "hooks = true" in config
    assert "[hooks]" not in config
    assert mod.run(repo, contract, "check")[1] == 0


def test_project_delivery_is_generated_once_and_idempotent(tmp_path):
    repo, contract = fixture(tmp_path, delivery="project")
    assert mod.run(repo, contract, "apply")[1] == 0
    assert mod.run(repo, contract, "apply")[1] == 0
    hooks = json.loads((repo / ".codex" / "hooks.json").read_text())
    commands = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
    assert commands.count(
        "python3 $CLAUDE_PLUGIN_ROOT/hooks/auto-sync.py # harness-managed:harness-creator:sync"
    ) == 1
    assert commands.count("bd codex-hook SessionStart") == 1


def test_discovery_requires_corresponding_codex_manifest(tmp_path):
    repo, contract = fixture(tmp_path)
    (repo / "plugins" / "harness-creator" / ".codex-plugin" / "plugin.json").unlink()
    try:
        mod.run(repo, contract, "check")
    except mod.ContractError as exc:
        assert "lacks Codex manifest" in str(exc)
    else:
        raise AssertionError("missing manifest accepted")


def test_missing_discovery_is_left_for_platform_projector(tmp_path):
    repo, contract = fixture(tmp_path)
    discovery = repo / ".agents" / "plugins" / "marketplace.json"
    discovery.unlink()
    report, code = mod.run(repo, contract, "apply")
    assert code == 0
    assert ".agents/plugins/marketplace.json" not in report["paths"]
    assert not discovery.exists()
    assert mod.run(repo, contract, "check")[1] == 0


def test_platform_projector_remains_only_marketplace_writer(tmp_path):
    repo, contract = fixture(tmp_path)
    for name in ("harness-creator", "zeta-plugin"):
        manifest = repo / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({
                "name": name,
                "version": "1.0.0",
                "description": f"{name} fixture",
                "author": {"name": "fixture"},
            }) + "\n",
            encoding="utf-8",
        )

    assert projector.run_all(
        repo=repo, mode="apply", marketplace_name="fixture-marketplace"
    )[1] == 0
    discovery = repo / ".agents" / "plugins" / "marketplace.json"
    projector_bytes = discovery.read_bytes()

    report, code = mod.run(repo, contract, "apply")

    assert code == 0
    assert ".agents/plugins/marketplace.json" not in report["paths"]
    assert discovery.read_bytes() == projector_bytes
    assert projector.run_all(
        repo=repo, mode="check", marketplace_name="fixture-marketplace"
    )[1] == 0


def test_project_delivery_update_replaces_prior_managed_generation(tmp_path):
    repo, contract = fixture(tmp_path, delivery="project")
    assert mod.run(repo, contract, "apply")[1] == 0
    text = contract.read_text().replace("auto-sync.py", "auto-sync-v2.py")
    contract.write_text(text)
    assert mod.run(repo, contract, "apply")[1] == 0
    hooks = json.loads((repo / ".codex" / "hooks.json").read_text())
    commands = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
    managed = [command for command in commands if "# harness-managed:harness-creator:sync" in command]
    assert managed == [
        "python3 $CLAUDE_PLUGIN_ROOT/hooks/auto-sync-v2.py # harness-managed:harness-creator:sync"
    ]


def test_malformed_existing_hooks_fail_closed(tmp_path):
    repo, contract = fixture(tmp_path)
    (repo / ".codex" / "hooks.json").write_text('{"hooks":{"SessionStart":{}}}\n')
    try:
        mod.run(repo, contract, "check")
    except mod.ContractError as exc:
        assert "events must map to arrays" in str(exc)
    else:
        raise AssertionError("malformed hooks accepted")


def test_multi_file_apply_failure_restores_every_preimage(tmp_path, monkeypatch):
    repo, contract = fixture(tmp_path, delivery="project")
    paths = [
        repo / ".codex" / "hooks.json",
        repo / ".codex" / "config.toml",
    ]
    before = {path: path.read_bytes() for path in paths}
    original = mod.atomic_write
    calls = 0

    def fail_second_write(path, text):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second-write failure")
        return original(path, text)

    monkeypatch.setattr(mod, "atomic_write", fail_second_write)
    with pytest.raises(mod.ContractError, match="preimages were restored"):
        mod.run(repo, contract, "apply")
    assert {path: path.read_bytes() for path in paths} == before


def test_inline_hooks_rejected_to_prevent_same_layer_double_load(tmp_path):
    repo, contract = fixture(tmp_path)
    (repo / ".codex" / "config.toml").write_text("[features]\nhooks=true\n[hooks]\n")
    try:
        mod.run(repo, contract, "check")
    except mod.ContractError as exc:
        assert "inline [hooks] is forbidden" in str(exc)
    else:
        raise AssertionError("inline hooks accepted")


def test_contract_cannot_redirect_child_writes_outside_exact_managed_paths(tmp_path):
    repo, contract = fixture(tmp_path)
    text = contract.read_text().replace(
        'hooks_file = ".codex/hooks.json"', 'hooks_file = "outside.json"'
    )
    contract.write_text(text)
    try:
        mod.run(repo, contract, "apply")
    except mod.ContractError as exc:
        assert "must be confined" in str(exc)
    else:
        raise AssertionError("redirected child write accepted")
    assert not (repo / "outside.json").exists()


def test_plugin_delivery_cannot_claim_codex_reach(tmp_path):
    """delivery=plugin + products=codex は到達不能な主張なので契約段階で落ちること。

    projector は plugin delivery の handler を .codex/hooks.json から除去するため、
    この組合せを許すと「Codex でも動く」と宣言しながら実体は Codex を外れる。
    Codex への配達は build-hook-registry.py が生成する project 層 router が担う。
    """
    repo, contract = fixture(tmp_path, delivery="plugin", products=["claude", "codex"])
    with pytest.raises(mod.ContractError, match="cannot reach Codex"):
        mod.run(repo, contract, "check")
