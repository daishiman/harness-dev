#!/usr/bin/env python3
# /// script
# name: mail_db_audit
# purpose: メール本文DB(DB1)/メール送信先_DB(DB2) のスキーマとデータ品質を監査し、送信前に直すべき問題(空本文/未知トークン/不正アドレス/重複/空差し込み値)を行単位で洗い出す。送信成功率を高めるための改善提案を生成する。
# inputs:
#   - client: NotionClient / db1_id / db2_id
# outputs:
#   - audit_body_db()/audit_recipient_db()/cross_audit(): issues 構造
# contexts: [C, E]
# network: true   # api.notion.com への HTTPS GET のみ
# write-scope: none   # 監査は read-only。改善は人が Notion 上で行う
# dependencies: []
# requires-python: ">=3.9"
# ///
"""メールソース2DB のデータ品質監査 (送信前のデータ改善)。

送信ログDB ではなくソース DB (本文/宛先) の品質を行単位で検査する。本 module は read-only で、
Notion への書込はしない (改善判断は人が行う領域。仕様書 §1 の宛先メンテは人手、機械は検出のみ)。
本文が使うトークンと宛先が持つ値のクロス検査で、送信時に skip される組を事前予告する。
"""
from __future__ import annotations

try:
    from . import notion_client as nc, render_substitute as rs, message_assemble as ma
except ImportError:
    import notion_client as nc, render_substitute as rs, message_assemble as ma  # type: ignore

# 差し込みトークンの既知集合 (宛先DB列に対応)
KNOWN_TOKENS = {"担当者様名", "会社名"}
# 廃止済みトークン (D1: 部署名は廃止。本文に残っていても unresolved_token で fail-closed されるが、
# typo の unknown_token とは区別して「削除推奨」を案内する)
DEPRECATED_TOKENS = {"部署名"}
# 廃止済み DB2 schema プロパティ (D1: 部署名列は削除する。本文トークンの DEPRECATED_TOKENS は
# 「本文に {{部署名}} が残っているか」を見るが、こちらは DB2 の**列そのもの**が残っているかを見る。
# 列が残っていても送信は止まらない=放置されやすいので schema 層で別途検出する。要件1(d) の機械検証。)
DEPRECATED_RECIPIENT_PROPERTIES = {"部署名"}


def audit_recipient_db_schema(client, db2_id: str) -> dict:
    """DB2 の **schema** を検査し、廃止済みプロパティの残存を洗い出す (要件1(d))。

    audit_recipient_db() が行データ(GET /databases/{id}/query)を見るのに対し、本関数は
    schema(GET /databases/{id})を見る。廃止列は送信を止めないため検知されず放置されやすい。

    Returns {properties, issues}
        issues item: {db, severity, code, detail, property}
    """
    db = client.retrieve_database(db2_id)
    prop_names = list((db.get("properties") or {}).keys())
    issues: list[dict] = []
    for name in sorted(set(prop_names) & DEPRECATED_RECIPIENT_PROPERTIES):
        issues.append({"db": "recipient_schema", "severity": "medium", "code": "deprecated_property",
                       "property": name,
                       "detail": f"廃止済みプロパティ『{name}』が DB2 schema に残存 (D1 で廃止)。"
                                 f"Notion 上で列を削除してください (送信は止まりませんが運用上の混乱を招きます)"})
    return {"properties": prop_names, "issues": issues}


def audit_body_db(client, db1_id: str) -> dict:
    """DB1 メール本文_DB を監査する。

    Returns {total_target, sendable, used_tokens, issues}
        issues item: {db, page_id, subject, severity, code, detail}
    """
    bodies, skipped = nc.fetch_bodies_true(client, db1_id)
    issues: list[dict] = []
    used_tokens: set[str] = set()

    for s in skipped:  # メッセージ対象✅ だが本文が使えない
        issues.append({"db": "body", "page_id": s["page_id"], "subject": s["subject"],
                       "severity": "high", "code": s["reason_code"],
                       "detail": "メッセージ対象=✅ だが本文が送信に使えない (本文記入が必要)"})

    for b in bodies:
        tokens = set(rs.find_unresolved_tokens(b["subject"]) + rs.find_unresolved_tokens(b["body"]))
        used_tokens |= tokens
        deprecated = tokens & DEPRECATED_TOKENS
        if deprecated:
            issues.append({"db": "body", "page_id": b["page_id"], "subject": b["subject"],
                           "severity": "medium", "code": "deprecated_token",
                           "detail": f"廃止トークン {sorted(deprecated)} (部署名は廃止。本文から削除してください。"
                                     f"残すと送信時 unresolved で skip されます)"})
        unknown = tokens - KNOWN_TOKENS - DEPRECATED_TOKENS
        if unknown:
            issues.append({"db": "body", "page_id": b["page_id"], "subject": b["subject"],
                           "severity": "high", "code": "unknown_token",
                           "detail": f"既知トークン{sorted(KNOWN_TOKENS)}外: {sorted(unknown)} (typo の可能性。送信時 unresolved で skip)"})
        if not b["from_addr"] or not ma.validate_email(b["from_addr"]):
            issues.append({"db": "body", "page_id": b["page_id"], "subject": b["subject"],
                           "severity": "high", "code": "invalid_from",
                           "detail": f"送り主(From)が空/不正: '{b['from_addr']}'"})
        for cc in ma.parse_comma_addrs(b["cc_raw"]):
            if not ma.validate_email(cc):
                issues.append({"db": "body", "page_id": b["page_id"], "subject": b["subject"],
                               "severity": "medium", "code": "invalid_cc", "detail": f"CC 不正: {cc}"})

    return {"total_target": len(bodies) + len(skipped), "sendable": len(bodies),
            "used_tokens": sorted(used_tokens), "issues": issues}


