#!/usr/bin/env python3
# 発火: PreToolUse:Bash hook (Claude Code)
# 副作用境界: stdout に警告 / stderr に拒否理由を出すのみ。git 実行はしない。
# 想定 input: {"tool_input": {"command": "git commit -m ..."}} 形式 JSON。
# exit code: 0=非ブロック(warn), 2=明示拒否(.env コミット等の致命パターン)。
"""git commit 前の preflight。--no-verify / --amend / .env 混入等を検出する."""
from __future__ import annotations

import json
import re
import sys

# 警告対象 (exit 0 + stdout): 慣習的に避けるべきフラグ
WARN_PATTERNS = [
    (re.compile(r"--no-verify\b"), "--no-verify はフック skip。ユーザ明示指示時のみ許容"),
    (re.compile(r"--amend\b"), "--amend は履歴改変。新規コミット推奨"),
    (re.compile(r"--no-gpg-sign\b"), "--no-gpg-sign は署名 bypass"),
    (re.compile(r"\bgit\s+add\s+(-A|\.|--all)\b"), "git add -A/. は秘密混入リスク"),
    (re.compile(r"\bgit\s+push\s+.*--force\b"), "force push は履歴破壊"),
]

# 明示拒否対象 (exit 2): 秘密ファイルの直接 add/commit
DENY_PATTERNS = [
    re.compile(r"\bgit\s+add\b[^&;|]*\.env(\b|$)"),
    re.compile(r"\bgit\s+add\b[^&;|]*credentials\.json"),
    re.compile(r"\bgit\s+commit\b[^&;|]*\.env(\b|$)"),
]


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def main() -> int:
    try:
        payload = _read_stdin_json()
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command") or ""
        if "git commit" not in command and "git add" not in command and "git push" not in command:
            return 0

        # 明示拒否
        for pat in DENY_PATTERNS:
            if pat.search(command):
                sys.stderr.write(
                    json.dumps(
                        {
                            "hook": "preflight-git-commit",
                            "decision": "deny",
                            "reason": ".env / credentials を直接 commit/add しようとしています",
                            "pattern": pat.pattern,
                        },
                        ensure_ascii=False,
                    )
                )
                return 2

        warnings = []
        for pat, msg in WARN_PATTERNS:
            if pat.search(command):
                warnings.append({"pattern": pat.pattern, "message": msg})
        if warnings:
            sys.stdout.write(
                json.dumps(
                    {
                        "hook": "preflight-git-commit",
                        "decision": "warn",
                        "warnings": warnings,
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        # silent: Claude を止めない
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
