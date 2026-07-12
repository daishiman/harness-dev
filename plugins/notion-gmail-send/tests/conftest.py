# /// script
# name: conftest
# purpose: pytest 共通設定。plugin root を import パスに追加し `from lib import ...` を可能にする。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""pytest 共通設定: plugin root を import パスに追加し `from lib import ...` を可能にする。"""
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
