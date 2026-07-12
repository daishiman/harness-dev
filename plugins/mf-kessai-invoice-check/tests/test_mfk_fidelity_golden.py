#!/usr/bin/env python3
"""症状①〜⑦ MF実績ゴールデン fixture 回帰 + OUT2 characterization (goal-spec C7)。

MF実績起点の amount-gate 根治 (C05 mfk_actuals) が、契約期待額駆動で金額を落としていた症状を
再現しつつ根治を凍結する。reconcile engine (build_mf_index → classify) を end-to-end で駆動し、
各 status verdict 行の MF実績 carrier (actual_amount/reliable_issued/supply_state) を検証する。

症状 → 根本原因 → 検証:
  ①今月金額空白       R-a amount-gate  amount_mismatch でも actual_amount が実額で焼かれる (空白でない)
  ③金額一致なのに未☑  R-a amount-gate  match で reliable_issued=True (契約突合に依らず実績で issued)
  ⑤請求ありなのに空白  R-a/R-c multi    (a)evidence-gate=amount_mismatch で actual_amount 充填
  ⑥今月金額相違追えず  R-a amount-gate  actual_amount=実額 かつ 期待額と差分開示可能
  ⑦会社名だけ取得     R-a amount-gate  会社境界一致で active 供給あれば actual_amount が取れる

K2 温存: amount_mismatch/no_supply の evidence は None のまま (DB2 matched_amount 不変)。
K3 隔離: 取消明細のみ (REVIEW_CANCELED) は reliable_issued=False・actual_amount=None (取消前額非昇格)。
OUT2 不変: SUPPRESS_ANNUAL / MATCH_ENDED_FINAL / J1名寄せ の既存 verdict は改修前後で不変。
"""
import os
import sys

import mfk_reconcile as R
import mfk_period_report as P

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import reconcile_invoices as O  # noqa: E402  (build_sink_rows の温存確認用)


def _mf(customers):
    return {"customers": customers}


def _line(desc, amount, status="passed", canceled_at=None, billing_id="b1"):
    return {"desc": desc, "amount": amount, "status": status,
            "canceled_at": canceled_at, "billing_id": billing_id}


def _contract(torihiki, product, genkatanka, **extra):
    c = {"取引先": torihiki, "商品": product, "現行単価": genkatanka,
         "契約開始日": "2601", "支払サイクル": "月払い", "ステータス": "有効"}
    c.update(extra)
    return c


def _classify_one(contract, customers, target="2606"):
    idx = R.build_mf_index(_mf(customers))
    return R.classify([contract], idx, target)[0]


# ---------------------------------------------------------------------------
# 症状① / ⑥: 今月金額空白 / 金額相違を追えない (amount_mismatch で actual_amount 充填)
# ---------------------------------------------------------------------------
def test_symptom_1_6_amount_mismatch_carries_actual_amount():
    # 期待額 60000 だが MF実額 55000 を発行。旧実装は evidence=None で金額列が空白 (症状①)、
    # 差分を追えなかった (症状⑥)。C05 は actual_amount=55000 を carrier に焼く。
    row = _classify_one(_contract("アクメ商事", "コンサル", 60000),
                        {"c1": {"name": "アクメ商事", "lines": [_line("コンサル", 55000)]}})
    assert row["verdict"] == "REVIEW_AMOUNT_MISMATCH"
    assert row["actual_amount"] == 55000            # ① 空白でなく実額が焼かれる
    assert row["reliable_issued"] is True
    assert row["supply_state"] == "active"
    # ⑥ D3: 金額列は実額 (期待額 60000 でなく実発行額 55000) を表示、期待額との差分は開示可能。
    assert P._amount_of(row) == 55000
    assert P._amount_of(row) != row["現行単価"]      # 実額 ≠ 期待額 (差分あり)


