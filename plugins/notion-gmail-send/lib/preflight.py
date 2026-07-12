#!/usr/bin/env python3
# /// script
# name: preflight
# purpose: dry-run(G0)/認証(G1)/依存実体(G2)/送信直前(G3) を fail-closed 検証する統括ロジック。未充足なら送信フェーズへ進ませず、誘導先 (GCP手順/db-setup/本文記入) を返す。
# inputs:
#   - config: dict / from_addr: str / bodies_true_count: int / 送信直前パラメータ
# outputs:
#   - gate_g1_auth()/gate_g2_dependencies()/gate_g3_presend(): GateResult(dict)
# contexts: [C, E]
# network: true   # G1 の実API検証時のみ (probe_api=True)
# write-scope: none
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""preflight gate (仕様書 §10/§13)。

dry-run preflight (G0) と live-send preflight (G1/G2/G3) を分離する。dry-run は送信ログDB
なしでも第1段件数・plan_hash まで作成できるが、live-send は送信ログDB なしで必ず中断する。
各ゲートは GateResult を返し、呼び出し側 (orchestrator) が全 PASS まで送信フェーズへ進めない。
"""
from __future__ import annotations

try:
    from . import secrets, notion_config, gmail_client
except ImportError:  # スクリプトが lib を sys.path に載せた場合
    import secrets, notion_config, gmail_client  # type: ignore


def _result(gate: str, passed: bool, reason: str = "", action: str = "", detail: str = "") -> dict:
    return {"gate": gate, "passed": passed, "reason": reason, "action": action, "detail": detail}


def gate_g1_auth(config: dict, from_addr: str, *, probe_api: bool = False,
                 verify_from_addrs: list[str] | None = None) -> list[dict]:
    """G1 認証: Keychain Notion鍵/SA鍵の存在、(probe_api 時) DWD+gmail.send+sendAs を実API検証。

    `verify_from_addrs` を渡すと先頭 From だけでなく全 distinct From を sendAs 検証する
    (複数本文が別 From を持つ campaign で 2 件目以降の未検証 From を preflight で先出しする)。
    未指定時は `from_addr` 単独を検証する。未充足は doc/GCP-Gmail送信設定手順.md へ誘導 (action="gcp_setup")。
    """
    results: list[dict] = []
    # Notion 鍵
    if secrets.probe_notion_api_key():
        results.append(_result("G1.notion_key", True))
    else:
        results.append(_result("G1.notion_key", False, "notion_key_missing",
                                "keychain_setup", "notion-api-key.<keychain-prefix> が無い"))

    # Google SA 鍵 (config の sender.sa_keychain)
    sender = notion_config.get_sender(config)
    sa = sender.get("sa_keychain") or {}
    svce, acct = sa.get("service"), sa.get("account")
    if not svce:
        results.append(_result("G1.sa_key", False, "sa_keychain_unconfigured",
                                "gcp_setup", "notion_gmail_send.sender.sa_keychain.service 未設定"))
        return results
    if not secrets.probe_google_sa_key(svce, acct):
        results.append(_result("G1.sa_key", False, "sa_key_missing", "gcp_setup",
                                f"Keychain に SA鍵が無い: service={svce}"))
        return results
    results.append(_result("G1.sa_key", True))

    if not probe_api:
        return results

    # 実API検証 (doctor --probe): DWD impersonate + sendAs alias
    impersonate = sender.get("impersonate") or from_addr
    # 検証対象 From を確定 (distinct・順序保持)。未指定なら from_addr 単独。
    to_verify = verify_from_addrs if verify_from_addrs is not None else [from_addr]
    to_verify = list(dict.fromkeys(a for a in to_verify if a))
    try:
        sa_key = secrets.get_google_sa_key(svce, acct)
        client = gmail_client.GmailClient(sa_key, impersonate)
        for fa in to_verify:
            if client.verify_sendas(fa):
                results.append(_result("G1.sendas", True, detail=f"From={fa}"))
            else:
                results.append(_result("G1.sendas", False, "from_alias_unverified", "gcp_setup",
                                        f"From={fa} が sendAs/impersonate 対象として未検証"))
    except gmail_client.GmailUnavailable as e:
        results.append(_result("G1.dwd", False, "dwd_or_lib_unavailable", "gcp_setup", str(e)))
    return results


def gate_g2_dependencies(config: dict, bodies_true_count: int) -> list[dict]:
    """G2 依存実体: 送信ログDB ID 解決可否と本文 true ≥ 1。"""
    results: list[dict] = []
    try:
        log_db_id = notion_config.get_db_id("gmail-send-log", config)
        results.append(_result("G2.log_db", True, detail=f"db_id={log_db_id[:8]}…"))
    except notion_config.ConfigError as e:
        results.append(_result("G2.log_db", False, "log_db_id_missing", "db_setup", str(e)))

    if bodies_true_count >= 1:
        results.append(_result("G2.body", True, detail=f"本文true={bodies_true_count}"))
    else:
        results.append(_result("G2.body", False, "no_body", "fill_body",
                                "メッセージ対象=✅ かつ 本文非空 の行が0件。本文記入が必要"))
    return results


def gate_g3_presend(*, approved_plan_hash: str, plan_hash: str,
                    approved_count: int, actual_count: int,
                    approved_first_to: str, actual_first_to: str) -> dict:
    """G3 送信直前のキャンペーン全体整合 (plan_hash/件数/先頭To)。

    個別送信単位の最終ゲートは gmail_client 内の send_guard が担う。本ゲートはキャンペーン
    レベルの一括検査で、不一致なら全体中断させる。
    """
    if not approved_plan_hash or approved_plan_hash != plan_hash:
        return _result("G3.plan_hash", False, "plan_hash_mismatch", "abort",
                       "承認 plan_hash と現在の plan_hash が不一致")
    if int(approved_count) != int(actual_count):
        return _result("G3.count", False, "count_mismatch", "abort",
                       f"承認件数 {approved_count} ≠ 送信予定 {actual_count}")
    if (approved_first_to or "") != (actual_first_to or ""):
        return _result("G3.first_to", False, "first_to_mismatch", "abort", "承認先頭To不一致")
    return _result("G3", True)


def all_passed(results: list[dict]) -> bool:
    return all(r["passed"] for r in results)
