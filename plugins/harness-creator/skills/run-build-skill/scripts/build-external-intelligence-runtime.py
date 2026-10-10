#!/usr/bin/env python3
"""Forward the historical Harness Creator path to the distributable adapter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from plugin_resources import forward_external_intelligence

forward_external_intelligence(globals())
