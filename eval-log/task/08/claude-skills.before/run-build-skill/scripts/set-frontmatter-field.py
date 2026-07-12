#!/usr/bin/env python3
# /// script
# name: set-frontmatter-field
# purpose: Set or insert one SKILL.md frontmatter field without external YAML dependencies.
# inputs:
#   - argv: --file, --key, --value
# outputs:
#   - file: updated SKILL.md
#   - stderr: validation errors
# contexts: [A, B]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""SKILL.md frontmatter の特定フィールドを上書き (stdlib only)."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--value", required=True)
    args = ap.parse_args()
    p = Path(args.file)
    if not p.exists():
        print(f"file not found: {p}", file=sys.stderr)
        return 1
    lines = p.read_text().splitlines()
    if not lines or lines[0] != "---":
        print("no frontmatter", file=sys.stderr)
        return 1
    # find frontmatter end
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), -1)
    if end < 0:
        return 1
    new_line = f"{args.key}: {args.value}"
    # replace or insert
    for i in range(1, end):
        if lines[i].startswith(f"{args.key}:"):
            lines[i] = new_line
            break
    else:
        lines.insert(end, new_line)
    p.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
