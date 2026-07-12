#!/usr/bin/env python3
"""scripts/mfk_fetch_audit.py (C06: fetch fidelity 監査器・network=false) の単体テスト。

オフライン・fixture はテスト内 dict で自己完結。
検証観点 (component-inventory C06 / goal-spec C2 由来):
  - pagination 完全性 (has_next↔end 整合・終端)。
  - total 件数突合 (Σitems_count == pagination.total)。
  - issue_date 範囲 / stale (billings の issue_date_from が対象月の当月初と一致)。
  - trace 完全不在 = fidelity violation (legacy 非trace経路を通さない)。
  - exit: 0=OK / 1=当月or先月 NG (fail-closed) / 3=lookback 部分欠損 (要確認降格)。
"""
import mfk_fetch_audit as F


def _page(site="billings", has_next=False, end=None, total=1, items=1, ym="2606"):
    year = 2000 + int(ym[:2])
    month = int(ym[2:])
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return {"site": site, "path": f"/{site}", "page_index": 0,
            "has_next": has_next, "end": end, "total": total, "items_count": items,
            "params": {"issue_date_from": f"{year:04d}-{month:02d}-01",
                       # over-fetch 上限は翌月末 (取引日基準の当月分は翌月発行のため)。
                       "issue_date_to": f"{ny:04d}-{nm:02d}-{28 if nm == 2 else 30}",
                       "status": "invoice_issued"}}


def _ok_trace():
    return {"target_month": "2606",
            "curr": [_page(ym="2606")],
            "prev": [_page(ym="2605")],
            "lookback": {"2505": [_page(ym="2505")]}}


def test_all_ok_is_exit0():
    r = F.audit_fetch_trace(_ok_trace())
    assert r["overall"] == "ok" and r["exit_code"] == 0
    assert r["curr"]["ok"] and r["prev"]["ok"]
    assert r["lookback"]["complete"] and not r["lookback"]["partial"]


def test_curr_pagination_ng_is_fail_closed():
    # has_next=true だが end 空 = 部分取得のまま停止 → 当月 NG → exit1。
    t = _ok_trace()
    t["curr"] = [_page(ym="2606", has_next=True, end=None)]
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1 and r["overall"] == "curr_fail"
    assert not r["curr"]["ok"]


def test_curr_total_count_mismatch_is_fail_closed():
    t = _ok_trace()
    t["curr"] = [_page(ym="2606", total=5, items=2)]   # total=5 だが取得 2 件
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1
    assert any("件数不一致" in v for v in r["curr"]["violations"])


def test_curr_stale_issue_date_is_fail_closed():
    # 当月 fetch なのに issue_date_from が別月 = stale → NG。
    t = _ok_trace()
    stale = _page(ym="2606")
    stale["params"]["issue_date_from"] = "2026-05-01"
    t["curr"] = [stale]
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1
    assert any("stale" in v or "不一致" in v for v in r["curr"]["violations"])


def test_prev_ng_is_also_fail_closed():
    # 先月の fidelity 違反も比較の前提が崩れるため fail-closed (exit1)。
    t = _ok_trace()
    t["prev"] = [_page(ym="2605", has_next=True, end=None)]
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1
    assert not r["prev"]["ok"]


def test_lookback_partial_is_exit3():
    # 当月/先月 OK・lookback の 1 月だけ NG → 部分欠損 (exit3・要確認降格)。
    t = _ok_trace()
    t["lookback"] = {"2505": [_page(ym="2505")],
                     "2506": [_page(ym="2506", has_next=True, end=None)]}
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 3 and r["overall"] == "lookback_partial"
    assert r["lookback"]["partial"] and "2506" in r["lookback"]["ng_months"]


def test_trace_absent_is_fidelity_violation():
    # trace 完全不在 (legacy 非trace経路) は fail-closed (exit1)。
    r = F.audit_fetch_trace({"target_month": "2606"})
    assert r["exit_code"] == 1 and r["overall"] == "trace_absent"


