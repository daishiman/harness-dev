#!/usr/bin/env python3
"""Load Python packages bundled with the skill-intake plugin.

The plugin must work after install without asking users to run pip manually.
Scripts that need third-party packages call `activate()` before importing them.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
VENDOR_DIR = PLUGIN_ROOT / "vendor" / "python"

def activate() -> Path:
    if VENDOR_DIR.exists():
        vendor = str(VENDOR_DIR)
        if vendor not in sys.path:
            sys.path.insert(0, vendor)
    return VENDOR_DIR
