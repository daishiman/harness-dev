#!/usr/bin/env python3
"""scripts/reconcile_invoices.py (月次1コマンド orchestrator) の単体テスト。

MF掛け払い (mfk_api) と Notion (notion_transport._req / _notion_token) は全て mock し、
実ネットワークを一切叩かない。golden 入力 (tests/fixtures の 2606 実データ) を Notion ページ
形へ再構成して sheet query を mock し、本物の lib (build_contracts / reconcile / build_sink_rows)
を一気通貫で走らせて配線を検証する。

検証する不変条件:
  - fail-closed : DB id 欠落 / target 不正 / step 依存違反 で exit 2。
  - dry-run     : 書き込み関数 (upsert_master / upsert_monthly) が一度も呼ばれない。
  - apply       : 各 step が canonical 順で実行され、sink へ渡る順方向 rows に
                  contract_page_id が解決済み。
  - collect     : mfk_api を mock し /billings/qualified→/transactions→/customers から
                  raw mf を組み立てる (ネットワーク無し)。
"""
import json
import os

import pytest

import mfk_reconcile
import notion_reconcile_sink
import notion_transport
import reconcile_invoices as O
import sheet_to_master

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TARGET = "2606"


def _load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def sheet_rows():
    return _load("notion_2606.json")


@pytest.fixture(scope="module")
def mf_json():
    return _load("mf_2606.json")


# ---------------------------------------------------------------------------
# golden 入力 → Notion ページ / MF API 応答 への再構成 (mock の素材)
# ---------------------------------------------------------------------------
def _row_to_page(row, i):
    """請求確認シート行 dict を Notion ページ形へ。取引先=title, 他=rich_text。"""
    def rt(v):
        return {"rich_text": [{"plain_text": v or "", "text": {"content": v or ""}}]}

    return {
        "id": row.get("page_id") or f"sheet-{i}",
        "properties": {
            "取引先": {"title": [{"plain_text": row.get("取引先", ""),
                               "text": {"content": row.get("取引先", "")}}]},
            "商品": rt(row.get("商品", "")),
            "確認内容": rt(row.get("確認内容", "")),
            "契約開始日": rt(row.get("契約開始日", "")),
            "契約終了月": rt(row.get("契約終了月", "")),
        },
    }


def _fake_notion_req(sheet_db, sheet_pages, sheet_writes=None):
    """sheet_db の query + シート書き戻し (判定列追加 + 行 PATCH) に応答する fake _req。

    sheet_writes(dict) を渡すと page_id→PATCH props を記録し、書き戻し内容を検証できる。
    GET /databases は『判定』列が未存在の状態を返し、ensure_judgment_property に作成させる。
    """
    def req(method, path, token, body=None):
        if method == "POST" and path == f"/databases/{sheet_db}/query":
            return {"results": sheet_pages, "has_more": False}
        if method == "GET" and path == f"/databases/{sheet_db}":
            return {"properties": {"取引先": {"type": "title"}, "AI確認": {"type": "checkbox"}}}
        if method == "PATCH" and path == f"/databases/{sheet_db}":
            return {}  # 判定 select 列の追加 (冪等)
        if method == "PATCH" and path.startswith("/pages/"):
            if sheet_writes is not None:
                sheet_writes[path.split("/pages/")[1]] = (body or {}).get("properties", {})
            return {}
        raise AssertionError(f"想定外の Notion 呼び出し: {method} {path}")
    return req


def test_extract_sheet_row_carries_mf_customer_id_fields():
    page = {
        "id": "p1",
        "properties": {
            "取引先": {"title": [{"plain_text": "A社", "text": {"content": "A社"}}]},
            "MF顧客ID": {"rich_text": [{"plain_text": "CUST-A"}]},
            "顧客ID": {"rich_text": [{"plain_text": "LEGACY-A"}]},
        },
    }
    row = O._extract_sheet_row(page)
    assert row["MF顧客ID"] == "CUST-A"
    assert row["顧客ID"] == "LEGACY-A"


