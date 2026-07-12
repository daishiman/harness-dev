#!/usr/bin/env python3
"""check_invoice_gaps.py の出力先解決(F2)・確定リスト昇格(F1)・schema検証(F4)の回帰テスト。

ネットワーク/Notion を伴わない純ファイル操作部分のみを対象とする。
"""
import datetime
import json
import os

import check_invoice_gaps as c


# --- F2: 出力先解決 env > project > cwd ---

def test_eval_log_prefers_env(monkeypatch):
    monkeypatch.setenv("MFK_OUTPUT_DIR", "/tmp/mfk-a")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-a/eval-log"


def test_eval_log_falls_back_to_project(monkeypatch):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-b/eval-log"


def test_eval_log_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert c.eval_log_dir() == os.path.join(str(tmp_path), "eval-log")


def test_no_repo_root_assumption():
    """_REPO_ROOT 派生 (repo 配置前提) が撤廃されていること。"""
    assert not hasattr(c, "_REPO_ROOT")
    assert not hasattr(c, "DEFAULT_CANDIDATES")


# --- F4: schema 検証 ---

def test_validate_rows_ok():
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "発行漏れ候補", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": None}]
    assert c.validate_rows(rows) == []


def test_validate_rows_rejects_empty_period():
    rows = [{"customer_id": "c1", "period_ym": "", "company_name": "A社",
             "verdict": "発行漏れ候補", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": None}]
    errs = c.validate_rows(rows)
    assert errs and "period_ym" in errs[0]


def test_validate_rows_rejects_nonexistent_month():
    rows = [{"customer_id": "c1", "period_ym": "2026-13", "company_name": "A社",
             "verdict": "発行漏れ候補", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": None}]
    errs = c.validate_rows(rows)
    assert any("実在月でない" in e for e in errs)


def test_validate_rows_rejects_bad_verdict_and_empty_cid():
    rows = [{"customer_id": "", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "謎判定", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": None}]
    errs = c.validate_rows(rows)
    assert any("customer_id" in e for e in errs)
    assert any("verdict" in e for e in errs)


def test_validate_rows_rejects_schema_extra_key():
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "継続発行", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": 100, "unexpected": "x"}]
    errs = c.validate_rows(rows)
    assert any("schema 外のキー" in e and "unexpected" in e for e in errs)


def test_validate_rows_rejects_bad_amount_type():
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "継続発行", "product_name": "SaaS",
             "prev_amount": "100", "curr_amount": 100}]
    errs = c.validate_rows(rows)
    assert any("prev_amount" in e and "integer/null" in e for e in errs)


def test_validate_rows_rejects_removed_initial_billing_key():
    """削除した initial_billing_month_estimated は schema 外キーとして拒否される。"""
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "継続発行", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": 100,
             "initial_billing_month_estimated": "2026-04"}]
    errs = c.validate_rows(rows)
    assert any("schema 外のキー" in e and "initial_billing_month_estimated" in e for e in errs)


# --- F1: finalize による確定リスト昇格 (誤検出除外) ---

def _cands(tmp_path):
    p = tmp_path / "mfk-gap-candidates.json"
    p.write_text(json.dumps([
        {"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
         "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 100, "curr_amount": None},
        {"customer_id": "c2", "period_ym": "2026-06", "company_name": "B社",
         "verdict": "発行漏れ候補", "product_name": "SaaS", "prev_amount": 200, "curr_amount": None},
        {"customer_id": "c3", "period_ym": "2026-06", "company_name": "C社",
         "verdict": "継続発行", "product_name": "", "prev_amount": 300, "curr_amount": 300},
    ], ensure_ascii=False), encoding="utf-8")
    return p


def test_finalize_excludes_false_positive(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize(["c2"], str(src), str(out))
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    ids = {r["customer_id"] for r in kept}
    assert ids == {"c1", "c3"}  # 誤検出 c2 のみ除外、継続発行 c3 は素通し


def test_finalize_keeps_all_when_no_exclusions(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize([""], str(src), str(out))  # 除外なし (空文字は無視)
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert len(kept) == 3


def test_finalize_does_not_exclude_non_gap(tmp_path):
    """継続発行は誤検出除外の対象外 (発行漏れ候補のみ exclude 可)。"""
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    c.finalize(["c3"], str(src), str(out))
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert "c3" in {r["customer_id"] for r in kept}


def test_finalize_rejects_invalid_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"customer_id": "x", "period_ym": "", "verdict": "発行漏れ候補"}]),
                   encoding="utf-8")
    out = tmp_path / "v.json"
    assert c.finalize([], str(bad), str(out)) == 2
    assert not out.exists()


def test_sink_rejects_candidates_input_without_force(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    os.makedirs(c.eval_log_dir(), exist_ok=True)
    path = c.candidates_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
                    "verdict": "継続発行", "product_name": "",
                    "prev_amount": 100, "curr_amount": 100}], f)
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink", "--input", path])
    assert c.main() == 2


