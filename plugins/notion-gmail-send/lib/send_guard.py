#!/usr/bin/env python3
# /// script
# name: send_guard
# purpose: Gmail API 呼び出しの正本防御。approved_plan_hash/plan_hash/承認件数/先頭To/reservedログ行ID/未置換トークン/From-sendAs 検証が全て一致しない限り送信関数へ到達させない (仕様書 §10)。
# inputs:
#   - SendGuardInput 相当のキーワード引数
# outputs:
#   - check(): None (全条件一致) / SendGuardError raise (不一致)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""送信ガード (仕様書 §10 — 安全の正本)。

PreToolUse hook は補助防御であり、決定論 script 内の Gmail API 呼び出しは hook で捕捉
できない可能性があるため、本 guard を必須防御とする。gmail_client は送信前に必ず check() を
通すので、orchestrator が呼び忘れても送信に到達しない構造になっている。
"""
from __future__ import annotations


class SendGuardError(Exception):
    """送信ガード違反。code は機械可読な reason、message は人間向け要約 (秘密値を含めない)。"""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"[{code}] {message}")


def check(
    *,
    approved_plan_hash: str,
    plan_hash: str,
    approved_count: int,
    actual_count: int,
    approved_first_to: str,
    actual_first_to: str,
    reserved_log_id: str | None,
    unresolved_tokens: list,
    from_verified: bool,
    approved_nonce: str = "",
    actual_nonce: str = "",
) -> None:
    """送信前ゲート。1つでも不一致なら SendGuardError を raise し Gmail API へ到達させない。

    呼び出し側 (gmail_client) はこの関数を例外なく通過した場合のみ送信する。
    `actual_nonce` (plan から決定論計算した承認確認語) が非空のとき、人間が入力した
    `approved_nonce` と一致しない限り送信させない (S-F1: blind approve 防止の読解強制)。
    """
    if not approved_plan_hash:
        raise SendGuardError("no_approval", "承認 plan_hash が空。承認ゲート未通過。")
    if approved_plan_hash != plan_hash:
        raise SendGuardError("plan_hash_mismatch", "承認 plan_hash と現在の plan_hash が不一致。")
    if int(approved_count) != int(actual_count):
        raise SendGuardError("count_mismatch", f"承認件数({approved_count})と送信件数({actual_count})が不一致。")
    if (approved_first_to or "") != (actual_first_to or ""):
        raise SendGuardError("first_to_mismatch", "承認先頭 To と送信先頭 To が不一致。")
    if actual_nonce and approved_nonce != actual_nonce:
        raise SendGuardError("nonce_mismatch",
                             "承認確認語が不一致。プレビューの該当単位を確認し正しい確認語を入力してください。")
    if not reserved_log_id:
        raise SendGuardError("no_reserved_log", "reserved ログ行 ID が無い。事前予約なしの送信は禁止。")
    if unresolved_tokens:
        raise SendGuardError("unresolved_token", "未置換 {{...}} トークンが残存。")
    if not from_verified:
        raise SendGuardError("from_alias_unverified", "From が sendAs alias / impersonate 対象として未検証。")
    # 全条件一致 → 呼び出し側が送信を続行してよい
