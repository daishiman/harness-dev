#!/usr/bin/env python3
"""scripts/clear_unsupported_end_dates.py (契約終了月の健全性クリア) の単体テスト。

Notion (notion_transport._req / _notion_token) と シート読取 (O.query_sheet_rows) を全 mock し、
実ネットワークを叩かない。検証する不変条件:
  - dry-run: シートへの PATCH が一切起きない。
  - apply  : 確認内容に終了根拠が無い行の契約終了月だけが空欄化され、根拠ありは不可侵。
  - fail-closed: sheet_db が解決できないと exit 2。
"""
import clear_unsupported_end_dates as C
import notion_transport
import reconcile_invoices as O


def _rows():
    return [
        {"page_id": "g", "取引先": "A", "契約終了月": "2606", "確認内容": "（2606終了）"},
        {"page_id": "u1", "取引先": "B", "契約終了月": "2606", "確認内容": "300,000円\n田中"},
        {"page_id": "u2", "取引先": "C", "契約終了月": "2605", "確認内容": ""},
        {"page_id": "e", "取引先": "D", "契約終了月": "", "確認内容": "x"},
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
    assert C._resolve_sheet_db(cfg, None) == "cfgS"
    assert C._resolve_sheet_db(cfg, "argS") == "argS"
    monkeypatch.setenv("MFK_SHEET_DB_ID", "envS")
    assert C._resolve_sheet_db(cfg, None) == "envS"


def test_missing_sheet_db_exit2(monkeypatch):
    monkeypatch.delenv("MFK_SHEET_DB_ID", raising=False)
    monkeypatch.setattr(O, "load_orchestrator_config", lambda *a, **k: {"notion": {}})
    assert C.main([]) == 2


def test_dry_run_no_writes(monkeypatch, capsys):
    writes = {}
    _wire(monkeypatch, writes)
    rc = C.main([])
    assert rc == 0
    assert writes == {}, "dry-run でシートへ書いてはいけない"
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "根拠なし" in out


def test_apply_clears_unsupported_only(monkeypatch, capsys):
    writes = {}
    _wire(monkeypatch, writes)
    rc = C.main(["--apply"])
    assert rc == 0
    # u1/u2 は終了根拠なし → 契約終了月を空欄化。g は根拠あり → 不可侵。e は終了月空 → 対象外。
    assert set(writes) == {"u1", "u2"}
    assert writes["u1"]["契約終了月"]["rich_text"] == []
    assert set(writes["u1"]) == {"契約終了月"}


def test_apply_reports_partial_failure(monkeypatch, capsys):
    def failing(method, path, token, body=None):
        if method == "PATCH" and path.startswith("/pages/"):
            raise RuntimeError("boom")
        raise AssertionError(path)
    monkeypatch.setattr(O, "load_orchestrator_config",
                        lambda *a, **k: {"notion": {"sheet_db_id": "S"}})
    monkeypatch.setattr(O, "query_sheet_rows", lambda *a, **k: _rows())
    monkeypatch.setattr(notion_transport, "_notion_token", lambda *a, **k: "tok")
    monkeypatch.setattr(notion_transport, "_req", failing)
    rc = C.main(["--apply"])
    assert rc == 2
    assert "失敗" in capsys.readouterr().err