def test_sink_candidates_input_with_force_is_allowed(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    os.makedirs(c.eval_log_dir(), exist_ok=True)
    path = c.candidates_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
                    "verdict": "継続発行", "product_name": "",
                    "prev_amount": 100, "curr_amount": 100}], f)

    calls = []
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(c.notion_invoice_sink, "upsert",
                        lambda db_id, rows, period_ym=None: calls.append((db_id, rows, period_ym))
                        or {"created": 0, "updated": 1, "period_ym": period_ym, "run_id": "rid"})
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--sink", "--input", path, "--force-unverified"])
    assert c.main() == 0
    assert calls and calls[0][0] == "db1"


def test_sink_rejects_arbitrary_input_without_force(monkeypatch, tmp_path):
    """--force-unverified なしの --input は正規の verified path だけ許可する。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    arbitrary = tmp_path / "copied-candidates.json"
    arbitrary.write_text(json.dumps(
        [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
          "verdict": "継続発行", "product_name": "",
          "prev_amount": 100, "curr_amount": 100}]), encoding="utf-8")
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink", "--input", str(arbitrary)])
    assert c.main() == 2


# --- 改修1: collect が全チェック対象顧客 (継続発行全件含む) を rows 化 ---

def _billing(cid, amount, bid=None, issue_date="2026-06-10"):
    return {"customer_id": cid, "amount": amount, "status": "invoice_issued",
            "id": bid or f"b-{cid}", "issue_date": issue_date}


def _patch_collect_api(monkeypatch, prev, curr):
    """fetch_issued/resolve_names/detail_of を差し替え、detail_of 呼び出しを記録する。

    年間契約抑制の Notion 取得 (_load_initial_contract_months) も既定で空 dict にスタブし、
    collect が initial_contract_months を明示しない既存テストがネットワークへ出ないようにする
    (空 dict = 抑制なし = 従来挙動: 全候補が発行漏れ候補に残る)。年間抑制を検証するテストは
    collect(ym, initial_contract_months=...) を明示して上書きする。
    """
    calls = {"detail_of": []}

    def fake_fetch(ym):
        # prev_month 側か当月側かを引数の月で判定する (collect は prev→curr の順で呼ぶ)。
        return prev if ym == c.prev_month("2026-06") else curr

    def fake_names(ids):
        return {cid: f"会社{cid}" for cid in ids}

    def fake_detail(billing_id):
        calls["detail_of"].append(billing_id)
        return {"product_name": f"商品-{billing_id}", "updated_at": "2026-06-11T00:00:00Z"}

    monkeypatch.setattr(c, "fetch_issued", fake_fetch)
    monkeypatch.setattr(c, "resolve_names", fake_names)
    monkeypatch.setattr(c, "detail_of", fake_detail)
    # 既存 collect テストが Notion を叩かないよう初回契約月取得を空 dict に固定 (抑制スキップ)。
    monkeypatch.setattr(c, "_load_initial_contract_months", lambda db_id: {})
    return calls


def test_resolve_initial_billing_months_function_removed():
    """初回請求月(API推定) 撤去に伴い resolve_initial_billing_months 関数は存在しない。"""
    assert not hasattr(c, "resolve_initial_billing_months")
    assert not hasattr(c, "_issue_month")


def test_fetch_issued_uses_transaction_date_month(monkeypatch):
    """6月分=取引日6月。翌月発行を採用し、当月発行でも前月取引なら除外する。"""
    billings = [
        {"id": "b-current", "customer_id": "current", "amount": 999,
         "status": "invoice_issued", "issue_date": "2026-07-01"},
        {"id": "b-prev", "customer_id": "prev", "amount": 999,
         "status": "invoice_issued", "issue_date": "2026-06-10"},
        {"id": "b-next", "customer_id": "next", "amount": 999,
         "status": "invoice_issued", "issue_date": "2026-07-01"},
    ]
    seen_params = {}
    by_id = {
        "b-current": [{"date": "2026-06-30", "transaction_details": [
            {"description": "6月分", "amount": 100}, {"description": "6月分追加", "amount": 25}
        ]}],
        "b-prev": [{"date": "2026-05-31", "transaction_details": [
            {"description": "5月分", "amount": 50}
        ]}],
        "b-next": [{"date": "2026-07-01", "transaction_details": [
            {"description": "7月分", "amount": 70}
        ]}],
    }

    def fake_iter(path, params):
        if path == "/billings/qualified":
            seen_params.update(params)
            return iter(billings)
        if path == "/transactions":
            return iter(by_id[params["billing_id"]])
        raise AssertionError(path)

    monkeypatch.setattr(c, "iter_all", fake_iter)
    rows = c.fetch_issued("2026-06")

    assert seen_params["issue_date_from"] == "2026-06-01"
    assert seen_params["issue_date_to"] == "2026-07-31"
    assert [r["customer_id"] for r in rows] == ["current"]
    assert rows[0]["amount"] == 125
    assert rows[0]["issue_date"] == "2026-07-01"


def test_fetch_issued_reads_all_transaction_pages(monkeypatch):
    """各 billing の /transactions を iter_all で全ページ読み、201件目以降の対象月取引も拾う。

    /transactions を単発 limit=200 で取ると 201 件目以降を黙って捨て、対象月取引がそこにある
    billing が当月母集合から脱落し継続顧客が発行漏れに誤分類される。iter_all で全ページ走査
    することを固定する (reconcile 側 collect_mf の test_collect_mf_reads_all_transaction_pages と対)。
    """
    billings = [{"id": "b1", "customer_id": "c1", "amount": 0,
                 "status": "invoice_issued", "issue_date": "2026-07-01"}]
    # 1ページ目は前月取引のみ (当月該当なし)、2ページ目=201件目相当に対象月 (2026-06) の取引。
    # 単発取得ならこの2ページ目が捨てられ c1 が脱落する。
    page1 = [{"date": "2026-05-31",
              "transaction_details": [{"description": "5月分", "amount": 1}]}]
    page2 = [{"date": "2026-06-30",
              "transaction_details": [{"description": "6月分", "amount": 500}]}]

    def fake_iter(path, params):
        if path == "/billings/qualified":
            return iter(billings)
        if path == "/transactions":
            assert params["billing_id"] == "b1"
            assert "limit" not in params  # ページングは iter_all 側が管理 (単発 limit=200 でない)
            return iter(page1 + page2)
        raise AssertionError(path)

    monkeypatch.setattr(c, "iter_all", fake_iter)
    rows = c.fetch_issued("2026-06")
    # 2ページ目の対象月取引が拾われ billing が脱落しない。
    assert [r["customer_id"] for r in rows] == ["c1"]
    assert rows[0]["amount"] == 500


def test_fetch_issued_warns_on_date_fallback(monkeypatch, capsys):
    """transaction.date 欠落時は issue_date(当月) へ縮退して当月集合に残しつつ縮退件数を warn する。

    date 欠落 → transaction.issue_date → billing.issue_date の順へ縮退 (発行日基準)。当月集合に
    残る一方、縮退は silent にせず stderr に1行 warn する (WARN-not-FAIL)。collect_mf 側の
    test_collect_mf_fallbacks_to_issue_date_when_txn_date_missing と対の check 側ケース。
    """
    billings = [{"id": "b1", "customer_id": "c1", "amount": 0,
                 "status": "invoice_issued", "issue_date": "2026-07-01"}]
    # date 欠落・issue_date=当月(2026-06) の取引。発行日基準へ縮退して当月集合に残る。
    txs = [{"issue_date": "2026-06-30",
            "transaction_details": [{"description": "6月分", "amount": 300}]}]

    def fake_iter(path, params):
        if path == "/billings/qualified":
            return iter(billings)
        if path == "/transactions":
            return iter(txs)
        raise AssertionError(path)

    monkeypatch.setattr(c, "iter_all", fake_iter)
    rows = c.fetch_issued("2026-06")

    # (1) 縮退で当月集合に残り金額も拾われる。
    assert [r["customer_id"] for r in rows] == ["c1"]
    assert rows[0]["amount"] == 300
    # (2) 縮退件数が stderr に1行 warn される (silent でない・FAIL でない)。
    err = capsys.readouterr().err
    assert "発行日基準へ縮退した取引 1件" in err
    assert "2026-06" in err


def test_fetch_issued_skips_canceled_transactions(monkeypatch, capsys):
    """取消(status=canceled)取引は発行集合へ計上しない(取消前金額が継続発行/今月新規へ化けない)。"""
    billings = [{"id": "b1", "customer_id": "c1", "amount": 0,
                 "status": "invoice_issued", "issue_date": "2026-07-01"}]
    txs = [
        {"date": "2026-06-30", "status": "passed",
         "transaction_details": [{"description": "有効", "amount": 100}]},
        {"date": "2026-06-30", "status": "canceled",
         "canceled_at": "2026-06-25T17:39:45+09:00",
         "transaction_details": [{"description": "取消", "amount": 9999}]},
    ]

    def fake_iter(path, params):
        if path == "/billings/qualified":
            return iter(billings)
        if path == "/transactions":
            return iter(txs)
        raise AssertionError(path)

    monkeypatch.setattr(c, "iter_all", fake_iter)
    rows = c.fetch_issued("2026-06")
    assert [r["customer_id"] for r in rows] == ["c1"]
    # 取消前金額 9999 は加算されず、有効分 100 のみ。
    assert rows[0]["amount"] == 100
    err = capsys.readouterr().err
    assert "取消 (canceled) 取引 1件" in err
    assert "2026-06" in err


def test_fetch_issued_all_canceled_billing_dropped(monkeypatch):
    """billing 内の対象月取引が全て取消なら has_target_transaction=False で発行集合から脱落する。"""
    billings = [{"id": "b1", "customer_id": "c1", "amount": 0,
                 "status": "invoice_issued", "issue_date": "2026-07-01"}]
    txs = [{"date": "2026-06-30", "status": "canceled",
            "canceled_at": "2026-06-25T17:39:45+09:00",
            "transaction_details": [{"description": "取消", "amount": 9999}]}]

    def fake_iter(path, params):
        if path == "/billings/qualified":
            return iter(billings)
        if path == "/transactions":
            return iter(txs)
        raise AssertionError(path)

    monkeypatch.setattr(c, "iter_all", fake_iter)
    assert c.fetch_issued("2026-06") == []  # 全取消 billing は発行集合に出ない


def test_collect_rows_have_no_initial_billing_key(monkeypatch):
    """collect が返す rows に削除した initial_billing_month_estimated キーが残らない。"""
    prev = [_billing("same", 500)]
    curr = [_billing("same", 500)]
    _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    assert rows
    for r in rows:
        assert "initial_billing_month_estimated" not in r


def test_collect_includes_all_continuing(monkeypatch):
    """継続発行は金額変動の有無に関わらず全件 rows 化される (チェック証跡の穴埋め)。"""
    prev = [_billing("gap", 1000), _billing("same", 500), _billing("chg", 200)]
    curr = [_billing("same", 500), _billing("chg", 900), _billing("new", 300)]
    _patch_collect_api(monkeypatch, prev, curr)
    res, rows = c.collect("2026-06")
    by_verdict = {}
    for r in rows:
        by_verdict.setdefault(r["verdict"], []).append(r)
    # 発行漏れ候補 gap / 継続発行 same+chg (変動なし same も含む) / 今月新規 new。
    assert {r["customer_id"] for r in by_verdict["発行漏れ候補"]} == {"gap"}
    assert {r["customer_id"] for r in by_verdict["継続発行"]} == {"same", "chg"}
    assert {r["customer_id"] for r in by_verdict["今月新規"]} == {"new"}
    # 全 verdict が enum 準拠 (validate_rows OK)。
    for r in rows:
        r.setdefault("period_ym", "2026-06")
    assert c.validate_rows(rows) == []


def test_collect_records_unchanged_continuing_amount(monkeypatch):
    """金額変動なし継続発行も前月/今月金額を記録する (verdict=継続発行, 金額は埋まる)。"""
    prev = [_billing("same", 500)]
    curr = [_billing("same", 500)]
    _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    same = [r for r in rows if r["customer_id"] == "same"][0]
    assert same["verdict"] == "継続発行"
    assert same["prev_amount"] == 500 and same["curr_amount"] == 500


def test_collect_unchanged_continuing_issue_date_from_billing(monkeypatch):
    """A3-008: 金額変動なし継続発行 (detail_of スキップ) でも issue_date を当月 billing で補完する。"""
    prev = [_billing("same", 500, issue_date="2026-05-10")]
    curr = [_billing("same", 500, issue_date="2026-06-15")]
    _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    same = [r for r in rows if r["customer_id"] == "same"][0]
    # detail_of をスキップしても当月 billing の発行日で埋まる (空欄落ちしない)。
    assert same["issue_date"] == "2026-06-15"


def test_resolve_names_warns_on_partial_resolution(monkeypatch, capsys):
    """A4-009: 一部 ID だけ企業名解決できた場合も未解決件数を stderr 警告する。"""
    # ids=2 件中 1 件だけ /customers が返す部分名寄せ失敗を再現。
    monkeypatch.setattr(c, "get", lambda path, params: {"items": [{"id": "a", "name": "A社"}]})
    names = c.resolve_names(["a", "b"])
    assert names == {"a": "A社"}
    err = capsys.readouterr().err
    assert "2件中 1件" in err


def test_collect_skips_detail_of_for_unchanged_continuing(monkeypatch):
    """金額変動のない継続発行は detail_of(/transactions)をスキップし API 負荷を抑える。"""
    prev = [_billing("gap", 1000), _billing("same", 500), _billing("chg", 200)]
    curr = [_billing("same", 500), _billing("chg", 900), _billing("new", 300)]
    calls = _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    # detail_of は注目顧客 (発行漏れ候補 gap / 変動継続 chg / 今月新規 new) の billing_id のみ。
    assert set(calls["detail_of"]) == {"b-gap", "b-chg", "b-new"}
    assert "b-same" not in calls["detail_of"]
    # スキップした same は product_name 空・updated_at None。
    same = [r for r in rows if r["customer_id"] == "same"][0]
    assert same["product_name"] == "" and same["updated_at"] is None


def test_collect_suppresses_annual_period_gap_with_injected_contract_months(monkeypatch):
    """年間契約抑制 (配線): 初回契約月から12ヶ月の年間契約期間中の発行漏れ候補を除外する。

    initial_contract_months を DI で与え、年間期間中の顧客は gap_candidates / rows から落ち、
    初回契約月が空/不明の顧客は従来どおり発行漏れ候補に残ることを検証する。
    """
    # 前月のみ発行 (今月未発行) = 発行漏れ候補になる 2 顧客。
    prev = [_billing("annual", 1000), _billing("unknown", 2000)]
    curr = []
    _patch_collect_api(monkeypatch, prev, curr)
    # annual は当月 (2026-06) 契約 → 年間契約期間中 → 抑制。unknown は初回契約月なし → 残す。
    contract_months = {"annual": {"initial_contract_month": "2026-06", "payment_cycle": "年間払い"}}
    res, rows = c.collect("2026-06", initial_contract_months=contract_months)

    # 年間契約期間中の annual は発行漏れ候補から除外され、rows にも出ない。
    assert res["gap_candidates"] == ["unknown"]
    assert res["suppressed_annual"] == ["annual"]
    gap_cids = {r["customer_id"] for r in rows if r["verdict"] == "発行漏れ候補"}
    assert gap_cids == {"unknown"}
    assert "annual" not in {r["customer_id"] for r in rows}


def test_collect_keeps_gap_when_contract_month_blank(monkeypatch):
    """初回契約月が空/未登録の顧客は年間抑制されず従来どおり発行漏れ候補に残る (fail-safe)。"""
    prev = [_billing("nomonth", 500)]
    curr = []
    _patch_collect_api(monkeypatch, prev, curr)
    # 空文字の初回契約月は billing_lifecycle が in_annual=False を返し抑制対象外。
    res, rows = c.collect("2026-06", initial_contract_months={
        "nomonth": {"initial_contract_month": "", "payment_cycle": "年間払い"}
    })
    assert res["gap_candidates"] == ["nomonth"]
    assert res["suppressed_annual"] == []
    assert "nomonth" in {r["customer_id"] for r in rows if r["verdict"] == "発行漏れ候補"}


def test_collect_loads_contract_months_from_notion_when_not_injected(monkeypatch):
    """initial_contract_months 未指定時は config の database_id で Notion から取得して抑制に使う。

    _patch_collect_api の _load_initial_contract_months スタブを使わず、本来の取得経路
    (load_config → fetch_initial_contract_months) を通して年間抑制が配線されていることを確認する。
    """
    prev = [_billing("annual", 1000), _billing("monthly", 2000)]
    curr = []
    # API 部分だけ差し替え、_load_initial_contract_months は本物のまま残す。
    monkeypatch.setattr(c, "fetch_issued",
                        lambda ym: prev if ym == c.prev_month("2026-06") else curr)
    monkeypatch.setattr(c, "resolve_names", lambda ids: {cid: f"会社{cid}" for cid in ids})
    monkeypatch.setattr(c, "detail_of",
                        lambda bid: {"product_name": f"商品-{bid}", "updated_at": None})
    # 取得経路を上書きし annual を年間契約期間中の初回契約月にする。
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(c.notion_invoice_sink, "fetch_initial_contract_months",
                        lambda db_id: {
                            "annual": {"initial_contract_month": "2026-06",
                                       "payment_cycle": "年間払い"}
                        })
    res, _rows = c.collect("2026-06")
    assert res["suppressed_annual"] == ["annual"]
    assert res["gap_candidates"] == ["monthly"]


def test_load_initial_contract_months_skips_when_no_db_id(capsys):
    """database_id 未設定なら空 dict を返し抑制スキップを stderr に1行出す。"""
    assert c._load_initial_contract_months(None) == {}
    err = capsys.readouterr().err
    assert "年間契約抑制をスキップ" in err


def test_load_initial_contract_months_swallows_fetch_failure(monkeypatch, capsys):
    """Notion 取得失敗時も例外を握りつぶし空 dict + stderr 警告で collect を止めない。"""
    def boom(db_id):
        raise RuntimeError("notion down")
    monkeypatch.setattr(c.notion_invoice_sink, "fetch_initial_contract_months", boom)
    assert c._load_initial_contract_months("db1") == {}
    assert "年間契約抑制をスキップ" in capsys.readouterr().err


def test_collect_aggregates_details_for_multiple_billings_same_customer(monkeypatch):
    """同一顧客に複数 billing がある場合、金額だけでなく商品名/発行日も対象全体から集約する。"""
    prev = [
        _billing("gap", 1000, bid="b-gap-1", issue_date="2026-05-10"),
        _billing("gap", 2000, bid="b-gap-2", issue_date="2026-05-20"),
    ]
    curr = []
    calls = _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    gap = rows[0]

    assert gap["customer_id"] == "gap"
    assert gap["prev_amount"] == 3000
    assert gap["product_name"] == "商品-b-gap-1 / 商品-b-gap-2"
    assert gap["issue_date"] == "2026-05-20"
    assert set(calls["detail_of"]) == {"b-gap-1", "b-gap-2"}


# --- 改修2: backfill 範囲一括投入 ---

def _row(cid, ym, verdict, prev_amt, curr_amt):
    """collect が返す行と同形 (全キーあり) のテスト用 row。_print_summary が落ちないよう全キー埋める。"""
    return {"customer_id": cid, "period_ym": ym, "company_name": f"会社{cid}",
            "verdict": verdict, "product_name": "", "prev_amount": prev_amt,
            "curr_amount": curr_amt, "issue_date": "2026-06-10", "updated_at": None}


# --- 既定対象月 = 実行日の年月。対象年月 == 今月、前月はその1つ前 ---

def test_default_target_month_is_current_calendar_month():
    """6月のいつ実行しても既定の対象年月/今月は 2026-06。"""
    assert c.default_target_month(datetime.date(2026, 6, 1)) == "2026-06"
    assert c.default_target_month(datetime.date(2026, 6, 22)) == "2026-06"
    assert c.default_target_month(datetime.date(2026, 6, 30)) == "2026-06"


def test_default_target_month_boundary_end_of_month():
    """6/30 23:59 までは6月、7/1 0:00以降は7月として扱う。"""
    assert c.default_target_month(datetime.datetime(2026, 6, 30, 23, 59)) == "2026-06"
    assert c.default_target_month(datetime.datetime(2026, 7, 1, 0, 0)) == "2026-07"


def test_default_target_month_crosses_year_boundary():
    assert c.default_target_month(datetime.date(2026, 1, 15)) == "2026-01"
    assert c.prev_month(c.default_target_month(datetime.date(2026, 1, 15))) == "2025-12"


def test_default_target_month_label_equals_curr_and_prev_is_one_back():
    """既定対象月では period_ym(対象年月ラベル)==今月、前月は1つ前。

    6/30 実行 → 対象年月=2026-06、今月金額=6月、前月金額=5月。
    """
    ym = c.default_target_month(datetime.date(2026, 6, 30))
    assert ym == "2026-06"            # 対象年月ラベル = 今月 = 6月
    assert c.prev_month(ym) == "2026-05"  # 比較する前月金額 = 5月


def test_month_iter_ascending_inclusive():
    assert list(c.month_iter("2026-05", "2026-08")) == ["2026-05", "2026-06", "2026-07", "2026-08"]
    assert list(c.month_iter("2025-11", "2026-02")) == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert list(c.month_iter("2026-06", "2026-06")) == ["2026-06"]
    assert list(c.month_iter("2026-08", "2026-05")) == []  # from > to は空


def test_backfill_processes_each_month_ascending(monkeypatch):
    """backfill は範囲の各月を昇順で collect→sink する。"""
    seen = []

    def fake_collect(ym):
        seen.append(("collect", ym))
        rows = [_row("same", ym, "継続発行", 500, 500)]
        res = {"gap_candidates": [], "continuing": ["same"], "new_this_month": [],
               "prev_amount": {"same": 500}, "curr_amount": {"same": 500}}
        return res, rows

    sink_calls = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sink_calls.append(period_ym)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    rc = c.backfill("2026-04", "2026-06", "db123")
    assert rc == 0
    # collect と sink が 4,5,6 月の昇順で呼ばれた。
    assert [ym for _, ym in seen] == ["2026-04", "2026-05", "2026-06"]
    assert sink_calls == ["2026-04", "2026-05", "2026-06"]


def test_backfill_skips_gap_candidates_by_default(monkeypatch):
    """既定 backfill は未検証の発行漏れ候補をスキップし、継続発行/今月新規のみ投入する。"""
    def fake_collect(ym):
        rows = [
            _row("gap", ym, "発行漏れ候補", 1000, None),
            _row("same", ym, "継続発行", 500, 500),
            _row("new", ym, "今月新規", None, 300),
        ]
        res = {"gap_candidates": ["gap"], "continuing": ["same"], "new_this_month": ["new"],
               "prev_amount": {"gap": 1000, "same": 500}, "curr_amount": {"same": 500, "new": 300}}
        return res, rows

    sunk = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sunk.extend(r["verdict"] for r in rows)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    assert c.backfill("2026-06", "2026-06", "db123") == 0
    # 発行漏れ候補は投入されず、継続発行/今月新規のみ。
    assert "発行漏れ候補" not in sunk
    assert set(sunk) == {"継続発行", "今月新規"}


def test_backfill_force_unverified_includes_gaps(monkeypatch):
    """--force-unverified 時は発行漏れ候補も未検証のまま投入する。"""
    def fake_collect(ym):
        rows = [_row("gap", ym, "発行漏れ候補", 1000, None)]
        res = {"gap_candidates": ["gap"], "continuing": [], "new_this_month": [],
               "prev_amount": {"gap": 1000}, "curr_amount": {}}
        return res, rows

    sunk = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sunk.extend(r["verdict"] for r in rows)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    assert c.backfill("2026-06", "2026-06", "db123", force_unverified=True) == 0
    assert sunk == ["発行漏れ候補"]


# --- main() dispatch (CLI 分岐の網羅) ---

def _fake_collect_continuing(ym):
    """継続発行1件を返す collect スタブ (period_ym=ym, 全キー埋め)。"""
    rows = [_row("same", ym, "継続発行", 500, 500)]
    res = {"gap_candidates": [], "continuing": ["same"], "new_this_month": [],
           "prev_amount": {"same": 500}, "curr_amount": {"same": 500}}
    return res, rows


def test_main_default_collect_writes_candidates(monkeypatch, tmp_path):
    """引数なし → 既定 collect。実行日の年月を対象に候補 JSON を書き出し 0 で終わる。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(c, "collect", _fake_collect_continuing)
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py"])
    assert c.main() == 0
    out = tmp_path / "eval-log" / "mfk-gap-candidates.json"
    assert out.exists()
    rows = json.loads(out.read_text(encoding="utf-8"))
    # 既定対象月 = 実行日の年月 が period_ym に入る。
    assert rows and rows[0]["period_ym"] == c.default_target_month()