def _fake_mfk(mf_json):
    """mfk_api.iter_all / get を mf fixture から再構成して返す mock 群。

    iter_all('/billings/qualified') : 各顧客の各 billing_id を 1 billing として yield。
    iter_all('/transactions')       : billing_id に属する明細を transaction_details 化。
    get('/customers')               : ids → name 解決。
    """
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            # 要因C1根治: status ハードフィルタは外れ client 側フィルタへ移行した。
            assert "status" not in params
            for cid, c in mf_json["customers"].items():
                seen = []
                for ln in c["lines"]:
                    if ln["billing_id"] not in seen:
                        seen.append(ln["billing_id"])
                for bid in seen:
                    yield {"id": bid, "customer_id": cid,
                           "issue_date": "2026-06-15", "status": "invoice_issued"}
            return
        if path == "/transactions":
            bid = params["billing_id"]
            details = []
            for c in mf_json["customers"].values():
                for ln in c["lines"]:
                    if ln["billing_id"] == bid:
                        details.append({"description": ln["desc"], "amount": ln["amount"],
                                        "unit_price": ln["unit_price"], "quantity": ln["qty"]})
            yield {"date": "2026-06-30", "transaction_details": details}
            return
        raise AssertionError(f"想定外の MF 呼び出し: {path}")

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            ids = params["ids"]
            return {"items": [{"id": cid, "name": mf_json["customers"][cid]["name"]}
                              for cid in ids if cid in mf_json["customers"]]}
        raise AssertionError(f"想定外の MF 呼び出し: {path}")

    return iter_all, get


class _AllPages(dict):
    """どの契約IDに対しても 'pg-<cid>' を返す page_id マップ (apply の解決を模す)。"""
    def get(self, key, default=None):
        return f"pg-{key}"


@pytest.fixture
def wired(monkeypatch, sheet_rows, mf_json):
    """orchestrator の外部 I/O を全 mock し、書き込み呼び出しを記録する。"""
    sheet_db = "sheetdb"
    pages = [_row_to_page(r, i) for i, r in enumerate(sheet_rows)]
    sheet_writes = {}
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req",
                        _fake_notion_req(sheet_db, pages, sheet_writes))
    iter_all, get = _fake_mfk(mf_json)
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})

    calls = {"master": [], "monthly": []}

    def fake_master(contracts, db1, token, req=None):
        calls["master"].append({"contracts": contracts, "db1": db1})
        return {"created": len(contracts), "updated": 0, "failed": []}

    def fake_monthly(rows, db2, target_ym, token, req=None):
        calls["monthly"].append({"rows": rows, "db2": db2, "target_ym": target_ym})
        return {"created": len(rows), "updated": 0, "frozen": 0, "failed": 0}

    monkeypatch.setattr(sheet_to_master, "upsert_master", fake_master)
    monkeypatch.setattr(notion_reconcile_sink, "upsert_monthly", fake_monthly)
    monkeypatch.setattr(sheet_to_master, "_existing_contract_ids",
                        lambda *a, **k: _AllPages())
    return {"sheet_db": sheet_db, "calls": calls, "sheet_writes": sheet_writes}


def _args(sheet_db, **over):
    base = dict(sheet_db=sheet_db, db1="db1", db2="db2")
    base.update(over)
    return ["--target", TARGET, "--sheet-db", base["sheet_db"],
            "--db1", base["db1"], "--db2", base["db2"]]


# ---------------------------------------------------------------------------
# fail-closed
# ---------------------------------------------------------------------------
def test_missing_db_ids_exit2(monkeypatch):
    # config 空 + env 無し + 引数無し → 必須 DB id が解決できず exit 2。
    for env in ("MFK_SHEET_DB_ID", "MFK_RECONCILE_DB1_ID", "MFK_RECONCILE_DB2_ID"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})
    assert O.main(["--target", TARGET]) == 2


def test_invalid_target_exit2():
    assert O.main(["--target", "2699"]) == 2   # 99 月は不正
    assert O.main(["--target", "abc"]) == 2
    assert O.main([]) == 2                      # --target 未指定


def test_unknown_step_exit2(monkeypatch):
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})
    assert O.main(["--target", TARGET, "--steps", "bogus"]) == 2


def test_step_dependency_violation_exit2(monkeypatch):
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})
    # reconcile には sync-master + collect が必要。
    assert O.main(["--target", TARGET, "--steps", "reconcile",
                   "--sheet-db", "s", "--db1", "d1", "--db2", "d2"]) == 2
    # sink には reconcile が必要。
    assert O.main(["--target", TARGET, "--steps", "sync-master,collect,sink",
                   "--sheet-db", "s", "--db1", "d1", "--db2", "d2"]) == 2


def test_db_id_from_config_keys(monkeypatch, capsys):
    # config の notion.* キーから解決され (引数省略でも) collect 単独は DB id 不要で通る。
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": "S", "reconcile_db1_id": "D1",
                                                    "reconcile_db2_id": "D2"}})
    iter_all, get = _fake_mfk(_load("mf_2606.json"))
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    assert O.main(["--target", TARGET, "--steps", "collect"]) == 0