def test_curr_terminated_multi_page_ok():
    # 複数ページで最終ページ has_next=false・total 突合 OK なら通る。
    t = _ok_trace()
    p0 = _page(ym="2606", has_next=True, end="cursor1", total=3, items=2)
    p1 = _page(ym="2606", has_next=False, end=None, total=3, items=1)
    t["curr"] = [p0, p1]
    r = F.audit_fetch_trace(t)
    assert r["curr"]["ok"] and r["exit_code"] == 0


def test_cli_exit_code_and_report(tmp_path, capsys):
    import json
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(_ok_trace()), encoding="utf-8")
    rc = F.main(["--fetch-trace", str(p), "--target", "2606"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["exit_code"] == 0


def test_cli_bad_trace_is_exit2(tmp_path):
    rc = F.main(["--fetch-trace", str(tmp_path / "nope.json")])
    assert rc == 2


def test_curr_issue_date_to_truncated_is_fail_closed():
    # over-fetch 上限を当月内へ切り詰めた窓 (issue_date_to が翌月でなく当月) = 翌月発行分取りこぼし → NG。
    t = _ok_trace()
    bad = _page(ym="2606")
    bad["params"]["issue_date_to"] = "2026-06-30"   # 上限を当月末に切詰め (本来は翌月末)
    t["curr"] = [bad]
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1
    assert any("上限" in v or "取りこぼし" in v for v in r["curr"]["violations"])


def test_curr_missing_billings_site_is_fail_closed():
    # transactions だけ trace し billings site を落とした部分 trace は最新性を保証できず fail-closed。
    t = _ok_trace()
    t["curr"] = [_page(site="transactions", ym="2606")]
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 1
    assert any("billings site" in v for v in r["curr"]["violations"])


def test_lookback_missing_declared_month_is_exit3():
    # expected_lookback_months で宣言した月が trace に無い (silent omission) → 部分欠損 (exit3)。
    t = _ok_trace()
    t["expected_lookback_months"] = ["2505", "2504"]   # 2504 は trace に無い
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 3 and r["overall"] == "lookback_partial"
    assert "2504" in r["lookback"]["missing_months"]


def test_malformed_trace_shape_is_fail_closed():
    # curr が list でない (dict) 等の shape 不正は crash させず fail-closed (exit1)。
    r = F.audit_fetch_trace({"target_month": "2606", "curr": {"oops": 1}, "prev": []})
    assert r["exit_code"] == 1 and r["overall"] == "trace_malformed"


# ---------------------------------------------------------------------------
# billing_status_summary (要因C1 収集是正の可視化・additive disclosure)
# ---------------------------------------------------------------------------
def test_billing_status_summary_disclosed_when_present():
    t = _ok_trace()
    t["billings"] = {
        "curr": [{"status": "invoice_issued"}, {"status": "account_transfer_notified"},
                 {"status": "stopped"}],
        "prev": [{"status": "invoice_issued"}],
        "lookback": {"2505": [{"status": "invoice_issued"}, {"status": "invoice_issued"}]},
    }
    r = F.audit_fetch_trace(t)
    assert r["exit_code"] == 0  # 既存ゲートは不変 (additive disclosure のみ)
    assert r["billing_status_summary"]["curr"] == {
        "invoice_issued": 1, "account_transfer_notified": 1, "stopped": 1}
    assert r["billing_status_summary"]["prev"] == {"invoice_issued": 1}
    assert r["billing_status_summary"]["lookback"]["2505"] == {"invoice_issued": 2}


def test_billing_status_summary_absent_is_empty_and_gates_unaffected():
    # 既存 trace は "billings" キーを持たない (全既存テスト共通)。空 dict で既存ゲートは無傷。
    r = F.audit_fetch_trace(_ok_trace())
    assert r["billing_status_summary"] == {}
    assert r["exit_code"] == 0


def test_billing_status_summary_malformed_is_empty_not_crash():
    t = _ok_trace()
    t["billings"] = "oops"
    r = F.audit_fetch_trace(t)
    assert r["billing_status_summary"] == {}
    assert r["exit_code"] == 0