def test_main_finalize_dispatch(monkeypatch, tmp_path):
    """--finalize → 候補を確定リストへ昇格 (誤検出 customer_id を除外)。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    cand = tmp_path / "eval-log" / "mfk-gap-candidates.json"
    os.makedirs(cand.parent, exist_ok=True)
    cand.write_text(json.dumps([
        {"customer_id": "c1", "period_ym": "2026-05", "company_name": "A社",
         "verdict": "発行漏れ候補", "product_name": "SaaS",
         "prev_amount": 100, "curr_amount": None},
        {"customer_id": "c2", "period_ym": "2026-05", "company_name": "B社",
         "verdict": "発行漏れ候補", "product_name": "SaaS",
         "prev_amount": 200, "curr_amount": None},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--finalize", "--exclude-ids", "c2"])
    assert c.main() == 0
    verified = json.loads((tmp_path / "eval-log" / "mfk-gap-verified.json").read_text(encoding="utf-8"))
    assert {r["customer_id"] for r in verified} == {"c1"}


def test_main_sink_fails_closed_without_db_id(monkeypatch, tmp_path):
    """--sink で notion.database_id 未設定なら fail-closed (exit 2)。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    verified = tmp_path / "eval-log" / "mfk-gap-verified.json"
    os.makedirs(verified.parent, exist_ok=True)
    verified.write_text(json.dumps(
        [{"customer_id": "c1", "period_ym": "2026-05", "company_name": "A社",
          "verdict": "継続発行", "product_name": "",
          "prev_amount": 100, "curr_amount": 100}]), encoding="utf-8")
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {}})
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink"])
    assert c.main() == 2