def audit_recipient_db(client, db2_id: str) -> dict:
    """DB2 メール送信先_DB を監査する。

    Returns {total_target, sendable, recipients, suppressed, duplicate_dropped, issues}
    """
    res = nc.fetch_recipients_true(client, db2_id)
    recips = res["recipients"]
    skipped = res["skipped"]
    suppressed = res["suppressed"]
    duplicate_dropped = res["duplicate_dropped"]
    issues: list[dict] = []

    for s in skipped:  # 送信対象✅ だがプロ人材メール空/不備
        issues.append({"db": "recipient", "page_id": s["page_id"], "name": s["name"],
                       "severity": "high", "code": s["reason_code"],
                       "detail": "送信対象=✅ だがプロ人材メールが空/不備"})

    for r in recips:
        if not ma.validate_email(r["pro_email"]):
            issues.append({"db": "recipient", "page_id": r["page_id"], "name": r["name"],
                           "severity": "high", "code": "invalid_to",
                           "detail": f"プロ人材(To)アドレス不正: {r['pro_email']}"})
        for addr in ma.parse_comma_addrs(r.get("hisho_email", "")):
            if not ma.validate_email(addr):
                issues.append({"db": "recipient", "page_id": r["page_id"], "name": r["name"],
                               "severity": "medium", "code": "invalid_cc",
                               "detail": f"秘書(CC)アドレス不正: {addr} (この単位は送信時 invalid_cc で skip)"})

    for d in duplicate_dropped:  # 同一プロ人材は最新 created_time 1件のみ送信 (同時刻は page_id 降順)
        issues.append({"db": "recipient", "page_id": d["page_id"], "name": d["name"],
                       "severity": "low", "code": "duplicate_recipient",
                       "detail": f"プロ人材 {d['pro_email']} 重複 (会社={d['company']}) → 最新の page "
                                 f"{d['kept_page_id'][-6:]} のみ送信・本行は除外"})

    return {"total_target": len(recips) + len(skipped) + len(suppressed) + len(duplicate_dropped),
            "sendable": len(recips), "recipients": recips,
            "suppressed": suppressed, "duplicate_dropped": duplicate_dropped, "issues": issues}


def run_full_audit(client, db1_id: str, db2_id: str) -> dict:
    """本文DB/宛先DB/schema/cross の全監査を集約し、issues と high severity を返す (集約 SSOT)。

    `run-notion-gmail-source-audit`(CLI) と確認0 auto-send の事前ゲートが**同一の判定**を使うための
    単一関数。high severity issue が1件でもあれば auto-send は送信前に fail-closed する根拠になる。

    Returns {all_issues, high, body_rep, recip_rep, recip_schema, cross}
    """
    body_rep = audit_body_db(client, db1_id)
    recip_rep = audit_recipient_db(client, db2_id)
    recip_schema = audit_recipient_db_schema(client, db2_id)
    cross = cross_audit(body_rep["used_tokens"], recip_rep["recipients"])
    all_issues = body_rep["issues"] + recip_rep["issues"] + recip_schema["issues"] + cross
    high = [i for i in all_issues if i.get("severity") == "high"]
    return {"all_issues": all_issues, "high": high, "body_rep": body_rep,
            "recip_rep": recip_rep, "recip_schema": recip_schema, "cross": cross}


def cross_audit(used_tokens: list[str], recipients: list[dict]) -> list[dict]:
    """本文が使うトークンに対し、宛先の対応値が空な組を未置換リスクとして洗い出す。"""
    issues: list[dict] = []
    relevant = [t for t in used_tokens if t in KNOWN_TOKENS]
    for r in recipients:
        vals = nc.values_for_recipient(r)
        empty = [t for t in relevant if not (vals.get(t) or "").strip()]
        if empty:
            issues.append({"db": "cross", "page_id": r["page_id"], "name": r["name"],
                           "severity": "high", "code": "empty_substitution",
                           "detail": f"本文が使う {empty} の値が空 → この宛先への全本文が送信時 unresolved_token で skip"})
    return issues
