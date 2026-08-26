"""Native manifest と Harness package contract の責務分離を固定する。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate-plugin-completeness.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_plugin_completeness", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_current_plugin_contract_is_complete():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=PLUGIN_ROOT
    )
    assert result.returncode == 0, result.stderr


def test_native_manifest_references_hooks_without_duplicating_catalog_metadata():
    catalog_manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    native_manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert "hooks" not in catalog_manifest
    assert native_manifest["hooks"] == "./hooks/hooks.json"
    assert {"entry_points", "distributable", "bundle_targets"}.isdisjoint(native_manifest)


def test_missing_contract_hook_is_detected():
    mod = _load()
    contract = json.loads((PLUGIN_ROOT / "references" / "package-contract.json").read_text())
    contract["entry_points"]["hooks"] = []
    errors: list[str] = []
    mod.check_entry_points(errors, contract)
    assert any("entry_points.hooks mismatch" in error for error in errors)


def test_dangling_hook_command_is_detected(tmp_path, monkeypatch):
    mod = _load()
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/missing.py",
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    monkeypatch.setattr(mod, "PLUGIN_ROOT", root)
    errors: list[str] = []
    mod.check_hooks(
        errors,
        {"hooks": "./hooks/hooks.json"},
        {"entry_points": {"hooks": ["missing.py"]}},
    )
    assert "hook command target missing: hooks/missing.py" in errors


def test_distribution_rejects_empty_bundle_for_distributable_plugin():
    mod = _load()
    errors: list[str] = []
    mod.check_distribution(
        errors,
        {"distribution": {"distributable": True, "bundle_targets": []}},
    )
    assert "package-contract bundle_targets must not be empty when distributable=true" in errors
