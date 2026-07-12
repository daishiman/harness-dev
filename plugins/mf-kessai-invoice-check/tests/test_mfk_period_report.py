#!/usr/bin/env python3
"""scripts/mfk_period_report.py (C03: 前月↔今月の発行状態遷移分類) の単体テスト。

オフライン・fixture はテスト内 dict で自己完結 (network/ファイル不要。CLI は tmp_path を使う)。
検証観点 (component-inventory C03 の criteria 由来):
  - 対象月決定 (7/2 実行なら今月=6月分・先月=5月分)。
  - 取引先×商品集合の 4 状態 (継続発行 / 前月なし今月あり / 元々請求なし / 前月あり今月なし)。
  - 差分該当取引先限定の 12ヶ月遡り (根拠コメント補強のみ・既存判定を上書きしない)。
  - 年契約周期 (SUPPRESS_ANNUAL 一次源) / 年→月切替 / トライアル完了 (canon 前生名) /
    契約終了 (SUPPRESS_ENDED 消費・自由文非再パース) / 発行漏れ候補(要対応) の全分岐。
  - 継続発行も全行 emit・今月なし前月なしは非 emit。
  - 根拠なき終了月が REVIEW_ENDED_NO_BASIS で漏れ隠蔽されない安全弁。
"""
import datetime
import json

import mfk_period_report as P


# ---------------------------------------------------------------------------
# 行ビルダ (per-月 verdict 行を模す最小 dict)
# ---------------------------------------------------------------------------
def _row(customer, product, verdict, amount=50000, contract_id=None,
         end_month=None, kakunin=None, evidence_amount=None, raw=None):
    r = {"取引先": customer, "商品": product, "verdict": verdict, "現行単価": amount}
    if contract_id is not None:
        r["契約ID"] = contract_id
    if end_month is not None:
        r["契約終了月"] = end_month
    if kakunin is not None:
        r["確認内容"] = kakunin
    if raw is not None:
        r["商品生名"] = raw
    if evidence_amount is not None:
        r["evidence"] = {"amount": evidence_amount, "desc": "MF明細"}
    return r


def _classify(prev_rows, curr_rows, lookback=None, contract_end=None, target="2606"):
    pairing = P.compare_periods(prev_rows, curr_rows)
    return P.classify_period_transition(
        pairing, lookback=lookback, contract_end=contract_end, target_month=target)


def _by_customer(report, customer):
    return [r for r in report if r["customer"] == customer]


# ---------------------------------------------------------------------------
# 対象月決定
# ---------------------------------------------------------------------------
def test_resolve_target_months_july_run():
    # 2026-07-02 実行 → 今月=2606 (6月分)・先月=2605 (5月分)。
    curr, prev = P.resolve_target_months(datetime.date(2026, 7, 2))
    assert curr == "2606"
    assert prev == "2605"


def test_resolve_target_months_january_wraps_year():
    curr, prev = P.resolve_target_months(datetime.date(2026, 1, 15))
    assert curr == "2512"   # 前月=前年12月
    assert prev == "2511"


def test_resolve_target_months_default_today():
    # today 省略でも (YYMM, YYMM) を返す (network なし・例外なし)。
    curr, prev = P.resolve_target_months()
    assert len(curr) == 4 and len(prev) == 4


def test_prev_month_helpers_invalid():
    assert P._prev_month_ym("bad") is None
    assert P._prev_year_month("bad") is None


# ---------------------------------------------------------------------------
# compare_periods: 4 状態
# ---------------------------------------------------------------------------
def test_compare_periods_four_states():
    prev = [
        _row("継続社", "月額", "MATCH_MONTHLY"),
        _row("停止社", "月額", "MATCH_MONTHLY"),
        _row("既存対象外社", "年額", "SUPPRESS_ANNUAL"),
    ]
    curr = [
        _row("継続社", "月額", "MATCH_MONTHLY"),
        _row("新規社", "月額", "MATCH_MONTHLY"),
        _row("停止社", "月額", "GAP"),
        _row("既存対象外社", "年額", "SUPPRESS_ANNUAL"),
    ]
    pairing = {tuple(p["key"]): p["state"] for p in P.compare_periods(prev, curr)}
    assert pairing[(P.R.normalize("継続社"), P.R.normalize("月額"))] == P.STATE_CONTINUED
    assert pairing[(P.R.normalize("新規社"), P.R.normalize("月額"))] == P.STATE_NEW
    assert pairing[(P.R.normalize("停止社"), P.R.normalize("月額"))] == P.STATE_STOPPED
    assert pairing[(P.R.normalize("既存対象外社"), P.R.normalize("年額"))] == P.STATE_NONE


def test_none_state_not_emitted_and_continued_all_emitted():
    prev = [_row("継続社", "月額", "MATCH_MONTHLY"),
            _row("対象外社", "年額", "SUPPRESS_ANNUAL")]
    curr = [_row("継続社", "月額", "MATCH_MONTHLY"),
            _row("対象外社", "年額", "SUPPRESS_ANNUAL")]
    report = _classify(prev, curr)
    customers = {r["customer"] for r in report}
    assert "継続社" in customers          # 継続発行は emit
    assert "対象外社" not in customers     # 元々請求なしは非 emit
    cont = _by_customer(report, "継続社")[0]
    assert cont["gap_check"] == "正常"
    assert cont["period_diff"] == "継続発行"


def test_continued_amount_change_note():
    prev = [_row("値上げ社", "月額", "MATCH_MONTHLY", amount=40000)]
    curr = [_row("値上げ社", "月額", "MATCH_MONTHLY", amount=50000)]
    row = _classify(prev, curr)[0]
    assert row["amount"] == 50000
    assert row["prev_amount"] == 40000
    assert "金額変動" in row["comment"]


