#!/usr/bin/env python3
# /// script
# name: plan_build
# purpose: 送信単位を正規化し campaign_id/content_hash/plan_hash と冪等キーを生成、dry-run plan を確定する。live-send は plan_hash 一致でのみ送信可能 (send_guard と連携)。
# inputs:
#   - units: list[dict] (置換組立済みの送信単位)
# outputs:
#   - generate_campaign_id() / content_hash() / plan_hash() / dedup_key() / approval_nonce() / finalize_plan()
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""plan 構築と content/plan hash (仕様書 §4)。

content_hash = 置換後 Subject/Body/From/To/CC/本文page_id/宛先page_id を正規化した SHA-256。
plan_hash = 全送信単位 (順序安定・正規化済み) の SHA-256。live-send は --approved-plan-hash が
本 plan_hash と一致しない限り Gmail API を呼ばない (send_guard が強制)。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid


def generate_campaign_id(now: datetime.datetime | None = None) -> str:
    """実行ごとの識別子 YYYYMMDD-HHMMSS-<shortuuid>。"""
    now = now or datetime.datetime.now()
    return f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"


def _normalize(unit: dict) -> dict:
    """content_hash 対象フィールドを順序固定で正規化する。To/CC は順序非依存にする。"""
    return {
        "subject": unit.get("subject", ""),
        "body": unit.get("body", ""),
        "from": unit.get("from_addr", ""),
        "to": sorted(unit.get("to_list", [])),
        "cc": sorted(unit.get("cc_list", [])),
        "body_page_id": unit.get("body_page_id", ""),
        "recipient_page_id": unit.get("recipient_page_id", ""),
    }


def content_hash(unit: dict) -> str:
    """1送信単位の content_hash (sha256:hex)。"""
    payload = json.dumps(_normalize(unit), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dedup_key(body_page_id: str, recipient_page_id: str, ch: str,
              *, resend_campaign_id: str | None = None) -> str:
    """冪等(重複判定)キー {本文page_id}:{宛先page_id}:{content_hash}。

    campaign_id を**含めない**ことで、別実行(別 campaign)でも同一本文×同一宛先×同一内容を
    再送しようとすれば同じキーになり、送信ログDB の既 sent 行にヒットして二重送信を機構で防ぐ。
    意図的再送のみ `resend_campaign_id` を付与して別キー化する (--allow-resend)。
    """
    base = f"{body_page_id}:{recipient_page_id}:{ch}"
    return f"{base}:{resend_campaign_id}" if resend_campaign_id else base


def approval_nonce(ph: str, units: list[dict]) -> tuple[int | None, str]:
    """承認時に「読まないと得られない」確認語を返す (index, code)。

    plan_hash から決定論的に1単位を選び、その単位の content_hash にバインドした短コードを返す。
    dry-run はこの code を該当単位のプレビュー行にのみ表示し (APPROVE 行には載せない)、承認者は
    その単位を目視で探して入力する必要がある。send_guard が再計算して照合する (blind approve のコスト上げ)。
    """
    if not units:
        return (None, "")
    hexpart = ph.split(":")[-1]
    idx = int(hexpart[:8], 16) % len(units)
    code = hashlib.sha256(f"{ph}:{units[idx].get('content_hash', '')}".encode("utf-8")).hexdigest()[:6]
    return (idx, code)


def plan_hash(units: list[dict]) -> str:
    """全送信単位の plan_hash (sha256:hex)。

    順序安定化のため (content_hash, 本文page_id, 宛先page_id) でソートしてから連結する。
    各 unit は content_hash キーを持つこと。
    """
    keys = sorted(
        f"{u['content_hash']}|{u.get('body_page_id', '')}|{u.get('recipient_page_id', '')}"
        for u in units
    )
    payload = "\n".join(keys)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def finalize_plan(campaign_id: str, units: list[dict]) -> dict:
    """送信予定 units から確定 plan を構築する。

    各 unit は content_hash と idempotency_key を付与済みであること。
    Returns plan dict: campaign_id / plan_hash / count / first_to / units。
    first_to は順序安定化後の先頭 unit の To 先頭アドレス (承認 echo 対象)。
    """
    ordered = sorted(units, key=lambda u: (u["content_hash"], u.get("body_page_id", ""), u.get("recipient_page_id", "")))
    ph = plan_hash(units)
    first_to = ""
    if ordered and ordered[0].get("to_list"):
        first_to = ordered[0]["to_list"][0]
    return {
        "campaign_id": campaign_id,
        "plan_hash": ph,
        "count": len(ordered),
        "first_to": first_to,
        "units": ordered,
    }
