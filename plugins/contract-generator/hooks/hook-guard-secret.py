#!/usr/bin/env python3
# /// script
# name: hook-guard-secret
# purpose: contract-generate の Service Account 鍵の平文流出・削除を PreToolUse でブロックする二段防御の動的層。
# inputs:
#   - stdin: PreToolUse hook JSON ({tool_name, tool_input.command})
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderrに理由)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""PreToolUse(Bash) 動的ガード。

SKILL.md セキュリティ節の二段防御のうち「文脈依存の危険検査」を担う実体。
静的層は references/settings-hardening.json の permissions.deny。

ブロック対象(本スキルの Keychain account を含む Bash コマンド):
  - `--print-unsafe`         : SA 鍵 JSON の平文標準出力(流出)
  - `delete-generic-password`: SA 鍵の誤削除

該当しないコマンドは no-op(exit 0)。Keychain account 文字列を含まない一般コマンドは一切干渉しない。
"""
import json
import sys

GUARD_ACCOUNTS = [
    "contract-generate/service-account-json",  # Google Drive/Sheets SA鍵
    "contract-generate/bot-token",             # Slack Bot Token
]
BLOCK_PATTERNS = ["--print-unsafe", "delete-generic-password"]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 解釈不能な入力は素通し(可用性優先・graceful degradation)
    cmd = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not any(acct in cmd for acct in GUARD_ACCOUNTS):
        return 0
    for pat in BLOCK_PATTERNS:
        if pat in cmd:
            sys.stderr.write(
                f"[hook-guard-secret] BLOCKED: '{pat}' は contract-generate の機密"
                "(SA鍵/Slackトークン)に対して禁止です(平文流出/誤削除防止)。"
                "鍵は Keychain のみで扱い、生値を端末に出さないでください。\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
