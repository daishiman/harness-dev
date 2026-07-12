#!/usr/bin/env python3
# /// script
# name: slack_notify
# purpose: Slack Bot Token(Keychain)で chat.postMessage を送る。契約書下書き通知・PDF再共有に使う。
# inputs:
#   - config(slack_channel/slack_keychain_*) + メッセージ本文
# outputs:
#   - Slack投稿(返信ts) / 失敗時は例外を握り潰さず呼び出し側へ
# contexts: [C, E]
# network: true
# write-scope: slack
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: Slack通知送信(Bot Token + chat.postMessage)。

claude.ai Slack MCP ではなく Bot Token を使う理由: cron/無人実行でも認証が切れず動くため
(Drive の Service Account と同じ Keychain+Script パターンに統一)。標準ライブラリ(urllib)のみ。
"""

import json
import urllib.request

from slack_common import slack_token as _token

API = "https://slack.com/api/chat.postMessage"


def post(cfg, text, thread_ts=None, dry_run=False):
    """channel(cfg.slack_channel)へ text を投稿。thread_ts 指定でスレッド返信。

    returns 投稿メッセージの ts(承認ポーリングの突合キー)。dry_run 時は送信せず None。
    """
    if dry_run:
        print(f"[slack_notify DRY] {text[:80]}")
        return None
    channel = cfg.get("slack_channel")
    if not channel:
        raise ValueError("config に slack_channel がありません(README Task 10)")
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {_token(cfg)}",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        body = json.loads(res.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(f"Slack送信失敗: {body.get('error')}")
    return body.get("ts")


def build_draft_message(row, type_label, doc_url, ledger_url, no):
    """下書き通知の本文を組み立てる。

    この通知は「お知らせ」であり発火条件ではない。PDF確定の発火条件は
    Claude Code 上で finalize を実行すること(pull 型)。Slack のリアクション/返信は
    承認ゲートではないため、文言でも Slack を発火条件として案内しない。
    """
    name = row.get("乙氏名・名称") or row.get("乙法人名・名称") or "(乙名未設定)"
    return (
        f"📄 業務委託契約書(下書き・要確認)を作成しました [{type_label}]\n"
        f"• 案件No: {no}  乙: {name}\n"
        f"• Docs(黄色=AI記入箇所・要確認): {doc_url}\n"
        f"• 管理台帳: {ledger_url}\n"
        "内容をご確認ください(このメッセージはお知らせです)。\n"
        "問題なければ Claude Code で「確定して(PDF発行)」と指示すると、"
        "提出用PDF(黄色除去版)を生成しこのスレッドへ共有します。"
    )
