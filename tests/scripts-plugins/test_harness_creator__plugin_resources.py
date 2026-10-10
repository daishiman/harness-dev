"""HC's shared resolver bootstrap and historical provider entry points."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
HC = ROOT / "plugins" / "harness-creator"
SPEC = importlib.util.spec_from_file_location("hc_plugin_resources_test", HC / "scripts" / "plugin_resources.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def plugin(path: Path, name: str) -> Path:
    (path / ".claude-plugin").mkdir(parents=True)
    (path / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return path


def test_resolver_uses_each_caller_root_without_module_cache_aliasing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    for dirname in ("one", "two"):
        host = plugin(tmp_path / dirname / "harness-creator", "harness-creator")
        provider = plugin(host.parent / "provider", "provider")
        (host / "scripts").mkdir()
        (host / "scripts" / "extract-plugin-root.py").write_bytes((ROOT / "scripts" / "extract-plugin-root.py").read_bytes())
        assert MOD.resolve_root("provider", host, tmp_path) == provider.resolve()
    with pytest.raises(MOD.ResolverUnavailable, match="extract-plugin-root.py is missing"):
        MOD.resolve_root("provider", tmp_path / "missing", tmp_path)


@pytest.mark.parametrize("filename", ["build-external-intelligence.py", "build-external-intelligence-runtime.py"])
def test_historical_forwarder_runs_and_exports_provider_from_cache(tmp_path, filename):
    config = tmp_path / "config path"
    cache = config / "plugins" / "cache" / "market"
    host = plugin(cache / "harness-creator" / "1.0.0", "harness-creator")
    provider = plugin(cache / "skill-governance-adapters" / "1.0.0", "skill-governance-adapters")
    for file in ("extract-plugin-root.py", "plugin_resources.py"):
        target = host / "scripts" / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((HC / "scripts" / file).read_bytes())
    wrapper = host / "skills" / "run-build-skill" / "scripts" / filename
    wrapper.parent.mkdir(parents=True)
    wrapper.write_bytes((HC / "skills" / "run-build-skill" / "scripts" / filename).read_bytes())
    target = provider / "scripts" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('EXPORTED = "provider-api"\nif __name__ == "__main__": print("provider-cli")\n', encoding="utf-8")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config), CODEX_HOME=str(tmp_path / "codex"))
    cli = subprocess.run([sys.executable, str(wrapper)], env=env, cwd=tmp_path,
                         capture_output=True, text=True, check=False)
    assert cli.returncode == 0, cli.stderr
    assert cli.stdout.strip() == "provider-cli"
    code = "import json, runpy, sys; n=runpy.run_path(sys.argv[1]); print(json.dumps([n['EXPORTED'], n['__file__']]))"
    imported = subprocess.run([sys.executable, "-c", code, str(wrapper)], env=env, cwd=tmp_path,
                              capture_output=True, text=True, check=False)
    assert imported.returncode == 0, imported.stderr
    assert json.loads(imported.stdout) == ["provider-api", str(wrapper)]
    target.unlink()
    missing = subprocess.run([sys.executable, str(wrapper)], env=env, cwd=tmp_path,
                             capture_output=True, text=True, check=False)
    assert missing.returncode != 0
    assert "external-intelligence provider is unavailable; install skill-governance-adapters" in missing.stderr
