#!/usr/bin/env python3
# /// script
# name: hook-post-compact
# purpose: PostCompact hook — rehydrate context from handoff snapshot.
# inputs:
#   - stdin: Claude Code PostCompact hook JSON
# outputs:
#   - stdout: rehydration prompt
#   - exit: 0=OK
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""PostCompact hook: after context compaction, read the latest handoff
snapshot and print a rehydration prompt to stdout so Claude can resume.
patch: PF-G3-001 — PostCompact hook 追加
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path


HANDOFF_DIR = Path(os.environ.get("CLAUDE_HANDOFF_DIR", ".claude/handoff"))


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    snapshots = sorted(HANDOFF_DIR.glob("*.md")) if HANDOFF_DIR.exists() else []
    if not snapshots:
        # no handoff found — no-op
        return 0

    latest = snapshots[-1]
    try:
        content = latest.read_text(encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"hook-post-compact: cannot read handoff ({e})\n")
        return 0

    # Print rehydration hint to stdout for Claude to read
    print(f"[PostCompact] Context restored from handoff snapshot: {latest.name}")
    print("--- HANDOFF SUMMARY (first 1000 chars) ---")
    print(content[:1000])
    print("--- END HANDOFF SUMMARY ---")
    print("Please resume from the state described above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
