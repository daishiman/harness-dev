#!/usr/bin/env python3
# /// script
# name: slack_poll
# purpose: draft通知メッセージへの✅リアクション/「OK」返信をBot Tokenで読み、承認を検知する。
# inputs:
#   - config + メッセージts(台帳 Slack_メッセージTS)
# outputs:
#   - 承認有無 + 承認者
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: Slack承認検知(ポーリング)。

reactions.get(✅) と conversations.replies("OK"/"承認") を読み、承認の有無と承認者を返す。
これが webhook常駐の代替。/loop・cron から呼ばれる。標準ライブラリ(urllib)のみ。
"""

import json
import re
import urllib.parse
import urllib.request

from slack_common import slack_token as _token

APPROVE_REACTIONS = {"white_check_mark", "+1", "ok", "heavy_check_mark"}
APPROVE_TEXTS = frozenset({"ok", "approve", "承認", "承諾", "yes"})
REJECT_PATTERNS = re.compile(r"(じゃない|ではない|\bnot\b|\bno\b|却下|拒否)", re.IGNORECASE)


def _is_approved(text):
    """テキストが承認意図か判定。否定語先行検査 + 完全一致。"""
    if not text:
        return False
    t = text.strip().lower()
    if REJECT_PATTERNS.search(t):
        return False
    return t in APPROVE_TEXTS


def _get(url, params, token):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{q}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def check_approved(cfg, message_ts):
    """message_ts のメッセージが承認されたか。returns (approved:bool, approver:str|None)。"""
    channel = cfg.get("slack_channel")
    token = _token(cfg)

    # 1) ✅ リアクション
    r = _get("https://slack.com/api/reactions.get",
             {"channel": channel, "timestamp": message_ts}, token)
    if r.get("ok"):
        for rc in (r.get("message", {}) or {}).get("reactions", []) or []:
            if rc.get("name") in APPROVE_REACTIONS:
                users = rc.get("users") or []
                return True, (users[0] if users else "(reaction)")

    # 2) "OK"/"承認" 返信
    rep = _get("https://slack.com/api/conversations.replies",
               {"channel": channel, "ts": message_ts}, token)
    if rep.get("ok"):
        for m in rep.get("messages", [])[1:]:  # [0]は親メッセージ
            if _is_approved(m.get("text") or ""):
                return True, m.get("user", "(reply)")

    return False, None