# ---------------------------------------------------------------------------
# 症状③: 金額一致なのに未☑ (match で reliable_issued=True)
# ---------------------------------------------------------------------------
def test_symptom_3_match_is_reliably_issued():
    row = _classify_one(_contract("ベータ社", "月額", 50000),
                        {"c1": {"name": "ベータ社", "lines": [_line("月額", 50000)]}})
    assert row["verdict"] == "MATCH_MONTHLY"
    assert row["reliable_issued"] is True           # 実績で issued (契約突合に依らない)
    assert row["actual_amount"] == 50000
    assert P._is_issued(row) is True                # 未☑ にならない


# ---------------------------------------------------------------------------
# 症状⑤(a): 請求ありなのに今月金額空白 (evidence-gate 由来=amount_mismatch を実額で埋める)
# ---------------------------------------------------------------------------
def test_symptom_5a_evidence_gate_filled_by_actual():
    row = _classify_one(_contract("ガンマ社", "保守", 80000),
                        {"c1": {"name": "ガンマ社", "lines": [_line("保守", 77000)]}})
    assert row["verdict"] == "REVIEW_AMOUNT_MISMATCH"
    assert P._amount_of(row) == 77000               # 請求あり=実額が金額列に出る (空白でない)


# ---------------------------------------------------------------------------
# 症状⑦: 会社名だけ取得で金額空白 (会社境界一致で active 供給の実額が取れる)
# ---------------------------------------------------------------------------
def test_symptom_7_company_boundary_supply_has_amount():
    # 会社名は一致するが期待額と異なる供給 → 旧実装は会社名だけ取れて金額空白。C05 は実額を焼く。
    row = _classify_one(_contract("デルタ株式会社", "月額", 30000),
                        {"c1": {"name": "デルタ株式会社", "lines": [_line("月額", 33000)]}})
    assert row["actual_amount"] == 33000
    assert row["reliable_issued"] is True


# ---------------------------------------------------------------------------
# K2 温存: amount_mismatch/no_supply の evidence は None のまま (DB2 matched_amount 不変)
# ---------------------------------------------------------------------------
def test_k2_evidence_byte_invariant_for_mismatch():
    row = _classify_one(_contract("アクメ商事", "コンサル", 60000),
                        {"c1": {"name": "アクメ商事", "lines": [_line("コンサル", 55000)]}})
    assert row["evidence"] is None                  # evidence は据え置き (書き換えない)
    # reconcile_invoices.build_sink_rows (別 skill の DB2 loader) は evidence.amount を読む。
    # evidence=None のままなので matched_amount も None (温存境界を割らない)。
    sink = O.build_sink_rows({"rows": [row], "orphans": []}, {})
    assert sink[0]["matched_amount"] is None


def test_k2_evidence_byte_invariant_for_no_supply():
    row = _classify_one(_contract("ノーサプライ社", "月額", 50000),
                        {"c1": {"name": "別の会社", "lines": [_line("月額", 50000)]}})
    assert row["verdict"] == "GAP"
    assert row["evidence"] is None
    assert row["reliable_issued"] is False
    assert row["actual_amount"] is None


# ---------------------------------------------------------------------------
# K3 隔離: 取消明細のみ (REVIEW_CANCELED) は issued 化しない・取消前額を金額列に出さない
# ---------------------------------------------------------------------------
def test_k3_canceled_only_not_issued_and_amount_blank():
    row = _classify_one(_contract("キャンセル社", "保守", 40000),
                        {"c1": {"name": "キャンセル社",
                                "lines": [_line("保守", 40000, status="canceled",
                                                canceled_at="2026-06-10")]}})
    assert row["verdict"] == "REVIEW_CANCELED"
    assert row["reliable_issued"] is False          # 取消前額を issued 化しない
    assert row["actual_amount"] is None
    assert row["supply_state"] == "inactive_canceled"
    assert P._is_issued(row) is False               # 継続発行へ誤分類しない
    assert P._amount_of(row) is None                # 金額列に取消前額を出さない


