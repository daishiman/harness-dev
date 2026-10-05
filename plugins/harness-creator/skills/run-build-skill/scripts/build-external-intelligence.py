#!/usr/bin/env python3
"""Forward the historical Harness Creator path to the distributable engine."""
from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path


def _canonical_path() -> Path:
    """skill-governance-adapters の正本を、install 配置に依存せず解決する。

    親ディレクトリ起点の兄弟パスは install 先 (<cache>/<marketplace>/<plugin>/<version>/)
    で届かないので、harness-creator 同梱の scripts/extract-plugin-root.py に root を解かせる。
    見つからなければ実在しないパスを返し、_forward() の RuntimeError に任せる。
    """
    plugin_root = Path(__file__).resolve().parents[3]
    resolver = plugin_root / "scripts" / "extract-plugin-root.py"
    if not resolver.is_file():
        return Path("plugin:skill-governance-adapters/scripts/build-external-intelligence.py")
    spec = importlib.util.spec_from_file_location("_extract_plugin_root", resolver)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    found = module.resolve("skill-governance-adapters", plugin_root, Path.cwd())
    if found is None:
        return Path("plugin:skill-governance-adapters/scripts/build-external-intelligence.py")
    return Path(found) / "scripts" / "build-external-intelligence.py"


CANONICAL_PATH = _canonical_path()


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
