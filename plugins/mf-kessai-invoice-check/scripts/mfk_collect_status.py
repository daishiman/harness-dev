#!/usr/bin/env python3
# /// script
# name: mfk_collect_status
# purpose: billing.status が「発行済み」(=当月に実発行された請求)かを判定する純関数 SSOT (要因C1根治)。
# inputs:
#   - is_issued_billing(): billing.status 文字列 (None/大小文字ゆらぎを許容)
#   - summarize_billing_statuses(): billing dict のリスト (/billings/qualified の items 相当)
# outputs:
#   - is_issued_billing(): bool
#   - summarize_billing_statuses(): {status: count} (fetch fidelity 開示用の status 別件数)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""billing.status の『発行済み』判定 SSOT (要因C1: 収集 billing-status フィルタの根治)。

scripts/reconcile_invoices.py の collect_mf は従来 /billings/qualified を
`status=invoice_issued` の API ハードフィルタで取得していたため、発行後に後続 status
(account_transfer_notified 等) へ進んだ請求を取得段で丸ごと落とし GAP(発行漏れ)へ誤分類していた
(実測: 2606 の qualified billing 171件中 account_transfer_notified=1 = paws有限会社・
55000円税込 = 実在。stopped=2 も同時に確認)。名前非依存・再発性の欠陥。

本 module は「発行が確定した lifecycle」を保守的にホワイトリスト化する。collect_mf は
API 側の status ハードフィルタを外し、over-fetch した billing を is_issued_billing で
client 側フィルタする(=取得段で丸ごと落とさない)。

billing.status の既知 enum (skills/ref-mf-kessai-api/references/mf-kessai-api.md §4):
  invoice_issued           : 発行済み。                          → issued。
  scheduled                : 発行予定 (発行前の段階)。            → 非issued (未発行)。
  account_transfer_notified: 口座振替通知済み (発行済み請求の振替通知段階、実測で確認)。→ issued。
  stopped                  : 停止 (真の停止=非発行)。             → 非issued (ISSUED から除外)。

未知の (将来追加されうる) status は保守的に非issued側へ倒す(発行が確定した lifecycle だけを
ホワイトリスト化する方針。ここでの fail-safe は『過大収集しない』方向であり、
`suppress_annual_period_gaps` 等の『抑制しない』fail-safe とは倒す方向が逆であることに注意)。

transaction.status(passed/canceled)による月帰属・有効供給判定(lib/mfk_reconcile.build_mf_index
の `_is_active_status`)とは別レイヤであり、本 module はそれを一切変更しない(billing レベルのみ)。
"""
import argparse
import sys

# 発行が確定した lifecycle のみを保守的にホワイトリスト化する。stopped は「真の停止=非発行」
# なので ISSUED には含めない(scheduled も未発行のため含めない)。
ISSUED_BILLING_STATUSES = frozenset({"invoice_issued", "account_transfer_notified"})

# billing.status の既知 enum 全体 (self-test の分類表網羅チェック用。API doc の enum と同期する)。
KNOWN_BILLING_STATUSES = frozenset(
    {"invoice_issued", "scheduled", "account_transfer_notified", "stopped"})


def is_issued_billing(status):
    """billing.status が『発行済み』(=収集対象) かを返す (None安全・大小文字/前後空白非依存)。

    未知の status 文字列は False (非issued) 側へ倒す (発行確定 lifecycle のみを収集する
    保守的ホワイトリスト方針)。
    """
    if not isinstance(status, str):
        return False
    return status.strip().lower() in ISSUED_BILLING_STATUSES


def summarize_billing_statuses(billings):
    """billing dict のリストを status 別件数へ集計する (fetch fidelity 開示用・副作用なし)。

    status が欠落/非文字列/空文字の billing は "(unknown)" へ畳む。billings が None/空なら
    空 dict を返す。key は API が返した status の原文字列 (大小文字を正規化しない) で、
    件数は int。
    """
    counts = {}
    for b in billings or []:
        st = b.get("status") if isinstance(b, dict) else None
        key = st if isinstance(st, str) and st.strip() else "(unknown)"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _self_test():
    """status 分類表の網羅性を検証し、違反メッセージの一覧を返す (空リスト=OK)。"""
    table = [
        ("invoice_issued", True),
        ("account_transfer_notified", True),
        ("scheduled", False),
        ("stopped", False),
        ("INVOICE_ISSUED", True),          # 大小文字非依存
        ("  invoice_issued  ", True),      # 前後空白非依存
        (None, False),
        ("", False),
        ("unknown_future_status", False),  # 未知 status は保守的に非issued
    ]
    violations = []
    for status, expected in table:
        got = is_issued_billing(status)
        if got != expected:
            violations.append(f"is_issued_billing({status!r}) = {got} (期待 {expected})")

    # KNOWN_BILLING_STATUSES (API doc enum) の全件が分類表でカバーされているか
    # (新規 enum 追加の取り残し検知)。
    covered = {s.lower() for s, _ in table if isinstance(s, str)}
    missing = {s.lower() for s in KNOWN_BILLING_STATUSES} - covered
    if missing:
        violations.append(f"KNOWN_BILLING_STATUSES が分類表で未網羅: {sorted(missing)}")

    summary = summarize_billing_statuses([
        {"status": "invoice_issued"}, {"status": "invoice_issued"},
        {"status": "account_transfer_notified"}, {"status": "stopped"}, {},
    ])
    expected_summary = {
        "invoice_issued": 2, "account_transfer_notified": 1,
        "stopped": 1, "(unknown)": 1,
    }
    if summary != expected_summary:
        violations.append(
            f"summarize_billing_statuses self-test 不一致: got={summary} expected={expected_summary}")
    return violations


def main(argv=None):
    p = argparse.ArgumentParser(
        description="billing.status『発行済み』判定 self-test (C01・引数なし)")
    p.parse_args(argv)  # 引数は取らない専用 CLI。未知引数は argparse が exit 2 で弾く。
    violations = _self_test()
    if violations:
        for v in violations:
            sys.stderr.write(f"[mfk_collect_status] self-test 違反: {v}\n")
        return 1
    print(f"[mfk_collect_status] self-test OK (ISSUED={sorted(ISSUED_BILLING_STATUSES)})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
