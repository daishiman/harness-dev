#!/usr/bin/env python3
"""scripts/mfk_actuals.py (C05: MF実績を取引先×商品粒度で抽出する SSOT) の単体テスト。

オフライン・fixture はテスト内 dict で自己完結 (network/ファイル不要)。
検証観点 (component-inventory C05 の criteria 由来):
  - resolve_actual: active 供給 → issued/actual_amount(実発行額)、inactive → issued=False/actual_amount=None
    (取消前額を昇格させない=K3 偽陰性隔離)、no_supply → supply_state=none。
  - amount_mismatch (evidence=None・active 供給ありで金額不一致) の actual_amount 代表選定
    (category 一致優先 → 最大 amount)。
  - build_actuals_index: build_mf_index の active/inactive 分別を写像する。
"""
import mfk_actuals as A


def _svc(amount, category=None, desc="x"):
    return {"amount": amount, "category": category, "desc": desc}


def _inactive(amount, status="canceled", canceled_at="2026-06-10", desc="x"):
    return {"amount": amount, "status": status, "canceled_at": canceled_at, "desc": desc}


# ---------------------------------------------------------------------------
# resolve_actual: active 供給 → issued/実額
# ---------------------------------------------------------------------------
def test_active_match_uses_evidence_amount():
    # match/typo は一致明細 (evidence.amount) を実額に採る。
    a = A.resolve_actual([("acme", _svc(55000))], [], status="match",
                         evidence={"cust": "acme", "amount": 55000})
    assert a == {"issued": True, "actual_amount": 55000, "supply_state": "active",
                 "canceled_at": None, "category_confirmed": True}


def test_amount_mismatch_uses_representative_not_expected():
    # amount_mismatch は evidence=None。actual_amount は scoped_candidates の代表 (最大 amount) を採る。
    a = A.resolve_actual([("acme", _svc(30000)), ("acme", _svc(55000))], [],
                         status="amount_mismatch", evidence=None)
    assert a["issued"] is True
    assert a["actual_amount"] == 55000     # 最大 amount を実発行額の代表に
    assert a["supply_state"] == "active"


def test_amount_mismatch_category_priority():
    # 複数候補時は category 一致を優先し、その中で最大 amount を採る。
    cands = [("acme", _svc(90000, category="other")),
             ("acme", _svc(40000, category="riyo")),
             ("acme", _svc(50000, category="riyo"))]
    a = A.resolve_actual(cands, [], status="amount_mismatch", evidence=None,
                         expected_cats={"riyo"})
    assert a["actual_amount"] == 50000     # category=riyo の中の最大 (90000 の other は除外)


# ---------------------------------------------------------------------------
# resolve_actual: inactive → 取消前額を昇格させない (K3)
# ---------------------------------------------------------------------------
def test_inactive_canceled_not_issued_and_no_amount():
    rep = _inactive(40000, status="canceled", canceled_at="2026-06-10")
    a = A.resolve_actual([], [("beta", rep)], status="inactive_only", evidence={"cust": "beta", **rep})
    assert a["issued"] is False
    assert a["actual_amount"] is None            # 取消前額を実額へ昇格させない (K3)
    assert a["supply_state"] == "inactive_canceled"
    assert a["canceled_at"] == "2026-06-10"


def test_inactive_pending_non_canceled():
    rep = _inactive(12000, status="pending", canceled_at=None)
    a = A.resolve_actual([], [("beta", rep)], status="inactive_only", evidence={"cust": "beta", **rep})
    assert a["issued"] is False
    assert a["actual_amount"] is None
    assert a["supply_state"] == "inactive_pending"


def test_no_supply_is_none_state():
    a = A.resolve_actual([], [], status="no_supply", evidence=None)
    assert a == {"issued": False, "actual_amount": None,
                 "supply_state": "none", "canceled_at": None}


def test_cross_client_is_not_issued_in_boundary():
    # cross_client は自境界に active/inactive 供給なし → none (別会社の証跡は本行の実額ではない)。
    a = A.resolve_actual([], [], status="cross_client", evidence=None)
    assert a["issued"] is False and a["supply_state"] == "none"


def test_zero_and_negative_amounts_excluded_from_actual():
    # 0円/負額は実額に採らない (representative が None を返す)。
    a = A.resolve_actual([("acme", _svc(0)), ("acme", _svc(-100))], [],
                         status="amount_mismatch", evidence=None)
    assert a["issued"] is True                   # active 供給の存在自体は issued
    assert a["actual_amount"] is None            # ただし正の実額は無い


# ---------------------------------------------------------------------------
# build_actuals_index: build_mf_index 分別の写像
# ---------------------------------------------------------------------------
def test_build_actuals_index_maps_active_and_inactive():
    mf_index = {
        "c1": {"cust": "アクメ商事",
               "services": [_svc(55000, desc="コンサル")],
               "inactive": [_inactive(40000, status="canceled", desc="保守")]},
    }
    idx = A.build_actuals_index(mf_index)
    actuals = idx["c1"]["actuals"]
    assert idx["c1"]["cust"] == "アクメ商事"
    active = [a for a in actuals if a["supply_state"] == "active"][0]
    assert active["issued"] is True and active["actual_amount"] == 55000
    inact = [a for a in actuals if a["supply_state"] == "inactive_canceled"][0]
    assert inact["issued"] is False and inact["actual_amount"] is None
