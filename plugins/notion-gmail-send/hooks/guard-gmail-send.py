#!/usr/bin/env python3
# /// script
# name: guard-gmail-send
# purpose: PreToolUse 補助防御。承認フローを迂回した Gmail 直接送信(Bash経路の curl/python -c 等)を遮断する。正本防御は lib/send_guard.py (gmail_client 内蔵)。
# inputs:
#   - stdin: PreToolUse payload (tool_name / tool_input)
# outputs:
#   - exit: 0=許可 / 2=拒否(承認迂回の Gmail 送信)
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""PreToolUse hook: 承認フローを迂回した Gmail 直接送信を Bash 経路で遮断する (補助防御の第1層)。

射程: Bash tool の command 文字列、および他 tool の tool_input JSON に gmail.googleapis.com と
messages/send パターンが現れ、かつ正規の送信スクリプト (send-campaign.py) 経由でない場合に exit 2
で拒否する。curl / python -c 等で承認 plan_hash を通さず直接送る操作を止める。

注意 (保証範囲の正直な明示・仕様書 §10): 本 hook は『Bash 経由の素の HTTP コマンド』を捕捉する
補助層であり、決定論スクリプト内部の urllib 呼び出しまでは射程外。そのため**安全の正本は
lib/gmail_client.py が内部で必ず呼ぶ lib/send_guard.py** とし (approved_plan_hash/件数/先頭To/
reservedログ行/未置換トークン/From検証が揃わない限り送信関数へ到達させない)、2層で誤送信を防ぐ。
Notion (api.notion.com) への書き込みは対象外。
"""
import json
import re
import sys

_HOST = "gmail.googleapis.com"
# 正規の送信経路。これを含む Bash コマンドは承認フロー (send_guard 内蔵) を通るため許可する。
_SANCTIONED = "send-campaign.py"
_SEND_PATTERNS = [
    r"messages/send",
    r"users/[^/\s]+/messages/send",
    r"\.send\s*\(",
    r'"send"',
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    text = ti.get("command", "") if tool == "Bash" else json.dumps(ti, ensure_ascii=False)
    if _HOST not in text:
        return 0
    if _SANCTIONED in text:
        return 0  # 正規スクリプト経由 (send_guard が守る)
    lowered = text.lower()
    if any(re.search(p, lowered) for p in _SEND_PATTERNS):
        sys.stderr.write(
            "[guard-gmail-send] 承認フローを迂回した Gmail 直接送信は禁止です。"
            "確認0で送る場合は run-notion-gmail-send、慎重運用では "
            "run-notion-gmail-dry-run で plan を作って APPROVE 後に "
            "run-notion-gmail-send (send-campaign.py / send_guard 内蔵) 経由で行ってください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
