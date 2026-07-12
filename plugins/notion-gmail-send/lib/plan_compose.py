#!/usr/bin/env python3
# /// script
# name: plan_compose
# purpose: Notion 2DB から「本文true × 宛先(解決後)」の直積を生成し {{}}置換・MIME組立・content_hash/plan_hash まで行って送信 plan を確定する純粋ロジック。dry-run(build-plan.py) と確認0 auto-send(send-campaign.py) が**同一の新鮮 plan** を生成するための単一 SSOT。Gmail API は呼ばない。
# inputs:
#   - bodies/body_skipped: fetch_bodies_true() の結果 / resolution: fetch_recipients_true() の RecipientResolution
#   - client+db1+db2 (compose_plan の場合は notion REST 取得を内包)
# outputs:
#   - assemble_plan()/compose_plan(): 確定 plan dict (units/skipped/suppressed/duplicate_dropped/各カウント/source)
# contexts: [C, E]
# network: true   # compose_plan のみ api.notion.com GET。assemble_plan は network:false の純関数
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""送信 plan の構築 (仕様書 §4/§5/§6/§8 step1-4)。

build-plan.py(dry-run) と send-campaign.py(確認0 auto-send) の双方がこの単一ロジックを呼ぶ
ことで、auto-send が「送信直前に Notion の最新状態から plan を再生成する」ことを保証する。
古い plan.json を使い回すと、承認後に宛先アドレスを編集した場合 plan 内は content_hash 一致のまま
旧アドレスへ送る鮮度漏れが生じるため、auto-send は必ず本ロジックで新鮮 plan を作る。
"""
from __future__ import annotations

import datetime

try:
    from . import notion_client, render_substitute as rs, message_assemble as ma, plan_build as pb
except ImportError:  # スクリプトが lib を sys.path に載せた場合
    import notion_client, render_substitute as rs, message_assemble as ma, plan_build as pb  # type: ignore


def _combine_cc(body_cc_raw: str, hisho_email: str) -> str:
    """本文CC + 秘書CC を結合した cc_raw 文字列にする (重複/To除外は assemble が正規化)。

    結合はここ1回だけ確定し plan.json の cc_list に焼く。live-send は再結合しない
    (content_hash の決定論を二重ロジックで壊さないため。仕様書 §6)。
    """
    return ",".join(p for p in (body_cc_raw or "", hisho_email or "") if p.strip())


def _classify_unit(body: dict, recip: dict) -> tuple[dict | None, str | None]:
    """1組(本文×宛先)を送信単位に変換する。skip 時は (None, reason_code)。

    To=プロ人材メール、CC=本文CC + 秘書(cc秘書)メール (仕様書 §6)。
    """
    values = notion_client.values_for_recipient(recip)
    if rs.unsafe_value_keys(values):
        return None, "unsafe_header"
    subject_out, un_s = rs.substitute(body["subject"], values)
    body_out, un_b = rs.substitute(body["body"], values)
    unresolved = list(dict.fromkeys(un_s + un_b))
    if unresolved:
        return None, "unresolved_token"
    cc_raw = _combine_cc(body["cc_raw"], recip.get("hisho_email", ""))
    asm = ma.assemble(subject_out, body_out, body["from_addr"], recip["pro_email"], cc_raw)
    if asm["invalid_addrs"]:
        reason = "invalid_cc" if all(a.startswith("cc:") for a in asm["invalid_addrs"]) else "invalid_to"
        return None, reason
    # To と重複して CC から除外されたアドレス (秘書addr==プロ人材To 等) を可視化する。
    cc_suppressed = ma.cc_suppressed_by_to(ma.parse_comma_addrs(cc_raw), asm["to_list"])
    unit = {
        "subject": subject_out,
        "body": body_out,
        "from_addr": body["from_addr"],
        "to_list": asm["to_list"],
        "cc_list": asm["cc_list"],
        "raw": asm["raw"],
        "multi_to_visible": asm["multi_to_visible"],
        "cc_suppressed_due_to_to_overlap": cc_suppressed,
        "body_page_id": body["page_id"],
        "recipient_page_id": recip["page_id"],
    }
    unit["content_hash"] = pb.content_hash(unit)
    return unit, None


def _stable_units(units: list[dict]) -> list[dict]:
    return sorted(units, key=lambda u: (u["content_hash"], u.get("body_page_id", ""), u.get("recipient_page_id", "")))


def assemble_plan(bodies: list[dict], body_skipped: list[dict], resolution: dict, *,
                  db1: str, db2: str, canary: int | None = None,
                  campaign_id: str | None = None, generated_at: str | None = None) -> dict:
    """取得済みの本文true/宛先解決から確定 plan を組み立てる純関数 (network 不要・単体テスト容易)。

    canary 指定時は送信可能 unit を安定順の先頭 N 件へ限定する。`available_unit_count` は
    限定前の全送信可能数を保持し、canary 適用後でも母数を見失わない。
    """
    recips = resolution["recipients"]            # 送信可能・dedup後
    recip_skipped = resolution["skipped"]        # プロ人材メール空
    suppressed = resolution["suppressed"]        # メールを送らない=✅ (送信対象より優先)
    duplicate_dropped = resolution["duplicate_dropped"]  # プロ人材重複で除外された古い行

    first_stage = len(bodies) * len(recips)
    campaign_id = campaign_id or pb.generate_campaign_id()
    units: list[dict] = []
    skipped: list[dict] = []
    for body in bodies:
        for recip in recips:
            unit, reason = _classify_unit(body, recip)
            if reason:
                skipped.append({"body_page_id": body["page_id"], "recipient_page_id": recip["page_id"],
                                "subject": body["subject"], "to": recip["pro_email"], "reason_code": reason})
                continue
            # dedup キーは content ベース (campaign_id 非依存) で別実行の二重送信も機構で防ぐ。
            unit["idempotency_key"] = pb.dedup_key(unit["body_page_id"], unit["recipient_page_id"], unit["content_hash"])
            units.append(unit)

    available_units = len(units)
    if canary is not None and canary < available_units:
        units = _stable_units(units)[:canary]
    plan = pb.finalize_plan(campaign_id, units)
    plan.update({
        "generated_at": generated_at or datetime.datetime.now().astimezone().isoformat(),
        "first_stage_count": first_stage,
        "body_true_count": len(bodies),       # 本文 true(メッセージ対象✅かつ非空) 行数。G2.body の正しい母数
        "recipient_true_count": len(recips),  # 宛先(送信対象✅かつ送らない☐かつプロ人材非空・dedup後) 行数
        "available_unit_count": available_units,
        "canary_limit": canary,
        "canary_applied": canary is not None and canary < available_units,
        "source": {"body_db": db1, "recipient_db": db2},
        "skipped": skipped,
        "suppressed": suppressed,                # メールを送らない=✅ で抑制した宛先
        "duplicate_dropped": duplicate_dropped,  # プロ人材重複で除外した古い行
        "body_skipped": body_skipped,
        "recipient_skipped": recip_skipped,
    })
    return plan


def compose_plan(client, db1: str, db2: str, *, canary: int | None = None) -> dict:
    """Notion 2DB を REST 取得して確定 plan を組み立てる (fresh rebuild 用の一本道)。

    send-campaign.py の確認0 auto-send が「送信直前の最新 Notion 状態」から plan を作るために
    使う。dry-run と同一ロジック (assemble_plan) を通すので、両者の plan は決定論的に一致する。
    """
    bodies, body_skipped = notion_client.fetch_bodies_true(client, db1)
    resolution = notion_client.fetch_recipients_true(client, db2)
    return assemble_plan(bodies, body_skipped, resolution, db1=db1, db2=db2, canary=canary)