# ---------------------------------------------------------------------------
# dry-run / apply
# ---------------------------------------------------------------------------
def test_dry_run_no_writes(wired, capsys):
    rc = O.main(_args(wired["sheet_db"]))
    assert rc == 0
    # 書き込み関数は一度も呼ばれない。
    assert wired["calls"]["master"] == []
    assert wired["calls"]["monthly"] == []
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "[collect]" in out and "[sync-master]" in out
    assert "[reconcile]" in out and "[sink]" in out


def test_apply_with_sink_requires_verified(wired, capsys):
    rc = O.main(_args(wired["sheet_db"]) + ["--apply"])
    assert rc == 2
    assert wired["calls"]["master"] == []
    assert wired["calls"]["monthly"] == []
    assert "--verified" in capsys.readouterr().err


def test_apply_runs_all_steps_and_resolves_page_id(wired):
    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])
    assert rc == 0
    # 各 step の書き込みが 1 回ずつ実行された。
    assert len(wired["calls"]["master"]) == 1
    assert len(wired["calls"]["monthly"]) == 1
    master = wired["calls"]["master"][0]
    assert master["db1"] == "db1"
    assert len(master["contracts"]) > 0
    monthly = wired["calls"]["monthly"][0]
    assert monthly["db2"] == "db2"
    assert monthly["target_ym"] == TARGET
    rows = monthly["rows"]
    forward = [r for r in rows if r["direction"] == "順方向"]
    assert forward, "順方向 row が生成されていない"
    # 順方向 row は全て contract_page_id が解決されている (apply 時 DB1 query で 契約ID→page_id)。
    assert all(r.get("contract_page_id") for r in forward)
    assert all(r["contract_page_id"] == f"pg-{r['contract_id']}" for r in forward)


def test_apply_stops_before_db2_when_db1_upsert_failed(wired, monkeypatch, capsys):
    def failed_master(contracts, db1, token, req=None):
        return {"created": 0, "updated": 0,
                "failed": [{"契約ID": contracts[0]["契約ID"], "error": "boom"}]}

    monkeypatch.setattr(sheet_to_master, "upsert_master", failed_master)
    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])
    assert rc == 2
    assert wired["calls"]["monthly"] == []
    err = capsys.readouterr().err
    assert "DB1 upsert failed; DB2 sink skipped" in err


def test_apply_sink_rows_have_judge_labels(wired):
    O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])
    rows = wired["calls"]["monthly"][0]["rows"]
    assert all(r.get("judge_label") for r in rows)
    # orphan 行は relation 無し・mf_customer_id を持つ。
    orphans = [r for r in rows if r["direction"] == "逆方向orphan"]
    if orphans:
        assert all(r.get("contract_page_id") is None for r in orphans)
        assert all(r.get("mf_customer_id") for r in orphans)


def test_apply_writes_back_judgment_to_sheet(wired):
    # apply 時、forward rows の 5値判定 + AI確認 + 確認ポイント が請求確認シート各行へ書き戻され、
    # 契約開始日は空欄セルのみ派生値で自動補完される。契約終了月は誤推定防止のため触らない。
    O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])
    writes = wired["sheet_writes"]
    assert writes, "シートへの書き戻しが発生していない"
    allowed = {"判定", "AI確認", "確認ポイント", "契約開始日"}
    human_forbidden = {"チェック済み", "確認内容", "取引先", "商品", "年月"}
    labels = set()
    for props in writes.values():
        # 機械が触るのは判定/AI確認/確認ポイント(+空欄日付の自動補完)のみ。人間列には触れない。
        assert set(props) <= allowed, f"想定外の列を書いた: {set(props) - allowed}"
        assert not (set(props) & human_forbidden), f"人間列に触れた: {set(props) & human_forbidden}"
        labels.add(props["判定"]["select"]["name"])
        assert isinstance(props["AI確認"]["checkbox"], bool)
    # 5値のうち実データに出るラベルだけが書かれる (DB2 の15ラベルでなく5値投影)。
    assert labels <= {"AIの確認OK", "対象外", "要確認", "発行漏れ"}


