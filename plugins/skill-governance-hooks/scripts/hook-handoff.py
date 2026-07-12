#!/usr/bin/env python3
# /// script
# name: hook-handoff
# purpose: PreCompact handoff snapshot to project-local .claude/handoff/
# inputs:
#   - stdin: Claude Code PreCompact hook JSON
# outputs:
#   - file: .claude/handoff/<timestamp>.md
#   - exit: 0=OK
# contexts: [C]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""PreCompact hook: serialize current progression state to a timestamped
markdown file so post-compact context can rehydrate.
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import sys
from pathlib import Path


OUT_DIR = Path(os.environ.get("CLAUDE_HANDOFF_DIR", ".claude/handoff"))


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        out = OUT_DIR / f"{ts}.md"
        cwd = os.getcwd()
        session_id = data.get("session_id", "")
        trigger = data.get("trigger", "PreCompact")
        body = [
            f"# Handoff snapshot {ts}",
            "",
            f"- trigger: {trigger}",
            f"- session_id: {session_id}",
            f"- cwd: {cwd}",
            "",
            "## Raw hook payload",
            "",
            "```json",
            json.dumps(data, ensure_ascii=False, indent=2)[:8000],
            "```",
        ]
        out.write_text("\n".join(body), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"hook-handoff: skipped ({e})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
