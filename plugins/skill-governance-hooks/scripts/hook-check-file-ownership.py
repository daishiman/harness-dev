#!/usr/bin/env python3
# /// script
# name: hook-check-file-ownership
# purpose: TaskCreated hook: block Agent Team file ownership collisions.
# inputs:
#   - stdin: Claude Code TaskCreated hook JSON
# outputs:
#   - stdout: hookSpecificOutput JSON / exit 0=allow / 2=deny
# contexts: [C]
# network: false
# write-scope: .claude/logs
# dependencies: []
# ///
"""TaskCreated hook for Agent Team file ownership.

Reads JSON from stdin. If the new task declares `files` or `file_ownership`,
the hook records ownership and blocks when an active task already owns a file.
Missing ownership is allowed because not every task edits files.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


STATE_FILE = Path(os.environ.get("CLAUDE_TASK_OWNERSHIP_STATE", ".claude/logs/task-ownership.json"))


def load_state() -> dict[str, list[str]]:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict[str, list[str]]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    task_id = str(data.get("task_id") or data.get("id") or "")
    files = data.get("files") or data.get("file_ownership") or []
    if not task_id or not isinstance(files, list) or not files:
        return 0

    state = load_state()
    active = {path: owner for owner, paths in state.items() for path in paths}
    conflicts = [path for path in files if path in active and active[path] != task_id]
    if conflicts:
        sys.stderr.write(
            "hook-check-file-ownership: "
            f"task {task_id} conflicts on {conflicts} "
            f"(owned by {[active[path] for path in conflicts]})\n"
        )
        return 2

    state[task_id] = [str(path) for path in files]
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