def test_issued_via_evidence_amount_only():
    # verdict が ISSUED 集合外でも evidence に正の金額があれば発行あり扱い。
    prev = [_row("証跡社", "月額", "REVIEW_QTY_MISMATCH", evidence_amount=12000)]
    curr = [_row("証跡社", "月額", "REVIEW_AMOUNT_MISMATCH", evidence_amount=12000)]
    row = _classify(prev, curr)[0]
    assert row["period_diff"] == "継続発行"


# ---------------------------------------------------------------------------
# C4: prev 取消の継続性 (_prev_continuity_issued は _is_issued の金額列セマンティクスと別述語)
# ---------------------------------------------------------------------------
def test_prev_canceled_with_continuing_curr_match_is_continued_not_new():
    # C4: prev=REVIEW_CANCELED (supply_state=inactive_canceled かつ canceled_at あり=前月に一度発行
    # され後に取消) + curr が継続発行 (MATCH) の契約は、継続性上 STATE_NEW でなく STATE_CONTINUED
    # (症状=2nd Community 5月分7/3取消)。金額列は _amount_of/_is_issued の K3 セマンティクス通り
    # (取消前額を金額列に出さない) 不変のまま。
    prev = [{"取引先": "継続取消社", "商品": "月額", "verdict": "REVIEW_CANCELED",
             "現行単価": 50000, "actual_amount": None,
             "supply_state": "inactive_canceled", "canceled_at": "2026-07-03"}]
    curr = [_row("継続取消社", "月額", "MATCH_MONTHLY", amount=50000)]
    row = _classify(prev, curr)[0]
    assert row["period_diff"] == "継続発行"
    assert row["gap_check"] == "正常"
    assert row["prev_amount"] is None  # K3: 取消前額は金額列に出さない (温存)


def test_prev_true_unissued_none_state_stays_new_not_continued():
    # 真の未発行 (supply_state=none) は継続性の特例対象外。prev が一度も発行されていない通常の
    # 新規は従来通り STATE_NEW のまま (C4 の適用範囲を取消行に限定する安全弁)。
    prev = [{"取引先": "真新規継続社", "商品": "月額", "verdict": None,
             "supply_state": "none"}]
    curr = [_row("真新規継続社", "月額", "MATCH_MONTHLY")]
    pairing = P.compare_periods(prev, curr)
    assert pairing[0]["state"] == P.STATE_NEW


def test_prev_canceled_without_canceled_at_stays_new():
    # inactive_canceled でも canceled_at が無ければ (前月発行の裏付けが弱い) 継続性特例は発火せず
    # 従来通り STATE_NEW のまま (述語の厳密さを保つ)。
    prev = [{"取引先": "取消日欠社", "商品": "月額", "verdict": "REVIEW_CANCELED",
             "supply_state": "inactive_canceled", "canceled_at": None}]
    curr = [_row("取消日欠社", "月額", "MATCH_MONTHLY")]
    pairing = P.compare_periods(prev, curr)
    assert pairing[0]["state"] == P.STATE_NEW


# ---------------------------------------------------------------------------
# 状態: 前月なし今月あり (新規 / 年→月切替)
# ---------------------------------------------------------------------------
def test_new_without_lookback_normal_but_discloses_unverified():
    # 新不変則 (Fix A・要件1を NEW 経路へ拡張): 前月なし今月あり=**今月に実発行あり**=定義上
    # 『発行漏れ』ではない → 漏れチェックは正常✓。旧 D1 は『発行漏れ (今月未発行)』と『内容の
    # 未確認 (年→月切替か真の新規か)』を混同して要対応☐へ flip していた (症状①『金額あるのに
    # チェックが入らない』の根治)。未確認は checkbox を倒さず**コメントで開示**する。
    curr = [_row("新規社", "月額", "MATCH_MONTHLY")]
    row = _classify([], curr)[0]
    assert row["gap_check"] == "正常"                 # 今月実発行あり=正常✓ (漏れではない)
    assert row["period_diff"] == "新規/年→月切替"
    assert "未実行" in row["comment"] and "未確認" in row["comment"]   # 未確認はコメントで開示


def test_new_with_lookback_but_no_annual_normal_true_new():
    # 新不変則: ルックバックを実行し年契約履歴が無い「真の新規」も、今月に実発行あり=正常✓。
    # 未実行 (上のテスト) と comment で区別され、真の新規である旨は明示される (checkbox は倒さない)。
    curr = [_row("真新規社", "月額", "MATCH_MONTHLY")]
    lookback = {"別の社": [{"month": "2506", "annual": True}]}  # 対象取引先は不在=確認済み・裏付けなし
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"                 # 今月実発行あり=正常✓
    assert "確認したが" in row["comment"] and "真の新規" in row["comment"]
    assert "未実行" not in row["comment"]


def test_new_with_annual_backing_is_normal():
    # D1: 12ヶ月履歴に **同一商品** の年契約一括裏付けがあれば年→月切替=正常☑ (裏付けありのみ GAP_OK)。
    curr = [_row("年→月社", "月額", "MATCH_MONTHLY")]
    lookback = {"年→月社": [{"month": "2506", "annual": True, "product": "月額"}]}
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"


def test_new_mixed_contract_product_b_normal_via_issuance_not_annual():
    # 新不変則: 別商品Bは**今月実発行あり=正常✓** (Aの年契約履歴で正常化するのではなく B 自身の
    # 実発行が根拠)。商品粒度突合は保持され A の年契約性を B へ誤帰属しない (漏れ隠蔽方向の是正は
    # 維持): コメントは B の年契約裏付けを主張せず『真の新規/未確認』を開示する。
    curr = [_row("混在社", "新商品B", "MATCH_MONTHLY")]
    lookback = {"混在社": [{"month": "2506", "annual": True, "product": "年契約商品A"}]}
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"     # Bは今月実発行あり=正常 (漏れではない)
    assert "真の新規" in row["comment"]   # Aの年契約裏付けをBへ誤帰属しない (商品粒度突合は保持)


