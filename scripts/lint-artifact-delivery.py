#!/usr/bin/env python3
"""Fail closed on artifact-delivery policy/projection drift."""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
GENERATOR = HERE / "build-artifact-delivery.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("artifact_delivery_generator", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator: {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    args = parser.parse_args(argv)
    module = _load_generator()
    root = args.repo_root.resolve()
    errors = module.lint_repository(root)
    if errors:
        for error in errors:
            print(f"ARTIFACT_DELIVERY_ERROR: {error}", file=sys.stderr)
        return 1
    print(f"ARTIFACT_DELIVERY_OK: {len(module.discover_plugin_dirs(root))} plugins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
