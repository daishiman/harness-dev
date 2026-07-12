#!/usr/bin/env python3
# /// script
# name: mfk_actuals
# purpose: MF実績(取引先×商品粒度)の issued/実発行額/供給状態を抽出する純関数 SSOT (amount-gate 根治)。
# inputs:
#   - resolve_actual(): find_mf_match が解決済みの scoped_candidates / scoped_inactive (自力照合しない)
#   - build_actuals_index(): build_mf_index の出力 (取引先×商品の実額一覧)
# outputs:
#   - resolve_actual(): {issued, actual_amount, supply_state, canceled_at}
#   - build_actuals_index(): {customer_id: {cust, actuals:[...]}}
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []   # mfk_reconcile を import しない (循環回避)。境界解決は呼出側が渡す。
# requires-python: ">=3.11"
# ///
"""MF実績を第一級の真実(source of truth)として取引先×商品粒度で抽出する純関数モジュール (C05)。

amount-gate 根治の中核: 既存 find_mf_match / classify (lib/mfk_reconcile.py) が全 status
(match / typo / amount_mismatch / no_supply / inactive_only / cross_client) の verdict 行へ、契約の
期待額ではなく **MF が実際に発行した額 (actual_amount)** と MF実績由来の reliable issued フラグを
焼くために、この module の resolve_actual を consume する (D3=金額列常時表示・症状①③⑥⑦の根治)。

設計上の不変則:
- **循環 import 回避**: 本 module は mfk_reconcile を import せず、呼出側 (find_mf_match) が既に解決した
  scoped_candidates / scoped_inactive (境界・endclient・category スコープ適用済み) を受け取る純関数。
  境界解決・名寄せ (_boundary_customers / _endclient_norms / _scoped_inactive) を再発明しない。
- **canonical carrier は行 top-level の actual_amount 単一**。find_mf_match の evidence:None は据え置く
  (evidence を書き換えると reconcile_invoices.build_sink_rows 経由で別 skill run-mf-invoice-reconcile の
  DB2 matched_amount が REVIEW_AMOUNT_MISMATCH 行で変わり温存境界を割るため)。本 module は evidence を
  一切変更しない (READ もしない)。
- **actual_amount は active 供給に限定**する。inactive (取消/審査中/否決/停止) の amount は取消前額であり
  実発行額ではないため actual_amount へ昇格させず、supply_state で判別可能にする (取消明細を issued 化して
  漏れ隠蔽を再生産しない = K3 偽陰性隔離)。
"""

# 供給状態の語彙 (SSOT)。_amount_of / _is_issued (mfk_period_report.py) が evidence.amount fallback を
# active に限定する際にこの値を参照する。
SUPPLY_ACTIVE = "active"
SUPPLY_INACTIVE_CANCELED = "inactive_canceled"
SUPPLY_INACTIVE_PENDING = "inactive_pending"
SUPPLY_NONE = "none"

# supply_state が「有効供給あり=当月に実発行された」と判定される値集合。
ISSUED_SUPPLY_STATES = frozenset({SUPPLY_ACTIVE})


def _positive_int(v):
    """v が正の整数なら返し、そうでなければ None (0円・負額・None・非数を実額から排除)。"""
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def _representative_amount(scoped_candidates, expected_cats=None):
    """active scoped_candidates から代表実額を選ぶ (category 一致優先 → 最大 amount)。

    amount_mismatch (evidence=None・名寄せ供給ありで金額のみ不一致) の actual_amount 代表選定契約:
    複数候補があるときは category 一致を優先し、その中で最大 amount を実発行額の代表とする。
    find_mf_match は expected_cats がある経路では scoped_candidates を既に category で絞るが、
    presence / annual 経路は絞り方が異なるためここでも冪等に category 一致を優先してから最大額を採る。
    """
    svcs = [svc for _cust, svc in scoped_candidates if isinstance(svc, dict)]
    if not svcs:
        return None
    if expected_cats:
        cat_match = [s for s in svcs if s.get("category") in expected_cats]
        if cat_match:
            svcs = cat_match
    amounts = [a for a in (_positive_int(s.get("amount")) for s in svcs) if a is not None]
    return max(amounts) if amounts else None


