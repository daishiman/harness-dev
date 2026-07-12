#!/usr/bin/env python3
# /// script
# name: idempotent_log
# purpose: Notion 送信ログDBへ冪等キーで reserved→sending→sent/unknown_needs_reconcile を更新し、既送照合・部分再開の起点化・二重送信防止を行う。送信成功後ログ失敗はローカル journal に退避する。
# inputs:
#   - client: NotionClient / log_db_id: str / 冪等キー・各フィールド
# outputs:
#   - reserve()/mark_sending()/mark_sent()/mark_unknown()/mark_skipped()/mark_error()/append_journal()
# contexts: [C, E]
# network: true   # 送信ログDB への Notion API のみ
# write-scope: notion-pages
# dependencies: []
# requires-python: ">=3.9"
# ///
"""事前予約つき冪等ログ (仕様書 §9/§11)。

Notion API は一意制約を提供しないため、送信前に検索 → 0件 create reserved / 1件 状態判定 /
2件以上 fail-closed (duplicate_log_key)。sent と unknown_needs_reconcile は自動再送しない。
本文全文は保存せず content_hash と件名を保存する (PII 方針 §12)。
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

P_KEY = "冪等キー"

# status enum (副作用段階) — 仕様書 §9
PLANNED = "planned"
RESERVED = "reserved"
SENDING = "sending"
SENT = "sent"
SKIPPED_IDEMPOTENT = "skipped_idempotent"
SKIPPED_VALIDATION = "skipped_validation"
ERROR = "error"
UNKNOWN = "unknown_needs_reconcile"

REASON_CODES = [
    "empty_body",
    "multiple_body_code_blocks",
    "body_fetch_failed",
    "invalid_to",
    "invalid_cc",
    "unresolved_token",
    "unsafe_header",
    "duplicate_recipient",
    "from_alias_unverified",
    "quota_stopped",
    "send_success_log_failed",
    "duplicate_log_key",
    "needs_reconcile",
    "sending_interrupted",
    "content_hash_mismatch",
    "invalid_addr_at_send",
    "send_suppressed",
    "send_failed",
    "no_approval",
    "plan_hash_mismatch",
    "count_mismatch",
    "first_to_mismatch",
    "nonce_mismatch",
    "no_reserved_log",
]

# reserve 時に「自動再送しない」既存状態
_NO_RESEND = {SENT, RESERVED, SENDING, UNKNOWN, SKIPPED_IDEMPOTENT}
# 再予約してよい既存状態 (未送信と判断できる)
_RESERVABLE = {PLANNED, ERROR, SKIPPED_VALIDATION}


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat()


def _title(v: str) -> dict:
    return {"title": [{"text": {"content": (v or "")[:2000]}}]}


def _rt(v: str) -> dict:
    return {"rich_text": [{"text": {"content": (v or "")[:2000]}}]}


def _select(v: str) -> dict:
    return {"select": {"name": v}}


def _date(iso: str) -> dict:
    return {"date": {"start": iso}}


def _base_props(fields: dict, status: str) -> dict:
    """送信ログDB の1行プロパティを組み立てる (本文全文は保存しない)。"""
    props = {
        P_KEY: _title(fields["idempotency_key"]),
        "campaign_id": _rt(fields.get("campaign_id", "")),
        "plan_hash": _rt(fields.get("plan_hash", "")),
        "content_hash": _rt(fields.get("content_hash", "")),
        "status": _select(status),
        "本文page_id": _rt(fields.get("body_page_id", "")),
        "宛先page_id": _rt(fields.get("recipient_page_id", "")),
        "From": _rt(fields.get("from_addr", "")),
        "To": _rt(json.dumps(fields.get("to_list", []), ensure_ascii=False)),
        "CC": _rt(json.dumps(fields.get("cc_list", []), ensure_ascii=False)),
        "件名": _rt(fields.get("subject", "")),
    }
    if fields.get("reason_code"):
        props["reason_code"] = _select(fields["reason_code"])
    return props


def _select_name(row: dict, prop: str) -> str | None:
    return (((row.get("properties", {}).get(prop) or {}).get("select") or {}).get("name"))


def reserve(client, log_db_id: str, fields: dict) -> dict:
    """送信前に冪等キーで検索し、状態を確定する。

    Returns dict:
        action: "reserved" | "skip" | "skip_manual" | "duplicate"
        status: 確定 status
        page_id: ログ行 ID (reserved/skip 時)
        reason_code: skip 理由 (該当時)
    """
    key = fields["idempotency_key"]
    rows = client.query_all(log_db_id, filter_={"property": P_KEY, "title": {"equals": key}})

    if len(rows) >= 2:
        return {"action": "duplicate", "status": ERROR, "reason_code": "duplicate_log_key",
                "page_id": None, "matched": len(rows)}

    if len(rows) == 1:
        row = rows[0]
        cur = _select_name(row, "status")
        reason = _select_name(row, "reason_code")
        pid = row.get("id")
        if cur == SENT:
            return {"action": "skip", "status": SKIPPED_IDEMPOTENT, "page_id": pid}
        if cur == SENDING:
            # 前回 mark_sending と mark_sent の間で中断 → 送信成否不明。unknown へ遷移させ要照合報告。
            # (SENDING のまま放置すると skipped_existing に埋もれ過少報告になる: §9 unknown 定義)
            client.update_page(pid, {"status": _select(UNKNOWN),
                                     "reason_code": _select("sending_interrupted"),
                                     "error": _rt("前回 sending 中に中断・送信成否不明")})
            return {"action": "skip_manual", "status": UNKNOWN, "page_id": pid,
                    "reason_code": "needs_reconcile"}
        if cur == RESERVED and reason == "quota_stopped":
            client.update_page(pid, {"status": _select(RESERVED), "reserved_at": _date(_now_iso())})
            return {"action": "reserved", "status": RESERVED, "page_id": pid,
                    "reason_code": "quota_stopped"}
        if cur in _NO_RESEND:
            return {"action": "skip_manual", "status": cur, "page_id": pid,
                    "reason_code": "needs_reconcile" if cur == UNKNOWN else cur}
        if cur in _RESERVABLE:
            client.update_page(pid, {"status": _select(RESERVED), "reserved_at": _date(_now_iso())})
            return {"action": "reserved", "status": RESERVED, "page_id": pid}
        # 未知 status: 安全側で手動扱い
        return {"action": "skip_manual", "status": cur or "unknown", "page_id": pid}

    # 0件: 新規 reserved 作成
    props = _base_props(fields, RESERVED)
    props["reserved_at"] = _date(_now_iso())
    page = client.create_page(log_db_id, props)
    # Notion には一意制約がないため、並行実行で同一キーが同時作成され得る。
    # create 後に再検索し、重複が見えた場合は Gmail 到達前に fail-closed する。
    rows_after = client.query_all(log_db_id, filter_={"property": P_KEY, "title": {"equals": key}})
    if len(rows_after) >= 2:
        return {"action": "duplicate", "status": ERROR, "reason_code": "duplicate_log_key",
                "page_id": None, "matched": len(rows_after)}
    return {"action": "reserved", "status": RESERVED, "page_id": page.get("id")}


def mark_sending(client, page_id: str) -> None:
    client.update_page(page_id, {"status": _select(SENDING), "sending_at": _date(_now_iso())})


def mark_reserved(client, page_id: str, reason_code: str | None = None) -> None:
    """送信に到達せず未送信が確定した単位 (quota 安全停止など) を reserved へ戻す。

    quota 拒否はサーバが受理前に弾く=未送信確定なので、次回 reserved として自動再開できる
    (SENDING のまま残すと _NO_RESEND で手動扱いになり再開不能になる: §11 矛盾の解消)。
    """
    props = {"status": _select(RESERVED), "reserved_at": _date(_now_iso())}
    if reason_code:
        props["reason_code"] = _select(reason_code)
    client.update_page(page_id, props)


def mark_sent(client, page_id: str, message_id: str) -> None:
    client.update_page(page_id, {
        "status": _select(SENT),
        "messageId": _rt(message_id),
        "sent_at": _date(_now_iso()),
    })


def mark_unknown(client, page_id: str, error_summary: str = "") -> None:
    client.update_page(page_id, {
        "status": _select(UNKNOWN),
        "reason_code": _select("send_success_log_failed"),
        "error": _rt(error_summary),
    })


def mark_error(client, page_id: str, reason_code: str, error_summary: str = "") -> None:
    client.update_page(page_id, {
        "status": _select(ERROR),
        "reason_code": _select(reason_code),
        "error": _rt(error_summary),
    })


def mark_skipped(client, log_db_id: str, fields: dict, reason_code: str) -> dict:
    """skipped_validation 行を記録する (送信前除外)。既存があれば作らない。"""
    key = fields["idempotency_key"]
    rows = client.query_all(log_db_id, filter_={"property": P_KEY, "title": {"equals": key}})
    if rows:
        return {"action": "exists", "page_id": rows[0].get("id")}
    fields = {**fields, "reason_code": reason_code}
    props = _base_props(fields, SKIPPED_VALIDATION)
    page = client.create_page(log_db_id, props)
    return {"action": "created", "page_id": page.get("id")}


def journal_path(campaign_id: str) -> Path:
    base = os.environ.get("NOTION_GMAIL_OUTPUT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    d = Path(base) / "eval-log" / "notion-gmail-send"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"journal-{campaign_id}.jsonl"


def append_journal(campaign_id: str, record: dict) -> Path:
    """送信成功後ログ失敗などをローカル journal に追記する (秘密値は含めない)。"""
    record = {**record, "ts": _now_iso()}
    path = journal_path(campaign_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
