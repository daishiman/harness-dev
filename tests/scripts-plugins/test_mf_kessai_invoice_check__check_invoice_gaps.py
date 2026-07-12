"""Genuine functional tests for
plugins/mf-kessai-invoice-check/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py.

network/Notion/keychain は一切叩かない。check_invoice_gaps が import する lib 関数
(mfk_api.get / mfk_api.iter_all / mfk_api.load_config / notion_invoice_sink.upsert) を
monkeypatch でメモリ stub に差し替え、

- 純関数 (validate_rows / month_range / prev_month / by_customer)
- 集約ロジック (resolve_names / detail_of / fetch_issued / collect / _print_summary)
- finalize (確定リスト昇格・誤検出除外・schema 違反 fail)
- main() の collect / finalize / sink 各サブコマンド (in-process で argv 駆動)

を実入出力で検査する。すべて MFK_OUTPUT_DIR=tmp_path で repo を汚さない。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "mf-kessai-invoice-check"
SCRIPT = PLUGIN / "skills" / "run-mf-invoice-check" / "scripts" / "check_invoice_gaps.py"

# lib を import path に通してから実ファイルからロード (check_invoice_gaps が lib import するため)
sys.path.insert(0, str(PLUGIN / "lib"))
_SPEC = importlib.util.spec_from_file_location("check_invoice_gaps_s3", SCRIPT)
CIG = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CIG)


# ===================== 純関数 =====================

def test_month_range():
    assert CIG.month_range("2026-02") == ("2026-02-01", "2026-02-28")
    assert CIG.month_range("2024-02") == ("2024-02-01", "2024-02-29")  # 閏年
    assert CIG.month_range("2026-12") == ("2026-12-01", "2026-12-31")


def test_prev_month_normal_and_year_rollover():
    assert CIG.prev_month("2026-06") == "2026-05"
    assert CIG.prev_month("2026-01") == "2025-12"  # 年跨ぎ


def test_billings_by_customer_groups_all():
    # by_customer は billings_by_customer に改名。後勝ち先勝ちの単一 dict ではなく
    # 顧客ごとに全 billing を list へ集約する (setdefault(...).append) 新仕様。
    billings = [
        {"customer_id": "c1", "id": "b1"},
        {"customer_id": "c1", "id": "b2"},  # 同一顧客は両方 list に残る
        {"customer_id": "c2", "id": "b3"},
    ]
    out = CIG.billings_by_customer(billings)
    assert [b["id"] for b in out["c1"]] == ["b1", "b2"]  # 入力順を保持
    assert [b["id"] for b in out["c2"]] == ["b3"]


def test_validate_rows_ok():
    # validate_rows は company_name/product_name/prev_amount/curr_amount を必須化し、
    # verdict 別に金額型を強制する (発行漏れ候補: prev=int, curr=null)。
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
             "verdict": "発行漏れ候補", "product_name": "SaaS",
             "prev_amount": 100, "curr_amount": None}]
    assert CIG.validate_rows(rows) == []


def test_validate_rows_not_a_list():
    assert CIG.validate_rows({"a": 1}) == ["入力が配列でない"]


def test_validate_rows_collects_all_violations():
    rows = [{"customer_id": "", "period_ym": "26-6", "verdict": "謎"}]
    errs = CIG.validate_rows(rows)
    assert any("customer_id" in e for e in errs)
    assert any("period_ym" in e for e in errs)
    assert any("verdict" in e for e in errs)


def test_validate_rows_accepts_all_enum_verdicts():
    # 各 verdict は固有の金額契約を満たす完全な行で受理される。
    base = {"customer_id": "c", "period_ym": "2026-06", "company_name": "A社",
            "product_name": "SaaS"}
    amounts = {
        "発行漏れ候補": {"prev_amount": 100, "curr_amount": None},
        "継続発行": {"prev_amount": 100, "curr_amount": 200},
        "今月新規": {"prev_amount": None, "curr_amount": 300},
    }
    for v, amt in amounts.items():
        rows = [{**base, "verdict": v, **amt}]
        assert CIG.validate_rows(rows) == [], v


# ===================== 出力先解決 (F2) =====================

def test_eval_log_dir_env_first(monkeypatch):
    monkeypatch.setenv("MFK_OUTPUT_DIR", "/tmp/mfk-a")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert CIG.eval_log_dir() == "/tmp/mfk-a/eval-log"


def test_eval_log_dir_project_fallback(monkeypatch):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert CIG.eval_log_dir() == "/tmp/mfk-b/eval-log"


def test_eval_log_dir_cwd_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert CIG.eval_log_dir() == os.path.join(str(tmp_path), "eval-log")


def test_candidates_and_verified_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    assert CIG.candidates_path() == str(tmp_path / "eval-log" / "mfk-gap-candidates.json")
    assert CIG.verified_path() == str(tmp_path / "eval-log" / "mfk-gap-verified.json")


# ===================== resolve_names (mfk_api.get を stub) =====================

def test_resolve_names_chunks_and_maps(monkeypatch):
    seen_chunks = []

    def fake_get(path, params=None):
        assert path == "/customers"
        ids = params["ids"]
        seen_chunks.append(len(ids))
        return {"items": [{"id": cid, "name": f"会社{cid}"} for cid in ids]}

    monkeypatch.setattr(CIG, "get", fake_get)
    ids = [f"c{i}" for i in range(250)]  # 200 超で 2 チャンクに分割
    names = CIG.resolve_names(set(ids))
    assert seen_chunks == [200, 50]
    assert names["c0"] == "会社c0"
    assert len(names) == 250


def test_resolve_names_warns_on_total_failure(monkeypatch, capsys):
    monkeypatch.setattr(CIG, "get", lambda path, params=None: {"items": []})
    names = CIG.resolve_names({"c1", "c2"})
    assert names == {}
    assert "1件も解決できませんでした" in capsys.readouterr().err


def test_resolve_names_empty_input_no_warning(monkeypatch, capsys):
    monkeypatch.setattr(CIG, "get", lambda path, params=None: {"items": []})
    assert CIG.resolve_names(set()) == {}
    assert capsys.readouterr().err == ""


# ===================== detail_of (transactions を stub) =====================

def test_detail_of_picks_latest_updated_and_descs(monkeypatch):
    def fake_get(path, params=None):
        assert path == "/transactions"
        assert params["billing_id"] == "b1"
        return {"items": [
            {"created_at": "2026-06-01T00:00:00Z",
             "transaction_details": [{"description": "商品A"}, {"description": "商品B"}]},
            {"created_at": "2026-06-10T00:00:00Z",
             "transaction_details": [{"description": "商品C"}, {"description": ""},
                                     {"description": "商品D"}]},
        ]}

    monkeypatch.setattr(CIG, "get", fake_get)
    det = CIG.detail_of("b1")
    assert det["updated_at"] == "2026-06-10T00:00:00Z"  # 最新 created_at
    # 先頭3明細のみ・空 description は除外
    assert det["product_name"] == "商品A / 商品B / 商品C"


def test_detail_of_empty_billing_id_short_circuits(monkeypatch):
    # billing_id が無ければ API を呼ばず空を返す
    monkeypatch.setattr(CIG, "get", lambda *a, **k: pytest.fail("get must not be called"))
    assert CIG.detail_of(None) == {"product_name": "", "updated_at": None}
    assert CIG.detail_of("") == {"product_name": "", "updated_at": None}


# ===================== fetch_issued (iter_all を stub) =====================

def test_fetch_issued_passes_date_window(monkeypatch):
    # 月帰属=transaction.date 改修: issue_date 窓は対象月初〜翌月末で over-fetch し、
    # 各 billing の /transactions を transaction.date で対象月へ絞る。
    captured = {}

    def fake_iter_all(path, params=None):
        if path == "/transactions":
            return iter([{"date": "2026-06-30",
                          "transaction_details": [{"description": "6月分", "amount": 0}]}])
        captured["path"] = path
        captured["params"] = params
        return iter([{"id": "b1", "customer_id": "c1", "status": "invoice_issued"}])

    monkeypatch.setattr(CIG, "iter_all", fake_iter_all)
    out = CIG.fetch_issued("2026-06")
    assert captured["path"] == "/billings/qualified"
    assert captured["params"]["issue_date_from"] == "2026-06-01"
    assert captured["params"]["issue_date_to"] == "2026-07-31"
    assert captured["params"]["status"] == "invoice_issued"
    assert [r["customer_id"] for r in out] == ["c1"]


# ===================== collect (全 API を stub) =====================

def _wire_collect(monkeypatch, prev_billings, curr_billings, names_map):
    """fetch_issued/resolve_names/detail_of を月別 stub で配線する。

    fetch_issued は transaction.date 基準へ改修されたため /billings/qualified に加え各 billing の
    /transactions も stub する。billing ごとに対象月 (prev=2026-05 / curr=2026-06) の取引を 1 件返し、
    明細金額の合計を元 billing の amount に一致させて、fetch_issued の amount 再計算後も
    prev_amount/curr_amount の期待値を保つ。
    """
    txn_by_billing = {}
    for b in prev_billings:
        txn_by_billing[b["id"]] = ("2026-05", b.get("amount", 0))
    for b in curr_billings:
        txn_by_billing[b["id"]] = ("2026-06", b.get("amount", 0))

    def fake_iter_all(path, params=None):
        if path == "/transactions":
            month, amount = txn_by_billing.get(params["billing_id"], ("2026-06", 0))
            return iter([{"date": f"{month}-15",
                          "transaction_details": [{"description": "明細", "amount": amount}]}])
        # /billings/qualified: issue_date_from の月で前月/今月を見分ける
        if params["issue_date_from"].startswith("2026-05"):
            return iter(prev_billings)
        return iter(curr_billings)

    monkeypatch.setattr(CIG, "iter_all", fake_iter_all)
    monkeypatch.setattr(CIG, "resolve_names", lambda ids: {i: names_map.get(i, "") for i in ids})

    def fake_get(path, params=None):
        # detail_of 用 transactions
        return {"items": [{"created_at": "2026-06-05T00:00:00Z",
                           "transaction_details": [{"description": "明細"}]}]}

    monkeypatch.setattr(CIG, "get", fake_get)
    # collect は initial_contract_months=None のとき load_config の database_id で
    # Notion から初回契約月を取得する。テストがネットワーク/Notion に出ないよう空 dict に固定
    # (空 dict = 年間契約抑制スキップ = 全候補が発行漏れ候補に残る従来挙動)。
    monkeypatch.setattr(CIG, "_load_initial_contract_months", lambda db_id: {})


def test_collect_classifies_gap_continuing_new(monkeypatch):
    prev = [
        {"customer_id": "gap", "id": "pg", "status": "invoice_issued",
         "amount": 1000, "issue_date": "2026-05-01"},
        {"customer_id": "cont", "id": "pc", "status": "invoice_issued",
         "amount": 500, "issue_date": "2026-05-02"},
    ]
    curr = [
        {"customer_id": "cont", "id": "cc", "status": "invoice_issued",
         "amount": 800, "issue_date": "2026-06-02"},  # 金額変動
        {"customer_id": "new", "id": "cn", "status": "invoice_issued",
         "amount": 300, "issue_date": "2026-06-03"},
    ]
    _wire_collect(monkeypatch, prev, curr, {"gap": "Gap社", "cont": "Cont社"})
    res, rows = CIG.collect("2026-06")
    assert res["gap_candidates"] == ["gap"]
    assert res["continuing"] == ["cont"]
    assert res["new_this_month"] == ["new"]
    verdicts = {r["customer_id"]: r["verdict"] for r in rows}
    assert verdicts["gap"] == "発行漏れ候補"
    assert verdicts["cont"] == "継続発行"  # 金額変動したので行に入る
    gap_row = [r for r in rows if r["customer_id"] == "gap"][0]
    assert gap_row["company_name"] == "Gap社"
    assert gap_row["prev_amount"] == 1000
    assert gap_row["curr_amount"] is None
    cont_row = [r for r in rows if r["customer_id"] == "cont"][0]
    assert cont_row["prev_amount"] == 500
    assert cont_row["curr_amount"] == 800


def test_collect_skips_detail_for_unchanged_continuing(monkeypatch):
    # 改修1で継続発行は金額変動の有無に関わらず全件 rows 化されるようになった。
    # 金額不変の継続発行も「チェック証跡」として行は残るが、detail_of(/transactions)は
    # スキップされ product_name 空・updated_at None で金額のみ記録する (元テストの
    # 『行を作らない』意図は『詳細取得をスキップする』に変わった)。
    prev = [{"customer_id": "cont", "id": "p", "status": "invoice_issued", "amount": 500}]
    curr = [{"customer_id": "cont", "id": "c", "status": "invoice_issued", "amount": 500}]
    _wire_collect(monkeypatch, prev, curr, {"cont": "Cont社"})
    res, rows = CIG.collect("2026-06")
    assert res["continuing"] == ["cont"]
    cont = [r for r in rows if r["customer_id"] == "cont"]
    assert len(cont) == 1
    assert cont[0]["verdict"] == "継続発行"
    assert cont[0]["prev_amount"] == 500 and cont[0]["curr_amount"] == 500
    # 金額不変なので detail_of をスキップ: 商品名空・更新日 None。
    assert cont[0]["product_name"] == "" and cont[0]["updated_at"] is None


def test_print_summary_output(monkeypatch, capsys):
    # _print_summary は amount_changed(res["continuing"], res["prev_amount"],
    # res["curr_amount"]) で金額変動件数を出すため、res に金額マップが必要。
    # c1 は 200→250 で変動、c2 は不変。
    res = {"gap_candidates": ["g1"], "continuing": ["c1", "c2"], "new_this_month": ["n1"],
           "prev_amount": {"c1": 200, "c2": 300}, "curr_amount": {"c1": 250, "c2": 300}}
    rows = [
        {"verdict": "発行漏れ候補", "company_name": "G社", "customer_id": "g1",
         "product_name": "商品", "prev_amount": 100, "curr_amount": None},
        {"verdict": "継続発行", "company_name": "C社", "customer_id": "c1",
         "product_name": "継続商品", "prev_amount": 200, "curr_amount": 250},
    ]
    CIG._print_summary("2026-06", res, rows)
    out = capsys.readouterr().out
    assert "発行漏れチェック 2026-05 → 2026-06" in out
    assert "発行漏れ候補: 1件" in out
    assert "継続発行(全件): 2件 (うち金額変動: 1件)" in out
    assert "今月新規: 1件" in out
    assert "[発行漏れ候補] G社(g1)" in out


# ===================== finalize (F1) =====================

def _cands_file(tmp_path):
    # validate_rows の必須キー (company_name/product_name/prev_amount/curr_amount) と
    # verdict 別の金額契約を満たす完全な候補行を書き出す。
    p = tmp_path / "cands.json"
    p.write_text(json.dumps([
        {"customer_id": "c1", "period_ym": "2026-06", "company_name": "A社",
         "verdict": "発行漏れ候補", "product_name": "SaaS",
         "prev_amount": 100, "curr_amount": None},
        {"customer_id": "c2", "period_ym": "2026-06", "company_name": "B社",
         "verdict": "発行漏れ候補", "product_name": "SaaS",
         "prev_amount": 200, "curr_amount": None},
        {"customer_id": "c3", "period_ym": "2026-06", "company_name": "C社",
         "verdict": "継続発行", "product_name": "", "prev_amount": 300, "curr_amount": 300},
    ], ensure_ascii=False), encoding="utf-8")
    return p


def test_finalize_excludes_false_positive(tmp_path, capsys):
    src = _cands_file(tmp_path)
    out = tmp_path / "sub" / "verified.json"  # 親ディレクトリ自動生成も検証
    rc = CIG.finalize(["c2"], str(src), str(out))
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert {r["customer_id"] for r in kept} == {"c1", "c3"}
    msg = capsys.readouterr().out
    assert "誤検出除外 1件" in msg


def test_finalize_no_exclusions_keeps_all(tmp_path):
    src = _cands_file(tmp_path)
    out = tmp_path / "v.json"
    assert CIG.finalize([""], str(src), str(out)) == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 3


def test_finalize_does_not_exclude_continuing(tmp_path):
    src = _cands_file(tmp_path)
    out = tmp_path / "v.json"
    CIG.finalize(["c3"], str(src), str(out))  # c3 は継続発行 → 除外対象外
    assert "c3" in {r["customer_id"] for r in json.loads(out.read_text(encoding="utf-8"))}


def test_finalize_rejects_schema_violation(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"customer_id": "x", "period_ym": "", "verdict": "発行漏れ候補"}]),
                   encoding="utf-8")
    out = tmp_path / "v.json"
    assert CIG.finalize([], str(bad), str(out)) == 2
    assert not out.exists()
    assert "schema 違反" in capsys.readouterr().err


# ===================== main() in-process (collect/finalize/sink) =====================

def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["check_invoice_gaps.py", *args])


def _valid_row(cid="c1", ym="2026-06"):
    """validate_rows を通る完全な発行漏れ候補行 (必須キー + verdict 別金額契約を満たす)。"""
    return {"customer_id": cid, "period_ym": ym, "company_name": "A社",
            "verdict": "発行漏れ候補", "product_name": "SaaS",
            "prev_amount": 100, "curr_amount": None}


def test_main_collect_writes_candidates(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    prev = [{"customer_id": "gap", "id": "pg", "status": "invoice_issued", "amount": 100}]
    curr = []
    _wire_collect(monkeypatch, prev, curr, {"gap": "Gap社"})
    _argv(monkeypatch, "--collect", "--month", "2026-06")
    assert CIG.main() == 0
    cand = json.loads((tmp_path / "eval-log" / "mfk-gap-candidates.json").read_text(encoding="utf-8"))
    assert len(cand) == 1
    assert cand[0]["customer_id"] == "gap"
    out = capsys.readouterr().out
    assert "候補を" in out


def test_main_collect_default_month(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    _wire_collect(monkeypatch, [], [], {})
    _argv(monkeypatch, "--collect")  # --month 無し → 実行月
    assert CIG.main() == 0
    assert (tmp_path / "eval-log" / "mfk-gap-candidates.json").exists()


def test_main_collect_custom_out(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    _wire_collect(monkeypatch, [], [], {})
    out = tmp_path / "nest" / "custom.json"
    _argv(monkeypatch, "--collect", "--month", "2026-06", "--out", str(out))
    assert CIG.main() == 0
    assert out.exists()


def test_main_finalize_via_argv(monkeypatch, tmp_path):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    src = _cands_file(tmp_path)
    out = tmp_path / "verified.json"
    _argv(monkeypatch, "--finalize", "--input", str(src), "--out", str(out),
          "--exclude-ids", "c2,c2")
    assert CIG.main() == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert {r["customer_id"] for r in kept} == {"c1", "c3"}


def test_main_finalize_default_paths(monkeypatch, tmp_path):
    # --input/--out 省略時は candidates_path()/verified_path() を使う
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    (eval_dir / "mfk-gap-candidates.json").write_text(
        json.dumps([_valid_row()], ensure_ascii=False), encoding="utf-8")
    _argv(monkeypatch, "--finalize")
    assert CIG.main() == 0
    assert (eval_dir / "mfk-gap-verified.json").exists()


def test_main_sink_fail_closed_without_verified(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    _argv(monkeypatch, "--sink")
    assert CIG.main() == 2  # 確定リスト不在で fail-closed
    assert "確定リスト" in capsys.readouterr().err


def test_main_sink_schema_violation(monkeypatch, tmp_path, capsys):
    # 新 main は --force-unverified なしの --input を確定リスト (verified_path) のみ許可する
    # path ガードを先に通す。schema 違反の検証を働かせるため、不正 JSON を確定リスト位置に置く。
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    bad = tmp_path / "eval-log" / "mfk-gap-verified.json"
    bad.parent.mkdir()
    bad.write_text(json.dumps([{"customer_id": "", "period_ym": "x", "verdict": "謎"}]),
                   encoding="utf-8")
    _argv(monkeypatch, "--sink")  # 既定で verified_path を読む
    assert CIG.main() == 2
    assert "schema 違反" in capsys.readouterr().err


def test_main_sink_missing_database_id(monkeypatch, tmp_path, capsys):
    # 確定リスト位置に有効行を置き path ガード/schema を通したうえで database_id 不在を検証する。
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    good = tmp_path / "eval-log" / "mfk-gap-verified.json"
    good.parent.mkdir()
    good.write_text(json.dumps([_valid_row()], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(CIG, "load_config", lambda: {"notion": {}})  # database_id 不在
    _argv(monkeypatch, "--sink")
    assert CIG.main() == 2
    assert "database_id 未設定" in capsys.readouterr().err


def test_main_sink_success_calls_upsert(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    good = tmp_path / "eval-log" / "mfk-gap-verified.json"
    good.parent.mkdir()
    good.write_text(json.dumps([_valid_row()], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(CIG, "load_config", lambda: {"notion": {"database_id": "db-1"}})
    captured = {}

    def fake_upsert(db_id, rows, period_ym=None):
        captured["db_id"] = db_id
        captured["rows"] = rows
        captured["period_ym"] = period_ym
        return {"created": 1, "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(CIG.notion_invoice_sink, "upsert", fake_upsert)
    _argv(monkeypatch, "--sink")  # 既定で確定リストを読む
    assert CIG.main() == 0
    assert captured["db_id"] == "db-1"
    assert captured["period_ym"] == "2026-06"  # rows[0] の period_ym
    out = capsys.readouterr().out
    assert "Notion upsert: created=1 updated=0" in out


def test_main_sink_force_unverified(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    eval_dir = tmp_path / "eval-log"
    eval_dir.mkdir()
    (eval_dir / "mfk-gap-candidates.json").write_text(
        json.dumps([_valid_row()], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(CIG, "load_config", lambda: {"notion": {"database_id": "db-1"}})
    monkeypatch.setattr(CIG.notion_invoice_sink, "upsert",
                        lambda db, rows, period_ym=None: {
                            "created": 0, "updated": 1, "period_ym": period_ym, "run_id": "r"})
    _argv(monkeypatch, "--sink", "--force-unverified")
    assert CIG.main() == 0
    assert "force-unverified" in capsys.readouterr().err


def test_main_sink_empty_rows_uses_month_arg(monkeypatch, tmp_path):
    # rows 空 + --month で period_ym を解決する分岐。空配列を確定リスト位置に置き
    # path ガードを通す (空配列は validate_rows OK・period 不一致チェックも素通り)。
    monkeypatch.setenv("MFK_OUTPUT_DIR", str(tmp_path))
    good = tmp_path / "eval-log" / "mfk-gap-verified.json"
    good.parent.mkdir()
    good.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(CIG, "load_config", lambda: {"notion": {"database_id": "db-1"}})
    captured = {}
    monkeypatch.setattr(CIG.notion_invoice_sink, "upsert",
                        lambda db, rows, period_ym=None: captured.update(period_ym=period_ym)
                        or {"created": 0, "updated": 0, "period_ym": period_ym, "run_id": "r"})
    _argv(monkeypatch, "--sink", "--month", "2026-09")
    assert CIG.main() == 0
    assert captured["period_ym"] == "2026-09"