def resolve_actual(scoped_candidates, scoped_inactive, status=None, evidence=None,
                   expected_cats=None, category_confirmed=True):
    """MF実績 (実発行額 / issued / 供給状態) を verdict 行 top-level へ焼くための dict を返す。

    返り値: {"issued": bool, "actual_amount": int|None, "supply_state": str, "canceled_at": str|None,
             "category_confirmed": bool}

    category_confirmed (安全弁・2026-07-10): scoped_candidates が期待 category の確定一致か
    (True) / find_mf_match の category-agnostic fallback (期待 category 一致ゼロで境界内全 active 供給へ
    退避) で得た非確定一致か (False)。False の active 供給は「別 category/商品の供給を当該契約の発行と
    取り違えている可能性」があり、reliable_issued を**権威ある正常訂正 (要対応☐の上書き)** に使うと真の
    月次漏れを隠す (system-strategic 検証 HIGH)。issued 自体は据え置き (false-GAP 過剰報告を防ぐ既存の
    presence 寛容さを保つ) が、category_confirmed=False を carrier へ透過して消費側 (_row_reliable_mf_issued)
    が権威判定から除外できるようにする。expected_cats が無い契約は category 制約が無い=presence 権威ゆえ
    呼出側が True を渡す。

    引数はいずれも find_mf_match が解決済みのもの (本 module は再照合しない):
      scoped_candidates : 境界内 active 供給 [(cust, svc)] (endclient/category スコープ済み)
      scoped_inactive   : 境界内 inactive 供給 [(cust, svc)] (取消/審査中等・同一スコープ)
      status / evidence : find_mf_match の返り status と一致明細 (match/typo は実額既知)
      expected_cats     : 期待 category 集合 (amount_mismatch 代表の category 一致優先に使う)

    優先順位 (MF実績 > 契約期待額):
      1. active scoped_candidates あり → issued=True・supply_state=active。actual_amount は
         match/typo の一致明細 (evidence.amount) を最優先し、無ければ (amount_mismatch 等) 代表
         (category 一致優先 → 最大額) を採る。いずれも MF が実際に発行した額であり期待額ではない。
      2. active 皆無 かつ scoped_inactive あり → issued=False・actual_amount=None (取消前額を昇格させない)。
         代表 inactive の status で supply_state を inactive_canceled / inactive_pending へ出し分け・canceled_at 保持。
      3. どちらも皆無 → issued=False・actual_amount=None・supply_state=none (no_supply / cross_client)。
    """
    scoped_candidates = scoped_candidates or []
    scoped_inactive = scoped_inactive or []
    if scoped_candidates:
        amt = None
        if isinstance(evidence, dict):
            amt = _positive_int(evidence.get("amount"))
        if amt is None:
            amt = _representative_amount(scoped_candidates, expected_cats)
        return {"issued": True, "actual_amount": amt,
                "supply_state": SUPPLY_ACTIVE, "canceled_at": None,
                "category_confirmed": bool(category_confirmed)}
    if scoped_inactive:
        # 代表 inactive 明細を選ぶ。呼出側 (inactive_only) が evidence に確定した代表 (status 付き)
        # を渡していればそれを使い、verdict (REVIEW_CANCELED / REVIEW_TXN_NOT_PASSED) と supply_state /
        # canceled_at を厳密一致させる (active 明細は build_mf_index で status キーを持たないため、
        # evidence.status の有無が active/inactive の確実な弁別子)。無ければ最大額 inactive を代表にする。
        if isinstance(evidence, dict) and evidence.get("status") is not None:
            rep = evidence
        else:
            _cust, rep = max(scoped_inactive, key=lambda cc: (cc[1].get("amount") or 0))
        st = (rep.get("status") or "").lower()
        supply_state = SUPPLY_INACTIVE_CANCELED if st == "canceled" else SUPPLY_INACTIVE_PENDING
        return {"issued": False, "actual_amount": None,
                "supply_state": supply_state, "canceled_at": rep.get("canceled_at")}
    return {"issued": False, "actual_amount": None,
            "supply_state": SUPPLY_NONE, "canceled_at": None}


def build_actuals_index(mf_index):
    """build_mf_index の出力から 取引先×商品(desc) 粒度の MF実績一覧を組む (R1 直列化 / doctor 用の純関数)。

    返り値: {customer_id: {"cust": str, "actuals": [
        {"desc", "category", "actual_amount", "issued", "supply_state", "canceled_at"}...]}}。
    active 明細は issued=True・actual_amount=実額、inactive 明細は issued=False・actual_amount=None
    (取消前額を昇格させない)。build_mf_index が既に active / inactive を分別済みなので写像するのみ
    (再照合しない)。当月/先月それぞれの mf_index を渡して curr/prev の実額一覧を得る。
    """
    out = {}
    for cid, c in (mf_index or {}).items():
        actuals = []
        for svc in c.get("services", []):
            actuals.append({
                "desc": svc.get("desc"), "category": svc.get("category"),
                "actual_amount": _positive_int(svc.get("amount")),
                "issued": True, "supply_state": SUPPLY_ACTIVE, "canceled_at": None,
            })
        for svc in c.get("inactive", []):
            st = (svc.get("status") or "").lower()
            actuals.append({
                "desc": svc.get("desc"), "category": svc.get("category"),
                "actual_amount": None, "issued": False,
                "supply_state": (SUPPLY_INACTIVE_CANCELED if st == "canceled"
                                 else SUPPLY_INACTIVE_PENDING),
                "canceled_at": svc.get("canceled_at"),
            })
        out[cid] = {"cust": c.get("cust"), "actuals": actuals}
    return out