def test_new_with_fidelity_partial_still_normal_issuance_confirmed():
    # 新不変則: C06 exit3 (lookback 部分欠損) でも**今月の実発行は確認済**ゆえ正常✓。年→月切替の
    # 裏付けのみ未確定である旨をコメントで開示する (旧: 要対応へ降格=発行済みを漏れ扱いする誤り)。
    pairing = P.compare_periods([], [_row("年→月社", "月額", "MATCH_MONTHLY")])
    rows = P.classify_period_transition(
        pairing, lookback={"年→月社": [{"month": "2506", "annual": True, "product": "月額"}]},
        target_month="2606", fidelity={"exit_code": 3, "overall": "lookback_partial"})
    assert rows[0]["gap_check"] == "正常"
    assert "部分欠損" in rows[0]["comment"]


def test_new_match_annual_verdict_is_dispositive_without_lookback():
    # C3: 今月 verdict=MATCH_ANNUAL (年一括発行) の新規行は reconcile が既に正常判定済みゆえ、
    # 12ヶ月ルックバックの裏付けが無くても要確認へ倒さず即正常 (症状=『100億ThinkTank利用料』等)。
    curr = [_row("新規年契約社", "利用料", "MATCH_ANNUAL", evidence_amount=1000000)]
    row = _classify([], curr)[0]
    assert row["gap_check"] == "正常"
    assert row["period_diff"] == "新規/年→月切替"
    assert "MATCH_ANNUAL" in row["comment"]


def test_new_suppress_annual_verdict_is_also_dispositive():
    # C3 同型: SUPPRESS_ANNUAL (年間前払い期間中) が curr_issued (reliable_issued 等) で新規行として
    # 現れても、ANNUAL_NORMAL_VERDICTS の一次源で即正常化する (STOPPED 側③と対称)。
    curr = [{"取引先": "新規年契約社2", "商品": "利用料", "verdict": "SUPPRESS_ANNUAL",
             "現行単価": 500000, "reliable_issued": True}]
    row = _classify([], curr)[0]
    assert row["gap_check"] == "正常"
    assert "SUPPRESS_ANNUAL" in row["comment"]


def test_new_with_12mo_annual_lookback_is_switch():
    # 12ヶ月前 (2606→2506) に年契約一括発行あり → 年→月切替の裏付け。
    curr = [_row("年→月社", "月額", "MATCH_MONTHLY")]
    lookback = {"年→月社": [{"month": "2506", "annual": True},
                          {"month": "2601", "issued": True}]}
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert row["period_diff"] == "新規/年→月切替"
    assert "2506" in row["comment"]
    assert "月額切替" in row["comment"]


def test_new_with_annual_history_other_month():
    # switch_month と一致しない年契約履歴でも二次分岐で年→月切替の可能性を返す。
    curr = [_row("年契約履歴社", "月額", "MATCH_MONTHLY")]
    lookback = [{"customer": "年契約履歴社", "month": "2509", "verdict": "MATCH_ANNUAL"}]
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert "年→月切替" in row["comment"]


# ---------------------------------------------------------------------------
# 状態: 前月あり今月なし (非請求事情 → 発行漏れ候補)
# ---------------------------------------------------------------------------
def test_stopped_annual_suppress_is_normal():
    prev = [_row("年契約社", "年額", "MATCH_ANNUAL", evidence_amount=600000)]
    curr = [_row("年契約社", "年額", "SUPPRESS_ANNUAL")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]
    assert "SUPPRESS_ANNUAL" in row["comment"]


def test_stopped_annual_with_lookback_reinforcement():
    prev = [_row("年契約社", "年額", "MATCH_ANNUAL", evidence_amount=600000)]
    curr = [_row("年契約社", "年額", "SUPPRESS_ANNUAL")]
    lookback = {"年契約社": [{"month": "2512", "annual_lump": True}]}
    row = _classify(prev, curr, lookback=lookback)[0]
    assert row["gap_check"] == "正常"          # 既存判定を上書きしない
    assert "12ヶ月履歴に年契約一括発行あり" in row["comment"]  # 補強のみ


