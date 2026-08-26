"""vendor additive 宣言と semantic 実装集合の drift を fail-closed に固定する。"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN_ROOT / "scripts" / "lint-vendor-parity.py"
MANIFEST = PLUGIN_ROOT / "vendor" / "vendor-digest-manifest.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("lint_vendor_parity", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_current_additive_manifest_matches_semantic_contracts() -> None:
    assert mod.validate_additive_runtime_manifest(_manifest()) == []


def test_undeclared_additive_implementation_fails_closed() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["additive_managed"].pop("vendor/scripts/playwright-runtime.js")
    errors = mod.validate_additive_runtime_manifest(manifest)
    assert errors == [
        "vendor/scripts/playwright-runtime.js: additive implementation missing from manifest"
    ]


def test_manifest_only_additive_entry_fails_closed() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["additive_managed"]["vendor/scripts/orphan.js"] = {
        "strategy": "semantic-additive"
    }
    errors = mod.validate_additive_runtime_manifest(manifest)
    assert errors == [
        "vendor/scripts/orphan.js: manifest additive entry has no semantic contract"
    ]
