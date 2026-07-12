#!/usr/bin/env python3
"""UserPromptSubmit hook: stale 時のみ cache refresh。常に exit 0。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTIFIER = HERE / "notifier-check.py"


# 本ファイル: plugins/harness-creator/skills/run-skill-update-notifier/scripts/hook-cache-refresh.py
# __file__.parents[3] = plugin-root (harness-creator)、parents[4] = plugins/。
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def _plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env).resolve()
    return PLUGIN_ROOT


def _plugins_root() -> Path:
    """notifier-check が走査する「複数 plugin を含む plugins/ ディレクトリ」を
    cwd 非依存で self-relative に解決する。

    解決順:
      1. env `CLAUDE_PLUGIN_ROOT` (= 単一 plugin ルート、慣習) があればその親 = plugins/。
         install 先 / dev いずれも同一の plugins/ を指す。
      2. 無ければ本ファイル位置から導出。plugin-root (parents[3]) の親 = plugins/。
    notifier-check.py:cmd_refresh は渡された root を glob("*/") で走査し各 subdir を
    plugin として扱うため、単一 plugin ルートではなく plugins/ を渡すのが正しい意味。
    """
    return _plugin_root().parent


def main() -> int:
    try:
        status = subprocess.run(
            ["python3", str(NOTIFIER), "cache-status"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if status in ("stale", "absent"):
            subprocess.run(
                ["python3", str(NOTIFIER), "refresh",
                 "--plugins-root", str(_plugins_root()),
                 "--plugin-root", str(_plugin_root())],
                capture_output=True, text=True, timeout=15,
            )
    except Exception as exc:
        print(f"[notifier-hook] skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
