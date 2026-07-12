#!/usr/bin/env python3
"""lib/mfk_invoice_diff.py の純関数を単体テストする (pytest, API不要)。"""
from mfk_invoice_diff import (
    CADENCE_ANNUAL,
    CADENCE_ANNUAL_RENEWAL,
    CADENCE_BIMONTHLY,
    CADENCE_METERED,
    CADENCE_MONTHLY,
    CADENCE_ONESHOT,
    CADENCE_SPLIT,
    amount_changed,
    annual_renewal_period,
    bimonthly_active,
    billing_lifecycle,
    detect_gaps,
    months_elapsed,
    oneshot_active,
    split_active,
    suppress_annual_period_gaps,
)


def _b(cid, amount, status="invoice_issued"):
    return {"customer_id": cid, "amount": amount, "status": status}


def test_gap_candidates():
    """前月取引あり・今月取引なしが発行漏れ候補になる。"""
    r = detect_gaps([_b("A", 100), _b("B", 200)], [_b("A", 100)])
    assert r["gap_candidates"] == ["B"]
    assert r["continuing"] == ["A"]
    assert r["new_this_month"] == []


def test_amount_changed():
    """継続発行で金額が変わったら検出する。"""
    r = detect_gaps([_b("A", 100)], [_b("A", 150)])
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == ["A"]


def test_amount_unchanged_not_flagged():
    """金額が同じなら変動扱いしない。"""
    r = detect_gaps([_b("A", 100)], [_b("A", 100)])
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == []


def test_ignores_non_issued():
    """scheduled(未発行)は発行扱いしないので漏れ候補にならない。"""
    r = detect_gaps([_b("A", 100, "scheduled")], [])
    assert r["gap_candidates"] == []


def test_new_this_month():
    """今月のみ発行は new_this_month。"""
    r = detect_gaps([], [_b("C", 300)])
    assert r["new_this_month"] == ["C"]
    assert r["gap_candidates"] == []


def test_multi_billing_amount_sum():
    """同一顧客の複数billingは金額合算される。"""
    r = detect_gaps([_b("A", 100), _b("A", 50)], [_b("A", 100), _b("A", 50)])
    assert r["prev_amount"]["A"] == 150
    assert r["curr_amount"]["A"] == 150


def test_amount_null_does_not_crash():
    """amount が null(キー有り値None)でも落ちず 0 扱い。"""
    r = detect_gaps([_b("A", None)], [_b("A", None)])
    assert r["prev_amount"]["A"] == 0
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == []


def test_amount_float_string_truncates():
    """amount が float 文字列でも int 化して落ちない。"""
    r = detect_gaps([_b("A", "1500.50")], [])
    assert r["prev_amount"]["A"] == 1500


# --- 契約ライフサイクル (年間→月払い自動切替) ----------------------------------

def test_months_elapsed_basic():
    """初回契約月から対象月までの経過月数。"""
    assert months_elapsed("2026-04", "2026-06") == 2
    assert months_elapsed("2026-04", "2026-04") == 0
    assert months_elapsed("2026-04", "2027-04") == 12  # 13ヶ月目
    assert months_elapsed("2026-04", "2025-04") == -12  # 過去


def test_months_elapsed_invalid_returns_none():
    """不正形式/None は None。"""
    assert months_elapsed(None, "2026-06") is None
    assert months_elapsed("2026-13", "2026-06") is None  # 月13は不正
    assert months_elapsed("2026-04", "bad") is None


def test_lifecycle_annual_period():
    """経過 0〜11ヶ月は年間払い・年間期間中 (発行漏れ判定から除外対象)。"""
    for target in ("2026-04", "2026-05", "2027-03"):  # 経過 0, 1, 11
        life = billing_lifecycle("2026-04", target, "年間払い")
        assert life["cadence"] == "年間払い"
        assert life["in_annual_period"] is True


def test_lifecycle_monthly_after_12_months():
    """経過 12ヶ月以降 (13ヶ月目) は月払い・年間期間外。"""
    life = billing_lifecycle("2026-04", "2027-04", "年間払い")  # 経過12
    assert life["cadence"] == "月払い"
    assert life["in_annual_period"] is False
    assert billing_lifecycle("2026-04", "2028-01", "年間払い")["cadence"] == "月払い"


def test_lifecycle_unknown_initial_is_failsafe():
    """初回契約月不明は判定不能・年間期間扱いにしない (真の漏れを隠さない fail-safe)。"""
    life = billing_lifecycle(None, "2026-06")
    assert life["cadence"] is None
    assert life["in_annual_period"] is False
    assert billing_lifecycle("", "2026-06", "年間払い")["in_annual_period"] is False


def test_lifecycle_monthly_cycle_is_failsafe_even_with_initial_month():
    """月払い顧客は初回契約月が入っていても年間抑制しない。"""
    life = billing_lifecycle("2026-04", "2026-06", "月払い")
    assert life["cadence"] == "月払い"
    assert life["in_annual_period"] is False


def test_lifecycle_target_before_contract_not_annual():
    """対象月が初回契約月より前 (経過マイナス) は年間期間にしない。"""
    life = billing_lifecycle("2026-04", "2026-01", "年間払い")
    assert life["in_annual_period"] is False
    assert life["cadence"] == "月払い"


