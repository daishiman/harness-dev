#!/usr/bin/env python3
"""発行漏れ判定の純関数。MF掛け払いの billing 一覧から前月−今月の差集合を取る。

副作用なし・ネットワークなし。pytest で単体テストする (tests/test_invoice_diff.py)。
入力は /billings/qualified の items 配列 (dict のリスト)。
"""
from __future__ import annotations


def _issued_customer_ids(billings):
    """status=invoice_issued の billing から customer_id 集合を返す。"""
    return {b["customer_id"] for b in billings if b.get("status") == "invoice_issued"}


def _to_int(v):
    """金額を int 化。None/空文字/float文字列/小数に堅牢 (API由来の型揺れを吸収)。"""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _amount_by_customer(billings):
    """customer_id → amount 合計 (同一顧客に複数billingがあれば合算)。"""
    out = {}
    for b in billings:
        if b.get("status") != "invoice_issued":
            continue
        cid = b["customer_id"]
        out[cid] = out.get(cid, 0) + _to_int(b.get("amount"))
    return out


def detect_gaps(prev_billings, curr_billings):
    """前月/今月の取引月で絞り込み済み billing 一覧から発行状況を分類して返す。

    返り値 dict:
      gap_candidates : 前月取引あり・今月取引なし (発行漏れ候補) — sorted list
      continuing     : 前月・今月とも取引あり (金額変動候補) — sorted list
      new_this_month : 今月のみ発行 — sorted list
      prev_amount    : {customer_id: 前月金額}
      curr_amount    : {customer_id: 今月金額}
    """
    P = _issued_customer_ids(prev_billings)
    C = _issued_customer_ids(curr_billings)
    prev_amount = _amount_by_customer(prev_billings)
    curr_amount = _amount_by_customer(curr_billings)
    return {
        "gap_candidates": sorted(P - C),
        "continuing": sorted(P & C),
        "new_this_month": sorted(C - P),
        "prev_amount": prev_amount,
        "curr_amount": curr_amount,
    }


def amount_changed(continuing, prev_amount, curr_amount):
    """継続発行のうち金額が前月と変わった customer_id を返す。"""
    return sorted(
        cid for cid in continuing
        if prev_amount.get(cid) != curr_amount.get(cid)
    )


# --- 契約ライフサイクル (年間契約 → 12ヶ月後に月払いへ自動切替) -----------------
# 仕様 (ユーザー確定 2026-06-23): 支払サイクルが「年間払い」で、かつ初回契約月から
# 12ヶ月以内なら年間前払い期間中として月次請求なしを正常扱いする。支払サイクルが
# 月払い/空欄/不明なら発行漏れ判定を抑制しない fail-safe に倒す。

ANNUAL_MONTHS = 12
CADENCE_ANNUAL = "年間払い"
CADENCE_MONTHLY = "月払い"


def _ym_index(ym):
    """'YYYY-MM' を月通し番号 (年*12+月) に変換。形式不正なら None。"""
    if not isinstance(ym, str):
        return None
    parts = ym.split("-")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return None
    y, m = int(parts[0]), int(parts[1])
    if not (1 <= m <= 12):
        return None
    return y * 12 + (m - 1)


def months_elapsed(initial_contract_month, target_ym):
    """初回契約月から対象月までの経過月数。どちらか不正なら None。

    例: initial=2026-04, target=2026-06 → 2。initial=2026-04, target=2027-04 → 12。
    """
    a, b = _ym_index(initial_contract_month), _ym_index(target_ym)
    if a is None or b is None:
        return None
    return b - a


def billing_lifecycle(initial_contract_month, target_ym, payment_cycle=None):
    """初回契約月・対象月・支払サイクルから年間契約期間中かを判定する。

    年間期間 = [初回契約月, 初回契約月 + 12ヶ月) (経過0〜11ヶ月)。
    返り値 dict:
      cadence          : '年間払い' / '月払い' / None(判定不能)
      in_annual_period : True なら年間契約期間中 (月次の発行漏れ判定から除外すべき)
      months_elapsed   : 経過月数 (None=判定不能)

    支払サイクルが年間払いでない、または初回契約月が不明 (None/空/形式不正) の場合は
    in_annual_period=False を返し、呼び出し側の発行漏れ判定を抑制しない
    (fail-safe: 真の漏れを隠さない)。対象月が初回契約月より前 (経過マイナス) の場合も
    年間期間扱いにはしない。
    """
    elapsed = months_elapsed(initial_contract_month, target_ym)
    if payment_cycle != CADENCE_ANNUAL:
        return {
            "cadence": payment_cycle if payment_cycle == CADENCE_MONTHLY else None,
            "in_annual_period": False,
            "months_elapsed": elapsed,
        }
    if elapsed is None:
        return {"cadence": None, "in_annual_period": False, "months_elapsed": None}
    in_annual = 0 <= elapsed < ANNUAL_MONTHS
    return {
        "cadence": CADENCE_ANNUAL if in_annual else CADENCE_MONTHLY,
        "in_annual_period": in_annual,
        "months_elapsed": elapsed,
    }


def _contract_term(value):
    """契約情報 value を (initial_contract_month, payment_cycle) に正規化する。

    旧形式の文字列だけでは支払サイクルが不明なので年間抑制しない。
    """
    if isinstance(value, dict):
        return value.get("initial_contract_month"), value.get("payment_cycle")
    return value, None