def test_apply_skips_sheet_writeback_when_db2_failed(wired, monkeypatch, capsys):
    def failed_monthly(rows, db2, target_ym, token, req=None):
        wired["calls"]["monthly"].append({"rows": rows, "db2": db2, "target_ym": target_ym})
        return {"created": 0, "updated": 0, "frozen": 0, "failed": 1}

    monkeypatch.setattr(notion_reconcile_sink, "upsert_monthly", failed_monthly)
    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])

    assert rc == 2
    assert wired["sheet_writes"] == {}
    assert "DB2 upsert had failed rows" in capsys.readouterr().err


def test_apply_continues_sheet_writeback_when_db2_frozen(wired, monkeypatch, capsys):
    def frozen_monthly(rows, db2, target_ym, token, req=None):
        wired["calls"]["monthly"].append({"rows": rows, "db2": db2, "target_ym": target_ym})
        return {"created": 0, "updated": 0, "frozen": 1, "failed": 0}

    monkeypatch.setattr(notion_reconcile_sink, "upsert_monthly", frozen_monthly)
    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])

    assert rc == 0
    assert wired["sheet_writes"], "DB2 frozen だけでシート確認ポイント全体を止めない"
    assert "DB2 upsert had frozen rows" in capsys.readouterr().err


def test_apply_aborts_when_verdict_mapping_missing(wired, monkeypatch, capsys):
    monkeypatch.setattr(mfk_reconcile, "load_verdict_mapping", lambda *a, **k: {})

    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--verified"])

    assert rc == 2
    assert wired["calls"]["monthly"] == []
    assert wired["sheet_writes"] == {}
    assert "verdict-mapping.json could not be loaded" in capsys.readouterr().err


def test_dry_run_does_not_write_sheet(wired):
    O.main(_args(wired["sheet_db"]))  # --apply 無し
    assert wired["sheet_writes"] == {}, "dry-run でシートへ書き戻してはいけない"


def test_steps_subset_sync_master_only(wired):
    # sync-master 単独 (apply) → DB1 upsert のみ・DB2 upsert は起きない。
    rc = O.main(_args(wired["sheet_db"]) + ["--apply", "--steps", "sync-master"])
    assert rc == 0
    assert len(wired["calls"]["master"]) == 1
    assert wired["calls"]["monthly"] == []


# ---------------------------------------------------------------------------
# 純関数ユニット (橋渡し / 抽出 / 解決)
# ---------------------------------------------------------------------------
def test_month_range_iso():
    # 取引日基準のため取得窓は当月初〜翌月末 (over-fetch)。当月取引(翌月発行)を捕捉する。
    assert O._month_range_iso("2606") == ("2026-06-01", "2026-07-31")
    assert O._month_range_iso("2602") == ("2026-02-01", "2026-03-31")
    assert O._month_range_iso("2612") == ("2026-12-01", "2027-01-31")  # 年跨ぎ


def test_iso_to_ym():
    assert O._iso_to_ym("2026-06-30") == "2606"
    assert O._iso_to_ym("2026-07-02") == "2607"
    assert O._iso_to_ym("2026-12-01") == "2612"
    assert O._iso_to_ym("") is None
    assert O._iso_to_ym(None) is None
    assert O._iso_to_ym("garbage") is None