def test_suppress_annual_period_gaps():
    """発行漏れ候補から年間契約期間中の顧客を除外し、月払い/不明は残す。"""
    initial = {
        "ANNUAL": {"initial_contract_month": "2026-06", "payment_cycle": "年間払い"},
        "MONTHLY": {"initial_contract_month": "2026-06", "payment_cycle": "月払い"},
        "OLD": {"initial_contract_month": "2025-01", "payment_cycle": "年間払い"},
        # "UNKNOWN" は初回契約月なし → fail-safe で残す
    }
    real, in_annual = suppress_annual_period_gaps(
        ["ANNUAL", "MONTHLY", "OLD", "UNKNOWN"], initial, "2026-06")
    assert in_annual == ["ANNUAL"]
    assert real == ["MONTHLY", "OLD", "UNKNOWN"]


def test_suppress_annual_legacy_month_only_mapping_is_failsafe():
    """旧形式 {customer_id: YYYY-MM} は支払サイクル不明なので抑制しない。"""
    real, in_annual = suppress_annual_period_gaps(["c1"], {"c1": "2026-06"}, "2026-06")
    assert real == ["c1"]
    assert in_annual == []


# --- 拡張支払サイクル定数 (MECE6値 + 従量) ------------------------------------

def test_extended_cadence_constants():
    """新サイクル定数の値が design SSOT (MECE6値+従量) と一致する。"""
    assert CADENCE_MONTHLY == "月払い"
    assert CADENCE_ANNUAL == "年間払い"
    assert CADENCE_ANNUAL_RENEWAL == "年間一括更新"
    assert CADENCE_ONESHOT == "単発"
    assert CADENCE_SPLIT == "分割"
    assert CADENCE_BIMONTHLY == "隔月"
    assert CADENCE_METERED == "従量(都度)"


def test_extended_cadence_enum_is_mece_distinct():
    """6サイクル + 従量 が互いに重複しない distinct 値である。"""
    vals = [CADENCE_MONTHLY, CADENCE_ANNUAL, CADENCE_ANNUAL_RENEWAL,
            CADENCE_ONESHOT, CADENCE_SPLIT, CADENCE_BIMONTHLY, CADENCE_METERED]
    assert len(set(vals)) == len(vals)


# --- 年間一括更新 (毎年 elapsed%12==0 で再一括, ThinkTank型) -------------------

def test_annual_renewal_lump_on_update_months():
    """elapsed が 12 の倍数 (更新月) は 'lump' = 年額一括。"""
    for e in (0, 12, 24, 36):
        assert annual_renewal_period(e) == "lump"


def test_annual_renewal_prepaid_between_updates():
    """更新月以外 (0<elapsed<12 等) は 'prepaid' = 年間前払い期間中。"""
    for e in (1, 6, 11, 13, 23):
        assert annual_renewal_period(e) == "prepaid"


def test_annual_renewal_failsafe_none_and_before_contract():
    """elapsed=None (判定不能) / 負 (契約開始前) は None (fail-safe, 抑制しない)。"""
    assert annual_renewal_period(None) is None
    assert annual_renewal_period(-1) is None
    assert annual_renewal_period(-12) is None


# --- 単発 (開始月のみ) --------------------------------------------------------

def test_oneshot_active_only_on_start_month():
    """単発は elapsed==0 (開始月) のみ対象。"""
    assert oneshot_active(0) is True
    assert oneshot_active(1) is False
    assert oneshot_active(12) is False


def test_oneshot_active_none_and_negative_is_inactive():
    """elapsed=None / 負は対象外 (非クラッシュ)。"""
    assert oneshot_active(None) is False
    assert oneshot_active(-1) is False


# --- 分割 (開始月から連続Nヶ月) ----------------------------------------------

def test_split_active_within_n_months():
    """0<=elapsed<n は対象、n 以上は分割完了で対象外。"""
    assert [split_active(e, 3) for e in range(5)] == [True, True, True, False, False]


def test_split_active_failsafe_none_and_zero_n():
    """elapsed/n=None や n<=0 は False。"""
    assert split_active(None, 3) is False
    assert split_active(1, None) is False
    assert split_active(0, 0) is False
    assert split_active(-1, 3) is False


# --- 隔月 (開始月パリティで1ヶ月おき) ----------------------------------------

def test_bimonthly_active_even_elapsed_default_parity():
    """既定 start_parity=0 では elapsed 偶数月 (0,2,4..) が請求月。"""
    assert [bimonthly_active(e) for e in range(5)] == [True, False, True, False, True]


def test_bimonthly_active_odd_parity():
    """start_parity=1 では elapsed 奇数月が請求月。"""
    assert bimonthly_active(1, 1) is True
    assert bimonthly_active(2, 1) is False


def test_bimonthly_active_parity_normalized_mod2():
    """start_parity は %2 正規化されるので開始月の絶対通し番号を渡しても良い。"""
    # 開始月の絶対通し番号が奇数 (例 24313) → parity 1 と等価
    assert bimonthly_active(1, 24313) is True
    assert bimonthly_active(0, 24313) is False


def test_bimonthly_active_failsafe_none_and_negative():
    """elapsed=None / 負 / start_parity=None は False。"""
    assert bimonthly_active(None) is False
    assert bimonthly_active(-2) is False
    assert bimonthly_active(2, None) is False
