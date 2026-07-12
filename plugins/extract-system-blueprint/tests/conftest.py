from __future__ import annotations

# /// script
# name: extract-system-blueprint-test-conftest
# purpose: extract-system-blueprint のハイフン付き Python 実体を pytest へ安全にロードする共通 fixture
# inputs:
#   - pytest fixture request / tmp_path
# outputs:
#   - loaded module fixtures / JSON fixture writer
# contexts: [C, E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load_script(relative: str, module_name: str):
    path = PLUGIN_ROOT / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def authz():
    return load_script("scripts/authz-classify.py", "test_esb_authz")


@pytest.fixture(scope="session")
def fetch_snapshot():
    return load_script("scripts/fetch-snapshot.py", "test_esb_fetch_snapshot")


@pytest.fixture(scope="session")
def guard():
    return load_script("hooks/pre-fetch-authz-guard.py", "test_esb_guard")


@pytest.fixture(scope="session")
def mermaid():
    return load_script("scripts/mermaid-validate.py", "test_esb_mermaid")


@pytest.fixture(scope="session")
def doc_emit():
    return load_script("scripts/doc-emit.py", "test_esb_doc_emit")


@pytest.fixture(scope="session")
def browser_render():
    return load_script("scripts/browser-render.py", "test_esb_browser_render")


@pytest.fixture
def write_json():
    def write(path: Path, value) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    return write