def test_main_sink_success(monkeypatch, tmp_path):
    """--sink で確定リストを顧客IDキーで upsert し period_ym を確定リストから採る。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    verified = tmp_path / "eval-log" / "mfk-gap-verified.json"
    os.makedirs(verified.parent, exist_ok=True)
    verified.write_text(json.dumps(
        [{"customer_id": "c1", "period_ym": "2026-05", "company_name": "A社",
          "verdict": "継続発行", "product_name": "",
          "prev_amount": 100, "curr_amount": 100}]), encoding="utf-8")
    calls = []
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(c.notion_invoice_sink, "upsert",
                        lambda db_id, rows, period_ym=None: calls.append((db_id, period_ym))
                        or {"created": 1, "updated": 0, "period_ym": period_ym, "run_id": "rid"})
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink"])
    assert c.main() == 0
    assert calls == [("db1", "2026-05")]


def test_main_sink_rejects_month_mismatch(monkeypatch, tmp_path):
    """--sink --month は rows の period_ym と一致しない場合に表示/投入のズレを拒否する。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    verified = tmp_path / "eval-log" / "mfk-gap-verified.json"
    os.makedirs(verified.parent, exist_ok=True)
    verified.write_text(json.dumps(
        [{"customer_id": "c1", "period_ym": "2026-05", "verdict": "継続発行"}]), encoding="utf-8")
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink", "--month", "2026-06"])
    assert c.main() == 2


