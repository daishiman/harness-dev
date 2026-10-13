# /// script
# name: validate_build_trace_shim
# purpose: import 用の shim。ハイフン入りの validate-build-trace.py を読み込み、正規表現の SSOT（LAYER_YAML_PATH_PATTERNS）を再エクスポートする
# inputs:
#   - import のみ（CLI ではない）
# outputs:
#   - module 属性: LAYER_YAML_PATH_PATTERNS, SKILL_LOCAL_V1_RE
# requires-python: ">=3.10"
# dependencies: [validate-build-trace.py]
# contexts: [C]
# network: false
# write-scope: none
# ///
"""SSOT 共有用 shim.

Python の import はハイフンを許さないため、ハイフン入りファイル名
`validate-build-trace.py` のシンボルを直接 import できない。
このモジュールは importlib で当該ファイルをロードし、
正規表現 SSOT (LAYER_YAML_PATH_PATTERNS) を再エクスポートする。

二重定義禁止 ([[project_ssot_dedup_mechanism]]): 本ファイルでは正規表現を
再定義せず、必ず validate-build-trace.py から取得する。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "validate-build-trace.py"
_spec = importlib.util.spec_from_file_location("_validate_build_trace", _SRC)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise ImportError(f"cannot load {_SRC}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

LAYER_YAML_PATH_PATTERNS = _mod.LAYER_YAML_PATH_PATTERNS
SKILL_LOCAL_V1_RE = LAYER_YAML_PATH_PATTERNS["skill-local-v1"]

__all__ = ["LAYER_YAML_PATH_PATTERNS", "SKILL_LOCAL_V1_RE"]
