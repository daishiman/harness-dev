"""共通feedback skillの配布後動作。Notion通信・Keychain呼出しは禁止する。"""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "plugins/harness-creator/skills/run-skill-feedback"


def test_feedback_guard_remains_compatible_with_canonical_wiring():
    spec = importlib.util.spec_from_file_location("feedback_canonical_delivery", ROOT / "scripts/build-artifact-delivery.py")
    delivery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(delivery)
    delivery._validate_runtime_root_wiring(CANONICAL / "SKILL.md")
    delivery._validate_external_guard_wiring(CANONICAL / "SKILL.md")
RUNTIME_SCRIPTS = (
    "notion-submit-improvement.py",
    "notion_config.py",
    "tenant_runtime.py",
    "extract-plugin-root.py",
    "validate-inline-goal-seek-anchor.py",
)
# child から curl/security/socket へ到達したら、外部作用を起こさずテスト失敗にする。
BLOCK_EXTERNAL = """
import socket, subprocess
def blocked(*args, **kwargs):
    raise AssertionError("external process/network is forbidden in bundle tests")
socket.socket = blocked
socket.create_connection = blocked
subprocess.run = blocked
subprocess.check_output = blocked
subprocess.Popen = blocked
"""


@pytest.fixture
def bundle(tmp_path):
    plugin = tmp_path / "installed" / "sample-plugin" / "0.0.0"
    skill = plugin / "skills" / "run-skill-feedback"
    skill.parent.mkdir(parents=True)
    shutil.copytree(
        CANONICAL, skill,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".DS_Store"),
    )
    (plugin / ".claude-plugin").mkdir()
    (plugin / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "sample-plugin", "version": "0.0.0"})
    )
    cwd = tmp_path / "unrelated-project"
    cwd.mkdir()
    env = {
        key: value for key, value in os.environ.items()
        if key not in {
            "PYTHONPATH", "HARNESS_ROOT", "HC_ROOT", "CLAUDE_PLUGIN_ROOT",
            "HARNESS_TENANT", "HARNESS_TENANT_CONFIG", "INTAKE_ALLOW_ENV_TOKEN",
        } and not key.startswith("NOTION")
    }
    return plugin, skill, cwd, env


def _child(bundle, code, *args, env=None):
    _, _, cwd, default_env = bundle
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", BLOCK_EXTERNAL + code, *map(str, args)],
        cwd=cwd, env=env or default_env, capture_output=True, text=True,
        timeout=10,
    )


def test_isolated_bundle_dry_run_requires_no_repo_config_or_external_process(bundle):
    _, skill, _, _ = bundle
    result = _child(
        bundle,
        """
import runpy, sys
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
""",
        skill / "scripts/notion-submit-improvement.py",
        "--plugin", "sample-plugin", "--title", "bundle test",
        "--type", "バグ", "--desire", "offline validation", "--dry-run",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert "[CREATED]" not in result.stdout


def test_nested_loader_uses_owner_manifest_and_plugin_config(bundle):
    plugin, skill, _, _ = bundle
    (plugin / ".notion-config.json").write_text(json.dumps({"label": "owner-plugin"}))
    # skill直下をrootと誤認するとこちらを読んでしまう。
    (skill / ".notion-config.json").write_text(json.dumps({"label": "wrong-skill-root"}))
    result = _child(
        bundle,
        """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import notion_config as nc
assert nc.plugin_root() == Path(sys.argv[2]).resolve()
assert nc.load_config()["label"] == "owner-plugin"
print("owner plugin config")
""",
        skill / "scripts", plugin,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_config_wins_and_missing_explicit_path_fails_closed(bundle, tmp_path):
    plugin, skill, _, base_env = bundle
    (plugin / ".notion-config.json").write_text(json.dumps({"label": "owner-plugin"}))
    explicit = tmp_path / "explicit-config.json"
    explicit.write_text(json.dumps({"label": "explicit"}))
    code = """
import sys
sys.path.insert(0, sys.argv[1])
import notion_config as nc
print(nc.load_config()["label"])
"""
    env = dict(base_env, NOTION_CONFIG_PATH=str(explicit))
    result = _child(bundle, code, skill / "scripts", env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "explicit"
    env["NOTION_CONFIG_PATH"] = str(tmp_path / "missing-config.json")
    result = _child(bundle, code, skill / "scripts", env=env)
    assert result.returncode != 0
    assert "Refusing to fall back" in result.stderr


def test_runtime_resources_and_schemas_are_inside_copied_skill(bundle):
    plugin, skill, _, _ = bundle
    manifest = json.loads((skill / "workflow-manifest.json").read_text())
    scripts = {
        row["path"] for row in manifest["resources"] if row["type"] == "script"
    }
    assert scripts == {"scripts/" + name for name in RUNTIME_SCRIPTS}
    for row in manifest["resources"]:
        path = (skill / row["path"]).resolve()
        assert path.is_relative_to(plugin.resolve())
        assert path.is_file(), row["path"]
    for name in ("skill-list.schema.json", "improvement-request.schema.json"):
        assert isinstance(json.loads((skill / "schemas" / name).read_text()), dict)
    assert not (skill / "scripts/lint-feedback-protocol.py").exists()
    assert set(manifest["build_validation"]["lint_feedback_protocol"]["criteria"]) == {"IN1", "IN2"}


def test_missing_guard_stops_without_external_mutation(bundle, tmp_path):
    plugin, skill, _, _ = bundle
    result = _child(
        bundle,
        """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("resolver", sys.argv[1])
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)
resolver._claude_home = lambda: Path(sys.argv[3]) / "empty-claude"
resolver._codex_home = lambda: Path(sys.argv[3]) / "empty-codex"
raise SystemExit(resolver.main(["skill-governance-adapters", "--from", sys.argv[2]]))
""",
        skill / "scripts/extract-plugin-root.py", plugin, tmp_path,
    )
    assert result.returncode == 1
    assert not result.stdout.strip()
    assert "plugin not found: skill-governance-adapters" in result.stderr


def test_registered_guard_resolves_without_sibling_layout(bundle, tmp_path):
    plugin, skill, _, _ = bundle
    guard = tmp_path / "different-market" / "skill-governance-adapters" / "1.0"
    (guard / ".claude-plugin").mkdir(parents=True)
    (guard / ".claude-plugin/plugin.json").write_text(
        json.dumps({"name": "skill-governance-adapters"})
    )
    claude = tmp_path / "fake-claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "plugins/installed_plugins.json").write_text(json.dumps({
        "plugins": {"skill-governance-adapters@test": [
            {"scope": "user", "installPath": str(guard)}
        ]}
    }))
    result = _child(
        bundle,
        """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("resolver", sys.argv[1])
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)
resolver._claude_home = lambda: Path(sys.argv[3])
resolver._codex_home = lambda: Path(sys.argv[3]) / "empty-codex"
raise SystemExit(resolver.main(["skill-governance-adapters", "--from", sys.argv[2]]))
""",
        skill / "scripts/extract-plugin-root.py", plugin, claude,
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == guard.resolve()
