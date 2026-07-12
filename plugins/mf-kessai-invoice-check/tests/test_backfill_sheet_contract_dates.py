#!/usr/bin/env python3
"""scripts/backfill_sheet_contract_dates.py (契約日 同一取引先 backfill) の単体テスト。

Notion (notion_transport._req / _notion_token) と シート読取 (O.query_sheet_rows) を全 mock し、
実ネットワークを叩かない。検証する不変条件:
  - dry-run: シートへの PATCH が一切起きない。
  - apply  : 同一取引先で契約開始日が 1 種類に収束する空欄セルだけが書かれ、
             契約終了月と競合取引先は書かれない。
  - fail-closed: sheet_db が解決できないと exit 2。
"""
import backfill_sheet_contract_dates as B
import notion_transport
import reconcile_invoices as O


def _rows():
    # X株式会社 / X = normalize 同一グループ (開始日 1 種類 → 伝播、終了月は伝播しない)。
    # Y = 開始日 2 種類 (複数契約) → 競合・非伝播。
    return [
        {"page_id": "a", "取引先": "X株式会社", "契約開始日": "2026-06-01", "契約終了月": "2608"},
        {"page_id": "b", "取引先": "X株式会社", "契約開始日": "", "契約終了月": ""},
        {"page_id": "c", "取引先": "X", "契約開始日": "2606", "契約終了月": ""},
        {"page_id": "d", "取引先": "Y", "契約開始日": "2026-04-01", "契約終了月": ""},
        {"page_id": "e", "取引先": "Y", "契約開始日": "2026-09-01", "契約終了月": ""},
    ]


def _fake_req(writes):
    def req(method, path, token, body=None):
        if method == "PATCH" and path.startswith("/pages/"):
            writes[path.split("/pages/")[1]] = (body or {}).get("properties", {})
            return {}
        raise AssertionError(f"想定外の Notion 呼び出し: {method} {path}")
    return req


def _wire(monkeypatch, writes):
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": "S"}})
    monkeypatch.setattr(O, "query_sheet_rows", lambda *a, **k: _rows())
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", _fake_req(writes))


def test_resolve_sheet_db_precedence(monkeypatch):
    monkeypatch.delenv("MFK_SHEET_DB_ID", raising=False)
    cfg = {"notion": {"sheet_db_id": "cfgS"}}
    assert B._resolve_sheet_db(cfg, None) == "cfgS"
    assert B._resolve_sheet_db(cfg, "argS") == "argS"      # 引数最優先
    monkeypatch.setenv("MFK_SHEET_DB_ID", "envS")
    assert B._resolve_sheet_db(cfg, None) == "envS"          # env が config を上書き


def test_backfill_missing_sheet_db_exit2(monkeypatch):
    monkeypatch.delenv("MFK_SHEET_DB_ID", raising=False)
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})
    assert B.main([]) == 2


def test_backfill_dry_run_no_writes(monkeypatch, capsys):
    writes = {}
    _wire(monkeypatch, writes)
    rc = B.main([])
    assert rc == 0
    assert writes == {}, "dry-run でシートへ書いてはいけない"
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "競合" in out  # Y は開始日が食い違うため競合として可視化される


def test_backfill_apply_writes_converged_blanks_only(monkeypatch, capsys):
    writes = {}
    _wire(monkeypatch, writes)
    rc = B.main(["--apply"])
    assert rc == 0
    # b: 開始日だけ伝播 / c: 開始日は非空で不可侵、終了月は伝播しない。
    assert writes["b"]["契約開始日"]["rich_text"][0]["text"]["content"] == "2026-06-01"
    assert "契約終了月" not in writes["b"]
    assert "c" not in writes
    # Y (d, e) は競合グループ → 一切書かれない (誤伝播=請求漏れ事故の防止)。
    assert "d" not in writes and "e" not in writes
    # a は全非空 → 書かれない。
    assert "a" not in writes


def test_backfill_apply_reports_partial_failure(monkeypatch, capsys):
    # PATCH が失敗しても全体を止めず exit 2 で可視化する。
    def failing_req(method, path, token, body=None):
        if method == "PATCH" and path.startswith("/pages/"):
            raise RuntimeError("boom")
        raise AssertionError(path)

    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": "S"}})
    monkeypatch.setattr(O, "query_sheet_rows", lambda *a, **k: _rows())
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", failing_req)
    rc = B.main(["--apply"])
    assert rc == 2
    assert "失敗" in capsys.readouterr().err
