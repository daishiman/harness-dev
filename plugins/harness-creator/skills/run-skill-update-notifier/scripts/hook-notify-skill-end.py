#!/usr/bin/env python3
"""PostToolUse hook (matcher=Skill): Skill 実行末尾に 1 行通知。常に exit 0。

stdin の payload から plugin 名を推定し、notifier-check.py --mode notify を呼ぶ。
plugin 名が特定できない場合は no-op (graceful degradation)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTIFIER = HERE / "notifier-check.py"


def _extract_plugin_name(payload: dict) -> str | None:
    # Skill tool の payload には skill 名 (e.g., "harness-creator:run-skill-create") が入る想定。
    # plugin prefix が無い場合 (built-in skill 等) は None を返す。
    skill_name = (
        payload.get("tool_input", {}).get("skill")
        or payload.get("tool_input", {}).get("skill_name")
        or ""
    )
    if ":" in skill_name:
        return skill_name.split(":", 1)[0]
    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if payload.get("tool_name") != "Skill":
            return 0
        plugin = _extract_plugin_name(payload)
        if not plugin:
            return 0
        result = subprocess.run(
            ["python3", str(NOTIFIER), "notify", "--plugin", plugin],
            capture_output=True, text=True, timeout=5,
        )
        line = result.stdout.strip()
        if line:
            print(line)
    except Exception as exc:
        print(f"[notifier-hook] skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
