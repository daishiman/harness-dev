#!/usr/bin/env python3
"""Forward the historical Harness Creator path to the distributable adapter."""
from __future__ import annotations

import runpy
from pathlib import Path


CANONICAL_PATH = (
    Path(__file__).resolve().parents[4]
    / "skill-governance-adapters"
    / "scripts"
    / "build-external-intelligence-runtime.py"
)


def _forward() -> dict[str, object]:
    if not CANONICAL_PATH.is_file():
        raise RuntimeError(
            "external-intelligence provider is unavailable; install "
            "skill-governance-adapters or use a standard bundle"
        )
    return runpy.run_path(
        str(CANONICAL_PATH), run_name="__main__" if __name__ == "__main__" else None
    )


if __name__ == "__main__":
    _forward()
else:
    globals().update(
        {
            key: value
            for key, value in _forward().items()
            if key not in {"__name__", "__file__", "__package__", "__spec__", "__loader__"}
        }
    )