def test_collect_mf_attributes_by_transaction_date(monkeypatch):
    """月帰属は取引日(transaction.date)。当月取引(翌月発行)を採用し前月取引(当月発行)を除外。"""
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            # 取得窓が翌月末まで広がっている (over-fetch)。
            assert params["issue_date_from"] == "2026-06-01"
            assert params["issue_date_to"] == "2026-07-31"
            # B_curr: 6月取引・7月発行 (当月分) / B_prev: 5月取引・6月発行 (前月分)。
            yield {"id": "B_curr", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            yield {"id": "B_prev", "customer_id": "C2", "issue_date": "2026-06-10",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            bid = params["billing_id"]
            if bid == "B_curr":
                yield {"date": "2026-06-30", "issue_date": "2026-07-02",
                       "transaction_details": [
                           {"description": "6月分", "amount": 100000,
                            "unit_price": 100000, "quantity": 1}]}
                return
            yield {"date": "2026-05-31", "issue_date": "2026-06-10",
                   "transaction_details": [
                       {"description": "5月分", "amount": 50000,
                        "unit_price": 50000, "quantity": 1}]}
            return
        raise AssertionError(f"想定外の MF 呼び出し: {path}")

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(f"想定外の MF 呼び出し: {path}")

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf("2606", cfg={})
    # 取引日6月(C1)は採用、取引日5月(C2)は当月発行でも除外。
    assert "C1" in raw["customers"]
    assert "C2" not in raw["customers"]
    assert raw["customers"]["C1"]["lines"][0]["desc"] == "6月分"
    assert raw["customers"]["C1"]["lines"][0]["txn_date"] == "2026-06-30"


def test_collect_mf_fallbacks_to_issue_date_when_txn_date_missing(monkeypatch):
    """transaction.date 欠落時は billing.issue_date へ縮退し当月発行分を取りこぼさない。"""
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            yield {"id": "B1", "customer_id": "C1", "issue_date": "2026-06-15",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            # date / issue_date とも無い transaction (旧 fixture 形)。
            yield {"transaction_details": [
                {"description": "x", "amount": 1000, "unit_price": 1000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf("2606", cfg={})
    assert "C1" in raw["customers"]  # issue_date 2026-06 → 2606 として採用


def test_collect_mf_reads_all_transaction_pages(monkeypatch):
    """各 billing の /transactions もカーソルページングで全ページ読む。"""
    calls = []

    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        calls.append((path, dict(params or {})))
        if path == "/billings/qualified":
            yield {"id": "B1", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            assert params["billing_id"] == "B1"
            yield {"date": "2026-06-30", "transaction_details": [
                {"description": "page1", "amount": 1000, "unit_price": 1000, "quantity": 1}]}
            yield {"date": "2026-06-30", "transaction_details": [
                {"description": "page2", "amount": 2000, "unit_price": 2000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf("2606", cfg={})
    lines = raw["customers"]["C1"]["lines"]
    assert [line["desc"] for line in lines] == ["page1", "page2"]
    assert any(path == "/transactions" for path, _params in calls)


def test_collect_mf_carries_status_and_canceled_at(monkeypatch, capsys):
    """collect_mf は line に status/canceled_at を載せ canceled 行も lines に残す。当月取消件数を stderr 可視化。"""
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            yield {"id": "B1", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            yield {"date": "2026-06-30", "status": "passed",
                   "transaction_details": [{"description": "有効", "amount": 100000,
                                            "unit_price": 100000, "quantity": 1}]}
            yield {"date": "2026-06-30", "status": "canceled",
                   "canceled_at": "2026-06-25T17:39:45+09:00",
                   "transaction_details": [{"description": "取消", "amount": 200000,
                                            "unit_price": 200000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf("2606", cfg={})
    lines = raw["customers"]["C1"]["lines"]
    # canceled 行も lines に残す (build_mf_signals 入力を不変に保つ)。
    assert len(lines) == 2
    by_desc = {ln["desc"]: ln for ln in lines}
    assert by_desc["有効"]["status"] == "passed" and by_desc["有効"]["canceled_at"] is None
    assert by_desc["取消"]["status"] == "canceled"
    assert by_desc["取消"]["canceled_at"] == "2026-06-25T17:39:45+09:00"
    assert "canceled (取消) 取引 1件" in capsys.readouterr().err


def test_collect_mf_then_index_routes_canceled(monkeypatch):
    """collect_mf → build_mf_index で取消は services でなく inactive バケットへ振り分けられる。"""
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            yield {"id": "B1", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            yield {"date": "2026-06-30", "status": "passed",
                   "transaction_details": [{"description": "有効", "amount": 100000,
                                            "unit_price": 100000, "quantity": 1}]}
            yield {"date": "2026-06-30", "status": "canceled",
                   "canceled_at": "2026-06-25T17:39:45+09:00",
                   "transaction_details": [{"description": "取消", "amount": 200000,
                                            "unit_price": 200000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    idx = mfk_reconcile.build_mf_index(O.collect_mf("2606", cfg={}))
    assert [s["amount"] for s in idx["C1"]["services"]] == [100000]
    assert [x["amount"] for x in idx["C1"]["inactive"]] == [200000]
    assert idx["C1"]["inactive"][0]["status"] == "canceled"


def test_reconcile_warns_unsupported_end_date(monkeypatch, capsys):
    """月次フローが確認内容に終了根拠なき契約終了月を read-only で検知・警告する (健全性・fail-soft)。

    当月契約なら engine が REVIEW_ENDED_NO_BASIS(要確認)で行ごと可視化し、全シート横断の件数も
    『健全性』サマリ + stderr で告知する。検知のみで列クリアは行わず exit code も変えない。
    """
    sheet_rows = [
        {"取引先": "継続商事", "商品": "P", "確認内容": "90,000円",
         "契約開始日": "2501", "契約終了月": "2605", "page_id": "pg-keizoku"},
    ]
    sheet_db = "sheetdb"
    pages = [_row_to_page(r, i) for i, r in enumerate(sheet_rows)]
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", _fake_notion_req(sheet_db, pages))
    iter_all, get = _fake_mfk({"customers": {}})  # MF 実績なし → SUPPRESS/REVIEW 分岐へ
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": sheet_db}})

    rc = O.main(["--target", "2606", "--steps", "collect,sync-master,reconcile",
                 "--sheet-db", sheet_db])
    out = capsys.readouterr()
    assert rc == 0  # fail-soft: 検知は exit code を変えない
    assert "根拠なき契約終了月: 1件" in out.out
    assert "clear_unsupported_end_dates.py --apply" in out.err
    assert "REVIEW_ENDED_NO_BASIS" in out.out  # 当月契約は要確認で行ごと可視化


def test_reconcile_no_health_warning_when_end_grounded(monkeypatch, capsys):
    """確認内容に終了根拠ありの契約終了月は健全性警告を出さない (誤検出しない)。"""
    sheet_rows = [
        {"取引先": "撤退商事", "商品": "P", "確認内容": "90,000円 請求なし（2605終了）",
         "契約開始日": "2501", "契約終了月": "2605", "page_id": "pg-tettai"},
    ]
    sheet_db = "sheetdb"
    pages = [_row_to_page(r, i) for i, r in enumerate(sheet_rows)]
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", _fake_notion_req(sheet_db, pages))
    iter_all, get = _fake_mfk({"customers": {}})
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": sheet_db}})

    rc = O.main(["--target", "2606", "--steps", "collect,sync-master,reconcile",
                 "--sheet-db", sheet_db])
    out = capsys.readouterr()
    assert rc == 0
    assert "健全性" not in out.out
    assert "REVIEW_ENDED_NO_BASIS" not in out.out  # 根拠ありは SUPPRESS_ENDED のまま


def test_reconcile_shows_cancellation_balance(monkeypatch, capsys):
    """取消が REVIEW_CANCELED と 対象外+取消注記 に振り分けられ、取消バランス行が出る (情報表示・exit不変)。

    C1(月次・取消のみ)→REVIEW_CANCELED、C2(終了根拠あり・取消のみ)→SUPPRESS_ENDED+取消注記。
    collect検出2件 = 要確認(取消)1 + 対象外等に取消注記1 をサマリへ可視化する (WARN-not-FAIL)。
    """
    sheet_rows = [
        {"取引先": "取消商事", "商品": "チイキズカン業務委託費", "確認内容": "70,000円",
         "契約開始日": "", "契約終了月": "", "page_id": "pg-cancel"},
        {"取引先": "終了取消商事", "商品": "P", "確認内容": "90,000円 請求なし（2605終了）",
         "契約開始日": "2501", "契約終了月": "2605", "page_id": "pg-ended"},
    ]
    sheet_db = "sheetdb"
    pages = [_row_to_page(r, i) for i, r in enumerate(sheet_rows)]

    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            yield {"id": "B1", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            yield {"id": "B2", "customer_id": "C2", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            return
        if path == "/transactions":
            if params["billing_id"] == "B1":
                yield {"date": "2026-06-30", "status": "canceled",
                       "canceled_at": "2026-06-25T17:39:45+09:00",
                       "transaction_details": [
                           {"description": "チイキズカン業務委託費（田中様 2026年6月分）",
                            "amount": 70000, "unit_price": 70000, "quantity": 1}]}
                return
            yield {"date": "2026-06-30", "status": "canceled",
                   "canceled_at": "2026-06-25T17:39:45+09:00",
                   "transaction_details": [
                       {"description": "業務委託費（佐藤様 2026年6月分）",
                        "amount": 90000, "unit_price": 90000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            names = {"C1": "取消商事", "C2": "終了取消商事"}
            return {"items": [{"id": c, "name": names[c]} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", _fake_notion_req(sheet_db, pages))
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": sheet_db}})

    rc = O.main(["--target", "2606", "--steps", "collect,sync-master,reconcile",
                 "--sheet-db", sheet_db])
    out = capsys.readouterr()
    assert rc == 0  # 情報表示・exit code を変えない
    assert "canceled (取消) 取引 2件" in out.err
    assert "[取消可視化] 要確認(取消): 1件" in out.out
    assert "[取消バランス] collect検出 2件" in out.out
    assert "要確認(取消) 1件 + 対象外等に取消注記 1件" in out.out


def test_extract_sheet_row():
    page = {
        "id": "pg-1",
        "properties": {
            "取引先": {"title": [{"plain_text": "X社"}]},
            "商品": {"select": {"name": "業務委託費"}},
            "確認内容": {"rich_text": [{"plain_text": "月額300,000円"}]},
            "契約開始日": {"date": {"start": "2026-05-01"}},
            "契約終了月": {"number": 2606},
        },
    }
    row = O._extract_sheet_row(page)
    assert row["取引先"] == "X社"
    assert row["商品"] == "業務委託費"
    assert row["確認内容"] == "月額300,000円"
    assert row["契約開始日"] == "2026-05-01"
    assert row["契約終了月"] == "2606"
    assert row["page_id"] == "pg-1"


def test_prop_to_text_handles_missing():
    assert O._prop_to_text(None) == ""
    assert O._prop_to_text({}) == ""
    assert O._prop_to_text({"select": None}) == ""
    assert O._prop_to_text({"date": None}) == ""
    assert O._prop_to_text({"number": None}) == ""


def test_resolve_db_ids_precedence(monkeypatch):
    cfg = {"notion": {"sheet_db_id": "cfgS", "reconcile_db1_id": "cfgD1",
                      "reconcile_db2_id": "cfgD2"}}
    args = type("A", (), {"sheet_db": None, "db1": None, "db2": None})()
    monkeypatch.delenv("MFK_SHEET_DB_ID", raising=False)
    monkeypatch.delenv("MFK_RECONCILE_DB1_ID", raising=False)
    monkeypatch.delenv("MFK_RECONCILE_DB2_ID", raising=False)
    assert O.resolve_db_ids(cfg, args) == ("cfgS", "cfgD1", "cfgD2")
    # env が config を上書きする。
    monkeypatch.setenv("MFK_SHEET_DB_ID", "envS")
    assert O.resolve_db_ids(cfg, args)[0] == "envS"
    # 引数が最優先。
    args.sheet_db = "argS"
    assert O.resolve_db_ids(cfg, args)[0] == "argS"


def test_required_db_ids():
    # dry-run (apply=False): 実際に DB を触らない step は DB id を要求しない。
    # sync-master のシート読取だけ sheet_db を要求 (db1/db2 は --apply 時のみ)。
    assert O.required_db_ids({"collect"}, False) == set()
    assert O.required_db_ids({"sync-master"}, False) == {"sheet_db"}
    assert O.required_db_ids({"sink"}, False) == set()
    assert O.required_db_ids(set(O.ALL_STEPS), False) == {"sheet_db"}
    # apply (apply=True): 書き込み/page_id 解決で db1/db2 が必要になる。
    assert O.required_db_ids({"collect"}, True) == set()
    assert O.required_db_ids({"sync-master"}, True) == {"sheet_db", "db1"}
    assert O.required_db_ids({"sink"}, True) == {"db1", "db2"}
    assert O.required_db_ids(set(O.ALL_STEPS), True) == {"sheet_db", "db1", "db2"}


def test_collect_mf_builds_raw(monkeypatch, mf_json):
    iter_all, get = _fake_mfk(mf_json)
    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf(TARGET, cfg={})
    assert "customers" in raw
    assert len(raw["customers"]) == len(mf_json["customers"])
    # 会社名が解決され、明細が line 化されている。
    sample = next(iter(raw["customers"].values()))
    assert sample["name"]
    assert sample["lines"]
    assert {"desc", "amount", "unit_price", "qty", "billing_id"} <= set(sample["lines"][0])


def test_build_sink_rows_maps_forward_and_orphan():
    result = {
        "rows": [
            {"direction": "順方向", "契約ID": "X/田中/業務委託費", "verdict": "MATCH_MONTHLY",
             "現行単価": 300000, "期待明細数": 1, "warning": "",
             "evidence": {"amount": 300000, "billing_id": "B1"}},
            {"direction": "順方向", "契約ID": "Y//業務委託費", "verdict": "GAP",
             "現行単価": 50000, "期待明細数": 1, "warning": "発行漏れ", "evidence": None},
        ],
        "orphans": [
            {"direction": "逆方向orphan", "MF顧客ID": "C9", "verdict": "ORPHAN",
             "amount": 88000, "warning": "要マスタ登録",
             "services": [{"amount": 88000, "billing_id": "B9"}]},
        ],
    }
    page_map = {"X/田中/業務委託費": "pg-1"}
    rows = O.build_sink_rows(result, page_map)
    assert len(rows) == 3
    f0 = rows[0]
    assert f0["contract_id"] == "X/田中/業務委託費"
    assert f0["contract_page_id"] == "pg-1"
    assert f0["expected_amount"] == 300000
    assert f0["matched_amount"] == 300000
    assert f0["mf_billing_id"] == "B1"
    assert f0["judge_label"]  # verdict-mapping から導出 (空でない)
    assert f0["ai_check"] is True
    f1 = rows[1]
    assert f1["contract_page_id"] is None  # マップに無い → 未解決
    assert f1["matched_amount"] is None
    assert f1["ai_check"] is False
    orphan = rows[2]
    assert orphan["direction"] == "逆方向orphan"
    assert orphan["contract_id"] is None
    assert orphan["mf_customer_id"] == "C9"
    assert orphan["matched_amount"] == 88000
    assert orphan["mf_billing_id"] == "B9"
    assert orphan["ai_check"] is False


def test_parse_steps():
    assert O._parse_steps(None) == set(O.ALL_STEPS)
    assert O._parse_steps("collect") == {"collect"}
    with pytest.raises(ValueError):
        O._parse_steps("nope")
    with pytest.raises(ValueError):
        O._parse_steps("reconcile")          # 依存欠落
    with pytest.raises(ValueError):
        O._parse_steps("sync-master,collect,sink")  # sink に reconcile 無し


def test_find_local_config(tmp_path, monkeypatch):
    # 親探索: 子ディレクトリから上方向に .mf-kessai-config.json を見つける。
    (tmp_path / "a").mkdir()
    cfg = tmp_path / ".mf-kessai-config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert O._find_local_config(str(tmp_path / "a")) == str(cfg)
    # 見つからない場合は None (存在しない隔離ディレクトリ)。
    empty = tmp_path / "x" / "y"
    empty.mkdir(parents=True)
    assert O._find_local_config(str(empty)) == str(cfg)  # 上方向に tmp_path の cfg を発見


def test_needs_notion():
    assert O._needs_notion({"sync-master"}, apply=False) is True
    assert O._needs_notion({"sink"}, apply=True) is True
    assert O._needs_notion({"sink"}, apply=False) is False
    assert O._needs_notion({"collect"}, apply=True) is False


def test_collect_mf_includes_post_issuance_billing_status(monkeypatch, capsys):
    """発行済み後続 status (account_transfer_notified) の billing を収集し、真の停止 (stopped) は
    除外する (要因C1回帰: paws有限会社型)。billings/qualified への status ハードフィルタも
    外れていることを確認する。
    """
    def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
        if path == "/billings/qualified":
            assert "status" not in params
            yield {"id": "B_issued", "customer_id": "C1", "issue_date": "2026-07-02",
                   "status": "invoice_issued"}
            yield {"id": "B_transfer", "customer_id": "C2", "issue_date": "2026-07-02",
                   "status": "account_transfer_notified"}
            yield {"id": "B_stopped", "customer_id": "C3", "issue_date": "2026-07-02",
                   "status": "stopped"}
            return
        if path == "/transactions":
            bid = params["billing_id"]
            if bid == "B_stopped":
                raise AssertionError("stopped billing の /transactions を取得してはいけない")
            yield {"date": "2026-06-30", "status": "passed", "transaction_details": [
                {"description": f"desc-{bid}", "amount": 55000,
                 "unit_price": 55000, "quantity": 1}]}
            return
        raise AssertionError(path)

    def get(path, params=None, cfg=None, api_key=None):
        if path == "/customers":
            return {"items": [{"id": c, "name": f"社{c}"} for c in params["ids"]]}
        raise AssertionError(path)

    monkeypatch.setattr(O.mfk_api, "iter_all", iter_all)
    monkeypatch.setattr(O.mfk_api, "get", get)
    raw = O.collect_mf("2606", cfg={})
    assert "C1" in raw["customers"] and "C2" in raw["customers"]
    assert "C3" not in raw["customers"]  # stopped は真の停止=非発行なので収集対象外
    assert raw["customers"]["C2"]["lines"][0]["billing_status"] == "account_transfer_notified"
    assert raw["customers"]["C1"]["lines"][0]["billing_status"] == "invoice_issued"
    # 生の billing 一覧 (client 側フィルタ前) を canonical carrier として返す。
    assert [b["status"] for b in raw["billings"]] == \
        ["invoice_issued", "account_transfer_notified", "stopped"]
    err = capsys.readouterr().err
    assert "1件" in err  # 非issued (stopped) 1件を除外した旨の可視化
