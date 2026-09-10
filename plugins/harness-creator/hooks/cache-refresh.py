#!/usr/bin/env python3
# /// script
# name: cache-refresh
# purpose: hook capability "cache-refresh" の公開 entry point。実処理は skill 所有 script へ委譲する。
# inputs:
#   - stdin: Claude Code hook event JSON
#   - argv: hook runner が渡す引数
# outputs:
#   - 委譲先 script の stdout/stderr/exit code をそのまま返す
# ///
"""Public hook entry point that delegates to its owning skill script.

The implementation stays with the skill that owns the rule, while the plugin
exposes exactly one file per declared hook capability.  Delegation uses execv so
the hook event JSON on stdin and the process exit code pass through untouched.
"""
import os
import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent.parent / "skills/run-skill-update-notifier/scripts/hook-cache-refresh.py"

if not TARGET.is_file():
    # 委譲先が無い状態で黙って成功すると、hook が働いていないのに緑に見える。
    print(f"cache-refresh: delegate target missing: {TARGET}", file=sys.stderr)
    raise SystemExit(1)

os.execv(sys.executable, [sys.executable, str(TARGET), *sys.argv[1:]])
