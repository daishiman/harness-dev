#!/usr/bin/env python3
# /// script
# name: hook-guard-secret
# purpose: company-master の Notion token / gBizINFO APIトークン / 日本郵便DA API機密の平文流出・削除を PreToolUse でブロックする二段防御の動的層。
# inputs:
#   - stdin: PreToolUse hook JSON ({tool_name, tool_input.command})
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderrに理由)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""PreToolUse(Bash) 動的ガード。

SKILL.md セキュリティ節の二段防御のうち「文脈依存の危険検査」を担う実体。
静的層は settings.json の permissions.deny。

ガード対象 (GUARD_ACCOUNTS: Notion / gBizINFO / 日本郵便DA API の Keychain
account/service 文字列) を含む Bash コマンドに対し以下をブロックする:
  - `-w` / `--print-unsafe`   : トークンの平文標準出力(流出)
  - `-g`                      : Keychain 属性と秘密値を stderr へ表示し得る操作
  - `delete-generic-password` : 鍵の誤削除
`add-generic-password`(登録)はセットアップ用途のため許容する。

該当しないコマンドは no-op(exit 0)。ガード対象文字列を含まない一般コマンドは一切干渉しない。
hook JSON を解釈できない入力は fail-closed (exit 2) で遮断する (保証要件は機械層で担保:
fail-open は hook-guard-skillgen 堅牢化 2026-06-06 で封鎖済みの旧世代パターン)。
"""
import json
import re
import sys

GUARD_SERVICE_PREFIXES = (
    "notion-api-key.",
    "gbizinfo-api-token.",
    "japanpost-da-api.",
)
BLOCK_PATTERNS = ["--print-unsafe", "delete-generic-password"]
# `-w` / `-g` はトークン平文出力につながる。account/service 文字列と同時出現時のみブロック。
# 正規表現ベース: 連結フラグ(-wa)・クォート(' "-w"')・変数接尾(-w$X) でもすり抜けないよう、
# 「区切り(行頭/空白/引用符/シェルメタ)直後の短フラグ群に w または g を含む」を検出する。
# `find-generic-password` 等の単語中ハイフン (-generic) は前が単語文字のため誤検出しない。
SECRET_OUTPUT_FLAG_RE = re.compile(r"""(?:^|[\s;|&'"=(`])-[A-Za-z]*[wg]""")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # fail-closed: 解釈不能な入力は遮断する (素通しは検査バイパス経路になる)。
        sys.stderr.write(
            "[hook-guard-secret] BLOCKED: stdin の hook JSON を解釈できないため "
            "fail-closed で遮断します(検査不能入力の素通しはバイパス経路になるため)。\n"
        )
        return 2
    cmd = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not any(prefix in cmd for prefix in GUARD_SERVICE_PREFIXES):
        return 0
    for pat in BLOCK_PATTERNS:
        if pat in cmd:
            sys.stderr.write(
                f"[hook-guard-secret] BLOCKED: '{pat}' は company-master の機密"
                "(Notion token / gBizINFO トークン / 日本郵便DA API機密)に対して禁止です(平文流出/誤削除防止)。"
                "鍵は Keychain のみで扱い、生値を端末に出さないでください。\n"
            )
            return 2
    if "find-generic-password" in cmd and SECRET_OUTPUT_FLAG_RE.search(cmd):
        sys.stderr.write(
            "[hook-guard-secret] BLOCKED: ガード対象アカウントの平文出力(find-generic-password -w/-g、"
            "連結フラグ含む)は禁止です。トークンは notion_config.get_token 経由でメモリ上のみ取得してください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