# ---------------------------------------------------------------------------
# OUT2 characterization: 既存 verdict の不変性 (SUPPRESS_ANNUAL / MATCH_ENDED_FINAL / J1)
# ---------------------------------------------------------------------------
def test_out2_suppress_annual_unchanged():
    # 年間払い前払い期間中 (elapsed 1..11・当月 MF 無し) は SUPPRESS_ANNUAL のまま不変。
    c = _contract("年契約社", "年額", 600000, 支払サイクル="年間払い", 契約開始日="2603")
    row = _classify_one(c, {"c1": {"name": "別会社", "lines": []}})
    assert row["verdict"] == "SUPPRESS_ANNUAL"


def test_out2_match_ended_final_unchanged():
    # 契約終了月の最終請求 (終了月〜翌月の MF) は MATCH_ENDED_FINAL のまま不変。
    c = _contract("終了社", "月額", 50000, ステータス="終了", 契約終了月="2606", 契約開始日="2601")
    row = _classify_one(c, {"c1": {"name": "終了社", "lines": [_line("月額", 50000)]}})
    assert row["verdict"] == "MATCH_ENDED_FINAL"
    assert row["reliable_issued"] is True           # 最終請求は実発行済み
    assert row["actual_amount"] == 50000


def test_out2_j1_cross_client_not_matched():
    # J1: 会社境界に該当会社なし・別会社で同名エンドクライアント同額 → MATCH 扱いしない (GAP+証跡)。
    c = _contract("架空商店", "月額", 50000, エンドクライアント名="山田太郎")
    row = _classify_one(c, {"c1": {"name": "無関係株式会社",
                                   "lines": [_line("月額(山田太郎)", 50000)]}})
    assert row["verdict"] == "GAP"                  # cross_client は MATCH に化けない
    assert row["reliable_issued"] is False          # 自境界に active 供給なし


def test_category_scope_falls_back_to_company_supply_when_category_misses():
    # 会社名は完全一致(境界確定は _company_match のみ)。商品カテゴリ不一致時に会社供給へ
    # フォールバックする挙動を検証する(alias 非依存)。
    row = _classify_one(_contract("セカンドコミュニティ株式会社", "チイキズカン利用料", 50000),
                        {"c1": {"name": "セカンドコミュニティ株式会社",
                                "lines": [_line("チイキズカン業務委託費", 50000)]}})
    assert row["supply_state"] == "active"
    assert row["actual_amount"] == 50000
    assert P._amount_of(row) == 50000


# ---------------------------------------------------------------------------
# C14 回帰(Goodhart 防止): 会社名 alias ハードコード撤去後、name-drift(日本語⇄英語表記等)は
# _company_match で境界一致しないが、MF顧客ID が契約へ carry されていれば境界解決できる。
# _COMPANY_ALIAS_GROUPS 復活なしに偽発行漏れ 0 件を保つ一般解(C02)の受入テスト。
# ---------------------------------------------------------------------------
def test_name_drift_matches_via_mf_customer_id_only_not_company_alias():
    notion_name, mf_name, desc, amount = (
        "セカンドコミュニティ株式会社", "2nd Community株式会社", "チイキズカン業務委託費", 50000,
    )
    # 会社名だけでは境界一致しない(alias 撤去の効果そのもの・偶発的な緩和が無いことの確認)。
    assert R._company_match(R.normalize(notion_name), R.normalize(mf_name)) is False

    # MF顧客ID が契約へ carry されていれば _boundary_customers の ID優先経路で境界解決できる。
    row = _classify_one(_contract(notion_name, "チイキズカン利用料", amount, MF顧客ID="c1"),
                        {"c1": {"name": mf_name, "lines": [_line(desc, amount)]}})
    assert row["verdict"] == "MATCH_MONTHLY"
    assert row["reliable_issued"] is True
    assert row["actual_amount"] == amount
    assert P._amount_of(row) == amount