def suppress_annual_period_gaps(gap_candidates, initial_contract_months, target_ym):
    """発行漏れ候補から「年間契約期間中の顧客」を除外する。

    gap_candidates: detect_gaps の gap_candidates (customer_id のリスト)。
    initial_contract_months: {customer_id: {initial_contract_month, payment_cycle}}。
      旧形式 {customer_id: 'YYYY-MM'} は支払サイクル不明として抑制しない。
    target_ym: 対象月。

    返り値 (real_gaps, in_annual): real_gaps=月払いフェーズで真に発行が欠けた候補、
    in_annual=年間契約期間中ゆえ除外した候補。初回契約月不明の顧客は real_gaps 側に残す
    (fail-safe で真の漏れを隠さない)。
    """
    real_gaps, in_annual = [], []
    for cid in gap_candidates:
        initial_month, payment_cycle = _contract_term(initial_contract_months.get(cid))
        life = billing_lifecycle(initial_month, target_ym, payment_cycle)
        (in_annual if life["in_annual_period"] else real_gaps).append(cid)
    return sorted(real_gaps), sorted(in_annual)


# --- 拡張支払サイクル (MECE6値 + 従量) の純関数 --------------------------------
# 仕様 (ユーザー確定 2026-06-26 / design wi22zpkq2): 支払サイクルは DB1 の単一列で
# 1契約=1値を明示設定する (推測しない)。年周期 = ANNUAL_MONTHS=12 固定。既存
# CADENCE_ANNUAL / CADENCE_MONTHLY / billing_lifecycle は byte 一致を維持し
# (run-mf-invoice-check の年間抑制回帰を壊さない)、ここでは追加サイクルの当月判定だけを
# 純関数 (副作用なし・月粒度・day破棄) で additive に提供する。入力 elapsed は
# months_elapsed(契約開始日, 対象月) が返す月通し番号の差 (int / None)。
#
#   月払い (CADENCE_MONTHLY)             : 毎月                        ... 呼び出し側 (常に対象)
#   年間払い (CADENCE_ANNUAL)            : 初年度のみ一括→翌年月額      ... billing_lifecycle
#   年間一括更新 (CADENCE_ANNUAL_RENEWAL): 毎年更新で再び年間一括(ThinkTank型) ... annual_renewal_period
#   単発 (CADENCE_ONESHOT)               : 開始月のみ                   ... oneshot_active
#   分割 (CADENCE_SPLIT)                 : 開始月から連続Nヶ月           ... split_active
#   隔月 (CADENCE_BIMONTHLY)             : 開始月パリティで1ヶ月おき       ... bimonthly_active
#   従量(都度) (CADENCE_METERED)         : 期待額不定で常に要確認         ... 展開規則は呼び出し側

CADENCE_ANNUAL_RENEWAL = "年間一括更新"
CADENCE_ONESHOT = "単発"
CADENCE_SPLIT = "分割"
CADENCE_BIMONTHLY = "隔月"
CADENCE_METERED = "従量(都度)"


def annual_renewal_period(elapsed):
    """年間一括更新サイクルの当月種別を返す (毎年更新で再び年間一括する ThinkTank型)。

    elapsed = months_elapsed(契約開始日, 対象月) (月通し番号の差, day破棄)。
    返り値:
      'lump'    : 更新月 (elapsed>=0 かつ elapsed%12==0) → 期待=年額一括 (MATCH_ANNUAL/GAP)
      'prepaid' : 年間前払い期間中 (elapsed>=0 かつ elapsed%12!=0) → 対象外 (SUPPRESS_ANNUAL)
      None      : 判定不能 (elapsed=None) / 契約開始前 (elapsed<0)。
                  fail-safe: 呼び出し側で抑制せず要確認/データ不備として扱える。

    『年間払い』(CADENCE_ANNUAL, 初年度のみ一括→翌年月額) とは別物。月額へは移行せず
    毎年 lump が再来する。年周期は ANNUAL_MONTHS=12 固定。
    """
    if elapsed is None or elapsed < 0:
        return None
    return "lump" if elapsed % ANNUAL_MONTHS == 0 else "prepaid"


def oneshot_active(elapsed):
    """単発サイクル: 開始月 (elapsed==0) のみ当月対象。他月は対象外 (SUPPRESS_ONESHOT)。

    elapsed が None (開始日不明) なら False を返す (None==0 は False ゆえ非クラッシュ)。
    非月払いサイクルで開始日空欄は呼び出し側がデータ不備 REVIEW として扱う。
    """
    return elapsed == 0


def split_active(elapsed, n):
    """分割サイクル: 開始月から連続Nヶ月 (0<=elapsed<n) が当月対象。

    n = 分割回数 (DB1『分割回数』)。範囲外 (elapsed>=n=分割完了) や
    elapsed/n が None なら False (対象外/データ不備として呼び出し側が扱う)。
    """
    if elapsed is None or n is None:
        return False
    return 0 <= elapsed < n


def bimonthly_active(elapsed, start_parity=0):
    """隔月サイクル: 開始月パリティに一致する月 (elapsed%2==start_parity) が当月対象。

    elapsed>=0 かつ (elapsed%2)==(start_parity%2) で請求月。請求月リストの手入力は
    不要で契約開始日からの elapsed パリティで決定論的に判定する (design 隔月規則)。
    start_parity 既定 0 = 開始月そのものを請求月とする (elapsed 偶数月が請求月)。
    elapsed/start_parity が None なら False。start_parity は %2 で正規化するので
    開始月の絶対通し番号をそのまま渡しても良い。
    """
    if elapsed is None or start_parity is None:
        return False
    return elapsed >= 0 and (elapsed % 2) == (start_parity % 2)