def test_main_collect_rejects_nonexistent_month(monkeypatch):
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--collect", "--month", "2026-13"])
    assert c.main() == 2


def test_main_sink_rejects_missing_verified(monkeypatch, tmp_path):
    """確定リストが不在なら二段確認前として exit 2 (fail-closed)。"""
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--sink"])
    assert c.main() == 2


def test_main_backfill_requires_from_to(monkeypatch):
    monkeypatch.setattr(c.sys, "argv", ["check_invoice_gaps.py", "--backfill"])
    assert c.main() == 2


def test_main_backfill_month_is_exclusive(monkeypatch):
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-04",
                         "--to", "2026-06", "--month", "2026-05"])
    assert c.main() == 2


def test_main_backfill_rejects_bad_format(monkeypatch):
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-4", "--to", "2026-06"])
    assert c.main() == 2


def test_main_backfill_rejects_nonexistent_month(monkeypatch):
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-00", "--to", "2026-06"])
    assert c.main() == 2


def test_main_backfill_rejects_from_after_to(monkeypatch):
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-08", "--to", "2026-05"])
    assert c.main() == 2


def test_main_backfill_success(monkeypatch):
    """--backfill 正常系: 範囲を月昇順に collect→sink し 0 終了。"""
    monkeypatch.setattr(c, "collect", _fake_collect_continuing)
    seen = []
    monkeypatch.setattr(c.notion_invoice_sink, "upsert",
                        lambda db_id, rows, period_ym=None: seen.append(period_ym)
                        or {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"})
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-04", "--to", "2026-06"])
    assert c.main() == 0
    assert seen == ["2026-04", "2026-05", "2026-06"]


def test_main_backfill_fails_closed_without_db_id(monkeypatch):
    monkeypatch.setattr(c, "load_config", lambda: {"notion": {}})
    monkeypatch.setattr(c.sys, "argv",
                        ["check_invoice_gaps.py", "--backfill", "--from", "2026-04", "--to", "2026-06"])
    assert c.main() == 2


# --- LS-05: schema ↔ validate_rows の二重定義 parity (将来ドリフト検出) ---

def _gap_schema():
    """invoice-gap-result.schema.json を読み込む (jsonschema 依存を増やさず標準 json のみ)。"""
    here = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(
        here, "..", "skills", "run-mf-invoice-check", "schemas",
        "invoice-gap-result.schema.json")
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def test_schema_properties_match_validate_rows_allowed_keys():
    """schema の items.properties キー集合 = check_invoice_gaps._ALLOWED_ROW_KEYS。

    additionalProperties:false の schema と validate_rows の許可キー集合が二重定義に
    なっており、片方だけ列を足す/消すと sink/finalize の検証が schema とずれる。
    両者のキー集合一致を CI で固定し、将来のドリフトを機械検出する。
    """
    schema = _gap_schema()
    schema_props = set(schema["items"]["properties"].keys())
    assert schema_props == c._ALLOWED_ROW_KEYS, (
        f"schema properties と validate_rows 許可キーが不一致: "
        f"schema のみ={schema_props - c._ALLOWED_ROW_KEYS}, "
        f"validate_rows のみ={c._ALLOWED_ROW_KEYS - schema_props}")


def test_schema_required_matches_validate_rows_mandatory_keys():
    """schema の items.required = validate_rows が『必須キー不足』を強制するキー集合。

    validate_rows は customer_id/period_ym/verdict を個別チェックし、加えて
    company_name/product_name/prev_amount/curr_amount を『必須キー不足』として要求する。
    schema 側 required との集合一致を固定し、必須条件のドリフトを検出する。
    """
    schema = _gap_schema()
    schema_required = set(schema["items"]["required"])
    # validate_rows が必須として扱うキー = 個別必須チェック + 「必須キー不足」ループ対象。
    validate_required = (
        {"customer_id", "period_ym", "verdict"}            # 個別の空/形式/enum チェック
        | {"company_name", "product_name", "prev_amount", "curr_amount"}  # 必須キー不足ループ
    )
    assert schema_required == validate_required, (
        f"schema required と validate_rows 必須キーが不一致: "
        f"schema のみ={schema_required - validate_required}, "
        f"validate_rows のみ={validate_required - schema_required}")


# --- 残骸検知の画面昇格: _warn_residual_to_screen (to-human フィードバックの出口) ---

def test_warn_residual_to_screen_prints_on_residual(capsys):
    """residual があれば⚠行を stdout に出し /run-mf-invoice-db-setup へ誘導する。"""
    c._warn_residual_to_screen({"residual": ["全体トータル"], "suspect_summary": []})
    out = capsys.readouterr().out
    assert "⚠" in out
    assert "全体トータル" in out
    assert "/run-mf-invoice-db-setup" in out


def test_warn_residual_to_screen_prints_on_suspect(capsys):
    """集計疑い extra (suspect_summary) があっても⚠行を stdout に出す。"""
    c._warn_residual_to_screen({"residual": [], "suspect_summary": ["月次サマリ"]})
    out = capsys.readouterr().out
    assert "⚠" in out
    assert "月次サマリ" in out


def test_warn_residual_to_screen_merges_residual_and_suspect(capsys):
    """residual と suspect の両方を重複なくマージして1行で表示する。"""
    c._warn_residual_to_screen(
        {"residual": ["全体トータル"], "suspect_summary": ["全体トータル", "総計"]})
    out = capsys.readouterr().out
    assert out.count("⚠") == 1
    assert "全体トータル" in out and "総計" in out


def test_warn_residual_to_screen_silent_when_clean(capsys):
    """residual も suspect も無ければ何も出さない (誤誘導しない)。"""
    c._warn_residual_to_screen({"residual": [], "suspect_summary": []})
    assert capsys.readouterr().out == ""


def test_warn_residual_to_screen_silent_on_missing_keys(capsys):
    """旧形式の upsert 戻り (新キー無し) でも KeyError にならず無出力 (後方互換)。"""
    c._warn_residual_to_screen({"created": 1, "updated": 0})
    assert capsys.readouterr().out == ""
