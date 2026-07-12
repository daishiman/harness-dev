#!/usr/bin/env python3
# /// script
# name: check-surface-inventory
# purpose: component-inventory.json が 5 component_kind の検討証跡と plugin-level surface 採否を漏れなく持つか検証する。
# inputs:
#   - argv: <component-inventory.json>
# outputs:
#   - stdout: OK summary
#   - stderr: surface inventory violations
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Surface inventory validator.

This gate separates "considered all plugin component kinds" from "generated all
component kinds". A plan may generate only the necessary components, but it must
show that every buildable kind and plugin-level surface was considered.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def run(path: Path) -> tuple[int, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 2, [f"JSON parse error: {exc}"]
    if not isinstance(data, dict):
        return 1, ["component-inventory root が object でない"]
    errors = specfm.validate_surface_inventory(data)
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="plugin surface inventory を検証する")
    ap.add_argument("inventory", help="component-inventory.json")
    args = ap.parse_args(argv)

    path = Path(args.inventory)
    if not path.is_file():
        sys.stderr.write(f"inventory not found: {path}\n")
        return 2
    code, errors = run(path)
    if code == 0:
        sys.stdout.write("OK: 5 component_kind 検討証跡 + plugin-level surface 採否が明示済み\n")
        return 0
    for err in errors:
        sys.stderr.write(err + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
