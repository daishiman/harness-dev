#!/usr/bin/env python3
# /// script
# name: build-external-intelligence-runtime
# purpose: 旧来の run-build-skill の path を保つ転送口。実体は skill-governance-adapters の scripts/build-external-intelligence-runtime.py で、plugin_resources.forward_external_intelligence が解決して実行する
# inputs:
#   - argv / stdin / env: 転送先の script と同じ
# outputs:
#   - 転送先の stdout・stderr・exit code をそのまま返す。転送先を解決できなければ RuntimeError
# requires-python: ">=3.10"
# dependencies: [../../../scripts/plugin_resources.py]
# contexts: [A, C, E]
# network: false
# write-scope: 転送先の script の write-scope に従う
# ///
"""Forward the historical Harness Creator path to the distributable adapter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from plugin_resources import forward_external_intelligence

forward_external_intelligence(globals(), provider="skill-governance-adapters")
