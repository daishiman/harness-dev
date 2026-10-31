#!/usr/bin/env python3
"""Read-only stand-in for the bd CLI in this live-trial fixture (pr86 decompose86).

It answers only the two read calls that bd-bridge.py makes before any Beads operation:
`bd version` and `bd where --json`. Every other argv (create, dep, show, update, close, ready, ...)
is refused with exit 4 and no stdout, so no Beads issue or edge can be written through this fixture.
Every call, answered or refused, is appended as one JSON line to `fake-bd-calls.jsonl` in the fixture
root. There is no database and no network access; the workspace reported by `where` does not exist.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "fake-bd-calls.jsonl"
VERSION = "bd version 1.4.2 (live-trial fixture read-only stand-in)"
WHERE = {"database_path": "fixture-readonly://decompose86/.beads/beads.db", "prefix": "gm4b", "schema_version": "1"}


def main(argv: list[str]) -> int:
    if argv == ["version"]:
        out, rc = VERSION, 0
    elif argv == ["where", "--json"]:
        out, rc = json.dumps(WHERE), 0
    else:
        out, rc = None, 4
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "answered": rc == 0, "exit": rc}) + "\n")
    if out is None:
        print("fake-bd: refused, this fixture answers only `version` and `where --json`: " + " ".join(argv),
              file=sys.stderr)
    else:
        print(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
