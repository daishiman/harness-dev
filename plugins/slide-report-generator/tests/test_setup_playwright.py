"""Plugin-local Playwright bootstrap contract tests (network-free)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "setup-playwright.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("setup_playwright_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def test_runtime_paths_stay_inside_plugin(tmp_path):
    paths = mod.runtime_paths(tmp_path)
    assert paths["browser_dir"] == tmp_path / "vendor" / "playwright-browsers"
    assert paths["playwright_cli"] == (
        tmp_path / "vendor" / "node_modules" / "playwright" / "cli.js"
    )
    assert paths["playwright_package"] == (
        tmp_path / "vendor" / "node_modules" / "playwright" / "package.json"
    )


def test_playwright_env_forces_plugin_local_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "/global/cache")
    paths = mod.runtime_paths(tmp_path)
    env = mod.playwright_env(paths)
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(
        tmp_path / "vendor" / "playwright-browsers"
    )


def test_inspect_missing_runtime_is_not_ready(tmp_path):
    (tmp_path / "vendor").mkdir()
    result = mod.inspect_runtime(tmp_path)
    assert result["ready"] is False
    assert result["detected"]["browser_dir"].startswith(str(tmp_path))
    assert result["detected"]["plugin_local"] is False
    assert result["detected"]["playwright_dependencies_current"] is False


def test_dependency_versions_detects_drift(tmp_path):
    paths = mod.runtime_paths(tmp_path)
    paths["package_lock"].parent.mkdir(parents=True)
    paths["package_lock"].write_text(
        json.dumps(
            {
                "packages": {
                    "node_modules/playwright": {"version": "1.60.0"},
                }
            }
        )
    )
    paths["playwright_package"].parent.mkdir(parents=True)
    paths["playwright_package"].write_text(json.dumps({"version": "1.59.0"}))
    versions = mod.dependency_versions(paths)
    assert versions == {
        "expected": "1.60.0",
        "installed": "1.59.0",
        "current": False,
    }


def test_cli_check_respects_relocated_srg_root(tmp_path):
    (tmp_path / "vendor").mkdir()
    env = os.environ.copy()
    env["SRG_ROOT"] = str(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--check"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ready"] is False
    assert payload["detected"]["browser_dir"] == str(
        tmp_path / "vendor" / "playwright-browsers"
    )