def test_stopped_ended_with_basis_is_normal():
    # 既存 verdict SUPPRESS_ENDED を消費するのみ (自由文再パースなし)。
    prev = [_row("終了社", "月額", "MATCH_MONTHLY")]
    curr = [_row("終了社", "月額", "SUPPRESS_ENDED", end_month="2605")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "契約完了" in row["period_diff"]
    assert "契約終了月=2605" in row["comment"]


def test_stopped_ended_no_basis_is_gap_safety_valve():
    # 安全弁: 構造化列に契約終了月があっても REVIEW_ENDED_NO_BASIS なら抑制せず発行漏れ候補。
    prev = [_row("疑似終了社", "月額", "MATCH_MONTHLY")]
    curr = [_row("疑似終了社", "月額", "REVIEW_ENDED_NO_BASIS", end_month="2605")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "根拠なき終了月" in row["period_diff"]
    assert "2605" in row["comment"]


def test_stopped_ended_no_basis_without_end_month_still_gap():
    prev = [_row("疑似終了社2", "月額", "MATCH_MONTHLY")]
    curr = [_row("疑似終了社2", "月額", "REVIEW_ENDED_NO_BASIS")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "終了根拠なし" in row["comment"]


def test_stopped_trial_completion_is_normal():
    # トライアル完了は canon 前の生商品名を参照 (verdict は GAP でもトライアル信号で正常化)。
    prev = [_row("トライアル社", "利用料", "MATCH_MONTHLY",
                 raw="100億ThinkTankトライアル(利用料)")]
    curr = [_row("トライアル社", "利用料", "GAP",
                 raw="100億ThinkTankトライアル(利用料)")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "トライアル完了" in row["period_diff"]


def test_stopped_gap_candidate_requires_action():
    # 正常事情に該当しない停止 → 発行漏れ候補 (要対応)。
    prev = [_row("漏れ社", "月額", "MATCH_MONTHLY")]
    curr = [_row("漏れ社", "月額", "GAP")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "発行漏れ候補" in row["period_diff"]
    assert row["prev_amount"] == 50000


def test_stopped_when_curr_row_absent():
    # 今月 verdict 行が全く無い (今月なし) 継続契約 → 既定は発行漏れ候補 (要対応)。
    # 保護不変条件: 月払い (prev=MATCH_MONTHLY) の curr=None は「真の漏れ」ゆえ要対応のまま。
    # 年契約 fix (prev=MATCH_ANNUAL 分岐) がこの月払いの真の漏れを誤って正常化しないことを守る。
    prev = [_row("消失社", "月額", "MATCH_MONTHLY")]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "要対応"


# ---------------------------------------------------------------------------
# GAP-C05-ANNUAL-STOPPED: curr=None (年契約の非請求月) 分岐カバレッジ (hard gate)
#   curr=None × prev-verdict 各値 (年契約 MATCH_ANNUAL / 月払い MATCH_MONTHLY / 12ヶ月履歴年契約 /
#   年契約だが prev に年契約 verdict 不在=初年度縁ケース) を網羅し、金子金物型 systemic bug の
#   再発 (全年契約の非請求月が⑥誤爆) を防ぐ。curr-present 変種は既存テストで別途素通り検証済み。
# ---------------------------------------------------------------------------

def test_stopped_annual_curr_absent_is_gap_ok_kaneko_kanamono():
    # 金子金物型: 先月 MATCH_ANNUAL (180万・年契約一括) ・今月行なし (curr=None) → 年契約周期=正常。
    # curr 単独では verdict=None ゆえ⑥誤爆していたのを prev.verdict MATCH_ANNUAL で正常化する。
    prev = [_row("金子金物", "100億ThinkTank利用料", "MATCH_ANNUAL", evidence_amount=1800000)]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]
    assert "先月 verdict MATCH_ANNUAL" in row["comment"]


def test_stopped_annual_curr_absent_via_suppress_annual_prev():
    # 先月 SUPPRESS_ANNUAL でも evidence 金額があれば発行済み扱い → curr=None は年契約周期=正常。
    prev = [_row("年契約社B", "年額", "SUPPRESS_ANNUAL", evidence_amount=600000)]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]


def test_stopped_annual_curr_absent_via_12mo_history():
    # 先月 verdict が年契約でなくても (issued=True の裏付けのみ)、12ヶ月履歴に**同一商品**の年契約
    # 一括があれば年契約周期=正常へ分類する (GAP-C05-ANNUAL-STOPPED (b) 二次トリガー)。
    # データ契約: 年契約履歴レコードは商品 (product) を持つ (round2 残穴1: 商品確定一致のみ抑制)。
    prev = [{"取引先": "履歴年契約社", "商品": "年額", "issued": True, "現行単価": 500000}]
    lookback = {"履歴年契約社": [{"month": "2506", "annual_lump": True, "product": "年額"}]}
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]
    assert "12ヶ月履歴の年契約一括" in row["comment"]


def test_stopped_annual_history_no_product_mixed_customer_not_hidden():
    # round2 残穴1 (adversarial 検出): 履歴レコードに商品が無いと当該商品の年契約性を確認できない。
    # 混在契約顧客 (年契約商品A・商品未記載 + 今月漏れは月次商品B) で、B の真の月次漏れを商品確認
    # できない年契約履歴で誤抑制しない (安全側=漏れを隠さない)。
    prev = [{"取引先": "混在社", "商品": "月次B", "issued": True, "現行単価": 30000}]
    lookback = {"混在社": [{"month": "2506", "annual_lump": True}]}  # product 無し=確認不能
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "要対応"                     # 商品確認できない年契約で隠さない


def test_stopped_no_product_row_falls_back_to_customer_annual():
    # 漏れ行自体に商品が無いとき (row_product 空) のみ顧客単位 best-effort へ fail-soft する。
    prev = [{"取引先": "商品不明社", "issued": True, "現行単価": 400000}]  # 商品なし
    lookback = {"商品不明社": [{"month": "2506", "annual_lump": True}]}
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"                       # 行に商品が無い→顧客単位 best-effort
    assert "年契約周期" in row["period_diff"]


def test_stopped_monthly_curr_absent_stays_action_not_annual_leak():
    # 分離不変条件: 月払い (prev=MATCH_MONTHLY・年契約シグナルなし) の curr=None は真の漏れ=要対応。
    # 年契約 fix が月払いの curr=None まで正常化しない (⑤隔月への prev.verdict 同型化を排した効果)。
    prev = [_row("月払い漏れ社", "月額", "MATCH_MONTHLY", amount=50000)]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "要対応"
    assert "発行漏れ候補" in row["period_diff"]


def test_stopped_annual_first_year_no_prev_verdict_is_action_edge_case():
    # 縁ケース (plan 明記): 年間契約でも reconcile が MATCH_ANNUAL を未 emit (初年度/verdict 欠落) かつ
    # 12ヶ月履歴なしだと、(a) prev.verdict も (b) 履歴も外れ・(c) DB1 支払サイクルは未配線ゆえ
    # 抑制できず要対応へ落ちる (安全側=漏れを隠さない)。DB1 支払サイクル OR 配線は将来の補強点。
    prev = [_row("初年度年契約社", "年額", "MATCH_MONTHLY", amount=300000)]  # 年契約だが verdict は月次相当
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "要対応"   # 安全側 (over-report)。DB1 配線で将来是正可能。


def test_stopped_annual_curr_present_still_wins_over_prev_inference():
    # curr が実 verdict を持つときは curr を優先 (prev 推定に落ちない)。年契約 prev + 今月 SUPPRESS_ENDED
    # (契約完了) は①契約完了が先に発火する (curr 情報 > prev 推定)。
    prev = [_row("年→終了社", "年額", "MATCH_ANNUAL", evidence_amount=600000)]
    curr = [_row("年→終了社", "年額", "SUPPRESS_ENDED", end_month="2605")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "契約完了" in row["period_diff"]   # ③年契約でなく①契約完了 (curr 優先)


def test_stopped_ended_final_curr_absent_is_gap_ok():
    # ①契約完了の curr=None 変種 (plan hard-gate・elegant-review F2): 先月 MATCH_ENDED_FINAL=最終
    # 請求済・今月行なし → 契約終了後の非請求月=正常。MATCH_ENDED_FINAL は識別的ゆえ誤爆を回避できる。
    prev = [_row("最終請求社", "月額", "MATCH_ENDED_FINAL", amount=50000, end_month="2605")]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "正常"
    assert "契約完了" in row["period_diff"]
    assert "MATCH_ENDED_FINAL" in row["comment"] and "契約終了月=2605" in row["comment"]


# --- elegant-review F1 是正: 年→月切替後の真の月次漏れを旧年契約履歴で隠さない (leak 封鎖) ---

def test_stopped_yearmonth_switch_monthly_gap_not_hidden_by_annual_history():
    # 年→月切替済み顧客: 12ヶ月前に年契約一括履歴があるが prev=MATCH_MONTHLY (今は月次)。
    # 今月 curr=None は真の月次漏れ。(b) 履歴トリガーは prev に月次 verdict があると発火しない
    # (prev.verdict=MATCH_MONTHLY で年→月切替後と判る)。旧年契約履歴で正常化してはならない。
    prev = [_row("年→月切替社", "月額", "MATCH_MONTHLY", amount=50000)]
    lookback = {"年→月切替社": [{"month": "2506", "annual_lump": True, "product": "月額"}]}
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "要対応"                     # 真の漏れを隠さない (false-negative 封鎖)
    assert "発行漏れ候補" in row["period_diff"]


def test_stopped_annual_history_wrong_product_not_hidden():
    # 混在契約: 年契約は商品A、今月漏れは商品B (prev verdict なし)。A の年契約履歴で B を誤抑制
    # しない (商品越境防止=_customer_is_annual_in_lookback の product 突合)。
    prev = [{"取引先": "混在社", "商品": "月次B", "issued": True, "現行単価": 30000}]
    lookback = {"混在社": [{"month": "2506", "annual_lump": True, "product": "年契約A"}]}
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "要対応"                     # 別商品の年契約で隠さない


def test_stopped_annual_history_same_product_still_normal():
    # 対称: 同一商品の年契約履歴なら (prev verdict なし・curr=None) は年契約周期=正常のまま。
    prev = [{"取引先": "同商品社", "商品": "年額P", "issued": True, "現行単価": 600000}]
    lookback = {"同商品社": [{"month": "2506", "annual_lump": True, "product": "年額P"}]}
    row = _classify(prev, [], lookback=lookback, target="2606")[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]


def test_stopped_offmonth_suppress_is_normal_not_leak():
    # SUPPRESS_OFFMONTH (隔月/分割の対象外月・契約開始前) は verdict-mapping SSOT で
    # SUPPRESS_*→対象外。C03 は再判定せず正常(対象外)扱いにする (偽陽性の漏れ扱いを防ぐ)。
    prev = [_row("隔月社", "隔月保守", "MATCH_MONTHLY")]
    curr = [_row("隔月社", "隔月保守", "SUPPRESS_OFFMONTH")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "対象外" in row["period_diff"]
    assert "SUPPRESS_OFFMONTH" in row["comment"]


def test_stopped_oneshot_suppress_is_normal_not_leak():
    # SUPPRESS_ONESHOT (単発発行済・当月対象外) も対象外=正常。
    prev = [_row("単発社", "初期費用", "MATCH_MONTHLY")]
    curr = [_row("単発社", "初期費用", "SUPPRESS_ONESHOT")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "単発発行済" in row["comment"]


def test_contract_end_file_lookup_for_ended():
    # 契約終了月は行に無くても contract_end データ (二次情報) から解決する。
    prev = [_row("終了社X", "月額", "MATCH_MONTHLY")]
    curr = [_row("終了社X", "月額", "SUPPRESS_ENDED")]
    contract_end = {"records": [
        {"取引先": "終了社X", "商品": "月額", "end_month": "2604"}]}
    row = _classify(prev, curr, contract_end=contract_end)[0]
    assert "契約終了月=2604" in row["comment"]


def test_contract_end_customer_map_form():
    # {customer: end_month} 形の contract_end も受ける (商品空キー)。
    ce = P._index_contract_end({"顧客A": "2603"})
    assert ce[(P.R.normalize("顧客A"), P.R.normalize(""))] == "2603"


# ---------------------------------------------------------------------------
# 突合キー: contract_id disambiguation
# ---------------------------------------------------------------------------
def test_contract_id_disambiguation_same_customer_product():
    # 同一取引先×同一商品で 2 契約 → contract_id で別扱い。片方継続・片方停止。
    prev = [_row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C1"),
            _row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C2")]
    curr = [_row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C1"),
            _row("複数契約社", "月額", "GAP", contract_id="C2")]
    report = _by_customer(_classify(prev, curr), "複数契約社")
    by_cid = {r["contract_id"]: r for r in report}
    assert by_cid["C1"]["period_diff"] == "継続発行"
    assert by_cid["C2"]["gap_check"] == "要対応"


def test_agency_end_client_disambiguation_prevents_silent_collapse():
    # C5: 代理店が同一商品を複数エンドクライアント (contract_id 未設定) に契約するとき、
    # エンドクライアント名で分離しないと (取引先,商品) の setdefault で 1 件のみ残り、他方の
    # 状態変化 (停止) が完全に隠蔽される (HOSONO 型)。エンドクライアント名で分離すれば個別に
    # 正しく突合される (継続 1 件・発行漏れ候補 1 件)。
    prev = [
        {"取引先": "代理店社", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 30000, "エンドクライアント名": "A様"},
        {"取引先": "代理店社", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 50000, "エンドクライアント名": "B様"},
    ]
    curr = [
        {"取引先": "代理店社", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 30000, "エンドクライアント名": "A様"},
        # B様は今月停止 (curr行なし)。
    ]
    report = _by_customer(_classify(prev, curr), "代理店社")
    assert len(report) == 2
    diffs = {r["period_diff"] for r in report}
    assert "継続発行" in diffs
    assert any("発行漏れ候補" in d for d in diffs)  # B様の停止が可視化される (隠蔽されない)


def test_agency_end_client_key_stable_despite_inconsistent_contract_id():
    # C5: contract_id が今月だけ付与される等の不整合があっても、エンドクライアント名で突合キーが
    # 安定するため両エンドクライアントとも正しく継続発行になる (contract_id 不整合由来の
    # 幻の NEW+STOPPED を防ぐ)。
    prev = [
        {"取引先": "代理店社2", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 30000, "エンドクライアント名": "A様"},
        {"取引先": "代理店社2", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 50000, "エンドクライアント名": "B様"},
    ]
    curr = [
        {"取引先": "代理店社2", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 30000, "エンドクライアント名": "A様", "契約ID": "C-A"},
        {"取引先": "代理店社2", "商品": "業務委託費", "verdict": "MATCH_MONTHLY",
         "現行単価": 50000, "エンドクライアント名": "B様", "契約ID": "C-B"},
    ]
    report = _by_customer(_classify(prev, curr), "代理店社2")
    assert len(report) == 2
    assert all(r["period_diff"] == "継続発行" for r in report)


def test_no_disambiguation_when_single_contract():
    # 単一 contract_id なら取引先×商品のみで突合 (片側に契約ID欠落でも対応付く)。
    prev = [_row("単一社", "月額", "MATCH_MONTHLY", contract_id="C9")]
    curr = [_row("単一社", "月額", "MATCH_MONTHLY")]  # contract_id 欠落
    report = _by_customer(_classify(prev, curr), "単一社")
    assert len(report) == 1
    assert report[0]["period_diff"] == "継続発行"


# ---------------------------------------------------------------------------
# フィールド抽出ヘルパ
# ---------------------------------------------------------------------------
def test_customer_fallback_via_extract_names():
    # customer/取引先 が空でも確認内容から extract_names で取引先を拾う。
    row = {"商品": "月額", "verdict": "GAP", "確認内容": "株式会社テスト の件"}
    assert "テスト" in P._customer(row)


def test_amount_and_int_coercion():
    assert P._to_int("50,000") == 50000
    assert P._to_int(None) is None
    assert P._to_int("x") is None
    assert P._amount_of({"現行単価": "12,000"}) == 12000
    assert P._amount_of({"evidence": {"amount": 900}}) == 900
    assert P._amount_of({}) is None


def test_amount_of_blocks_expected_fallback_for_supply_none():
    # 未発行 (GAP・supply_state=none) は期待額 fallback せず金額列を空にする
    # (ユーザー確定2026-07-10: 「金額あり=発行済み」の直感を崩さない・K3 の GAP 拡張)。
    row = {"actual_amount": None, "supply_state": "none", "現行単価": "50,000"}
    assert P._amount_of(row) is None


def test_amount_of_blocks_expected_fallback_for_inactive_supply():
    row = {"actual_amount": None, "supply_state": "inactive_canceled", "現行単価": "50,000"}
    assert P._amount_of(row) is None


def test_lookback_index_forms():
    # dict(customer→list) / dict(records) / list の 3 形を吸収する。
    a = P._index_lookback({"社": [{"month": "2501"}]})
    b = P._index_lookback({"records": [{"customer": "社", "month": "2501"}]})
    c = P._index_lookback([{"customer": "社", "month": "2501"}])
    key = P.R.normalize("社")
    assert a[key] and b[key] and c[key]
    assert P._index_lookback(None) == {}


# ---------------------------------------------------------------------------
# CLI (main) — I/O + exit code
# ---------------------------------------------------------------------------
def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _fidelity(tmp_path, exit_code=0, overall="ok", name="fid.json"):
    """C06 fetch fidelity report の最小 fixture を書いて path を返す (--fidelity-report は必須入力)。"""
    return _write(tmp_path, name, {"target_month": "2606", "exit_code": exit_code,
                                   "overall": overall, "lookback": {"ng_months": []}})


def test_main_happy_path_exit0(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json",
                  [_row("継続社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json",
                  {"target_month": "2606",
                   "rows": [_row("継続社", "月額", "MATCH_MONTHLY")]})
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--fidelity-report", _fidelity(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["customer"] == "継続社"
    assert out[0]["target_month"] == "2606"


def test_main_gap_returns_exit1(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json", [_row("漏れ社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json", [_row("漏れ社", "月額", "GAP")])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--target-month", "2606", "--fidelity-report", _fidelity(tmp_path)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out[0]["gap_check"] == "要対応"


def test_main_with_lookback_and_contract_end_files(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json", [_row("年契約社", "年額", "MATCH_ANNUAL",
                                               evidence_amount=600000)])
    curr = _write(tmp_path, "curr.json", [_row("年契約社", "年額", "SUPPRESS_ANNUAL")])
    lb = _write(tmp_path, "lb.json", {"年契約社": [{"month": "2512", "annual": True}]})
    ce = _write(tmp_path, "ce.json", {"records": []})
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--lookback-12mo", lb, "--contract-end", ce, "--target-month", "2606",
                 "--fidelity-report", _fidelity(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "年契約周期" in out[0]["period_diff"]


def test_main_empty_lookback_file_still_warns_unverified(tmp_path, capsys):
    """空の --lookback-12mo ファイルでも『実質未実行』として stderr 警告する (縁ケース)。

    パスは指定されているが中身が空=12ヶ月履歴なし。前月なし今月あり (新規) 行の年→月切替
    裏付けは未確認なので、未指定時と同様に警告を出す (loaded content の真偽で判定)。
    """
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [_row("新規社", "月額", "MATCH_MONTHLY")])
    empty_lb = _write(tmp_path, "lb.json", [])   # 空ファイル (パスは指定・中身は空)
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--lookback-12mo", empty_lb, "--target-month", "2606",
                 "--fidelity-report", _fidelity(tmp_path)])
    # 新不変則: 空 lookback でも新規は今月実発行あり=正常✓ (漏れではない) ゆえ rc=0。
    # 年→月切替の裏付け未確認は checkbox を倒さないが stderr 警告での開示は維持する。
    assert rc == 0
    err = capsys.readouterr().err
    assert "12ヶ月履歴データなし" in err and "未確認" in err   # 空でも警告発火 (開示は維持)


def test_main_missing_file_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    rc = P.main(["--curr-verdicts", str(tmp_path / "nope.json"),
                 "--prev-verdicts", prev, "--fidelity-report", _fidelity(tmp_path)])
    assert rc == 2


def test_main_bad_lookback_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--fidelity-report", _fidelity(tmp_path),
                 "--lookback-12mo", str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_bad_contract_end_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--fidelity-report", _fidelity(tmp_path),
                 "--contract-end", str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_fidelity_curr_fail_is_fail_closed(tmp_path, capsys):
    # C06 exit1 (当月/先月 fetch fidelity 違反) は漏れ確認レポートを emit せず fail-closed (rc=1)。
    prev = _write(tmp_path, "prev.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    fid = _fidelity(tmp_path, exit_code=1, overall="curr_fail")
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--target-month", "2606", "--fidelity-report", fid])
    assert rc == 1
    cap = capsys.readouterr()
    assert cap.out.strip() == ""            # 非 emit (レポートを出さない)
    assert "fail-closed" in cap.err


def test_main_bad_fidelity_report_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--fidelity-report", str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_default_target_when_absent(tmp_path, capsys):
    # target 指定も file の target_month も無いとき resolve_target_months で導出する。
    prev = _write(tmp_path, "prev.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--fidelity-report", _fidelity(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out[0]["target_month"]) == 4  # YYMM 導出


def test_rows_of_accepts_list_and_dict():
    assert P._rows_of([{"a": 1}, "skip"]) == [{"a": 1}]
    assert P._rows_of({"verdicts": [{"b": 2}]}) == [{"b": 2}]
    assert P._rows_of(123) == []


# ---------------------------------------------------------------------------
# F-1: 継続漏れ (両月未発行だが今月 GAP) を要対応として emit・対象外は非 emit を維持
# ---------------------------------------------------------------------------

def test_continuing_gap_emitted_as_action():
    # 前月も今月も未発行だが今月 verdict=GAP の継続漏れは要対応として残す (脱落させない)。
    rows = P.build_report(
        [_row("継続漏れ社", "月額", "GAP")],
        [_row("継続漏れ社", "月額", "GAP")], target_month="2606")
    assert len(rows) == 1
    assert rows[0]["gap_check"] == "要対応"
    assert rows[0]["customer"] == "継続漏れ社"
    assert "継続" in rows[0]["period_diff"]


def test_originally_unbilled_and_suppressed_still_dropped():
    # F-1 の裏: SUPPRESS_* の両月未発行は対象外=非 emit を維持 (過剰報告しない)。
    suppressed = P.build_report(
        [_row("隔月社", "月額", "SUPPRESS_OFFMONTH")],
        [_row("隔月社", "月額", "SUPPRESS_OFFMONTH")], target_month="2606")
    assert suppressed == []
    # curr に行が無い (元々請求なし/当月の発行期待なし) も非 emit。
    prev_only = P.build_report([], [_row("退会社", "月額", "GAP")], target_month="2606")
    assert prev_only == []


def test_orphan_master_registration_is_normal_check():
    # 要件3(2026-07-10): MF実績あり×シート契約なし=要マスタ登録 は正常✓ (GAP_ACTION でなく GAP_OK)。
    # 発行自体は正常 (MF実績あり) ゆえ漏れチェックは正常、登録方法はコメントに保持し、契約なしを漏れ扱いしない。
    curr = {"rows": [], "orphans": [
        {"customer": "オーファン商事", "product": "月額サービス", "actual_amount": 88000}]}
    rows = P.build_report(curr, [], target_month="2606")
    orphan = [r for r in rows if r["period_diff"] == "要マスタ登録"]
    assert len(orphan) == 1
    assert orphan[0]["gap_check"] == "正常"              # 漏れチェック=正常✓ (要対応でない)
    assert orphan[0]["customer"] == "オーファン商事"
    assert orphan[0]["amount"] == 88000                  # MF実績額を保持
    assert "要マスタ登録" in orphan[0]["comment"]         # 名寄せ登録の action をコメントで保持
    assert orphan[0]["reliable_issued"] is True


# ---------------------------------------------------------------------------
# 要因A/B/C (2026-07-10 ユーザー確定): 月跨ぎ ID 突合 / 年契約開始✓ / 長期未発行 surface
# ---------------------------------------------------------------------------
def _issued(customer, product, cid=None, cycle=None, status=None,
            amount=50000, verdict="MATCH_MONTHLY"):
    r = {"取引先": customer, "商品": product, "verdict": verdict,
         "reliable_issued": True, "actual_amount": amount, "supply_state": "active"}
    if cid is not None:
        r["MF顧客ID"] = cid
    if cycle is not None:
        r["支払サイクル"] = cycle
    if status is not None:
        r["ステータス"] = status
    return r


def _not_issued(customer, product, cid=None, cycle=None, status=None, verdict="GAP"):
    r = {"取引先": customer, "商品": product, "verdict": verdict,
         "reliable_issued": False, "supply_state": "none"}
    if cid is not None:
        r["MF顧客ID"] = cid
    if cycle is not None:
        r["支払サイクル"] = cycle
    if status is not None:
        r["ステータス"] = status
    return r


# --- 要因A: 月跨ぎ突合を MF顧客ID 第一キーにする ---
def test_A_matches_by_customer_id_across_name_drift():
    prev = [_issued("アルファ合同会社", "利用料", cid="cust-XYZ")]
    curr = [_issued("アルファ合同会社(旧アルファ)", "利用料", cid="cust-XYZ")]
    pairing = P.compare_periods(prev, curr)
    assert len(pairing) == 1
    assert pairing[0]["state"] == P.STATE_CONTINUED


def test_A_name_drift_without_id_still_splits():
    prev = [_issued("アルファ合同会社", "利用料")]
    curr = [_issued("アルファ合同会社(旧アルファ)", "利用料")]
    assert len(P.compare_periods(prev, curr)) == 2


def test_A_id_bridge_inherits_when_one_month_lacks_explicit_id():
    prev = [_issued("ベータ商事", "保守", cid="cust-B")]
    curr = [_issued("ベータ商事", "保守")]
    pairing = P.compare_periods(prev, curr)
    assert len(pairing) == 1
    assert pairing[0]["state"] == P.STATE_CONTINUED


def test_A_different_customer_ids_do_not_merge():
    prev = [_issued("同名社", "月額", cid="cust-1")]
    curr = [_issued("同名社", "月額", cid="cust-2")]
    assert len(P.compare_periods(prev, curr)) == 2


# --- 要因B: 新規年契約開始 (支払サイクル年契約系) は 12ヶ月履歴なしでも正常✓ ---
def test_B_new_annual_cycle_start_is_normal():
    curr = [_issued("ガンマ", "年間ライセンス", cid="c-g", cycle="年間払い",
                    amount=1200000, verdict=None)]
    rows = _classify([], curr)
    assert len(rows) == 1
    assert rows[0]["gap_check"] == "正常"
    assert "年契約開始" in rows[0]["comment"]


def test_B_new_annual_renewal_cycle_is_normal():
    curr = [_issued("シータ", "更新ライセンス", cid="c-t", cycle="年間一括更新",
                    amount=900000, verdict=None)]
    assert _classify([], curr)[0]["gap_check"] == "正常"


def test_B_new_monthly_without_backing_is_normal_issued_this_month():
    # 新不変則: 月払いの新規契約でも**今月に実発行あり**なら正常✓ (発行漏れは今月未発行に限る)。
    # 旧挙動 (裏付けなし月払い新規=要対応) は『発行の存在』と『内容の未確認』の混同だった。
    curr = [_issued("デルタ", "保守月額", cid="c-d", cycle="月払い",
                    amount=50000, verdict=None)]
    assert _classify([], curr)[0]["gap_check"] == "正常"


# --- 要因C: 先月も今月も未発行の月払いアクティブ契約 (完了未確認) を要対応 surface ---
def test_C_both_absent_active_monthly_surfaced_as_action():
    prev = [_not_issued("イプシロン", "保守月額", cid="c-e", cycle="月払い", status="有効")]
    rows = _classify(prev, [])
    assert len(rows) == 1
    assert rows[0]["gap_check"] == "要対応"
    assert "継続" in rows[0]["period_diff"]
    assert "契約完了の確認が取れず" in rows[0]["comment"]


def test_C_both_absent_completed_verdict_not_emitted():
    prev = [_not_issued("ゼータ", "保守月額", cid="c-z", cycle="月払い", verdict="SUPPRESS_ENDED")]
    assert _classify(prev, []) == []


def test_C_both_absent_status_ended_not_emitted():
    prev = [_not_issued("イオタ", "保守月額", cid="c-i", cycle="月払い", status="終了")]
    assert _classify(prev, []) == []


def test_C_both_absent_annual_cycle_not_emitted():
    prev = [_not_issued("イータ", "年間ライセンス", cid="c-h", cycle="年間払い")]
    assert _classify(prev, []) == []


def test_C_both_absent_non_monthly_cycle_not_surfaced():
    assert _classify([_not_issued("カッパ", "従量課金", cid="c-k", cycle="従量")], []) == []
    assert _classify([_not_issued("ラムダ", "保留商品", cid="c-l")], []) == []


def test_C_both_absent_review_pending_not_surfaced():
    prev = [_not_issued("ミュー", "保守月額", cid="c-m", cycle="月払い", verdict="REVIEW_PENDING")]
    assert _classify(prev, []) == []
