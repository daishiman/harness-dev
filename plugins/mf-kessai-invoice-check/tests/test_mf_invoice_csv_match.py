#!/usr/bin/env python3
"""mf_invoice_csv_match.py (CSV 名寄せ・API不要) を tmp file で検証する (network 不要)。

守る契約:
- pick_column: 部分一致・最初の一致・None。
- to_ym: 区切り違い ("/", ".") を YYYY-MM へ正規化、不正/空 → None。
- read_csv: utf-8-sig / cp932 を判定、空行 → SystemExit。
- main(): VERIFIED 確定リスト不在なら fail-closed (return 2)。両方揃えば return 0 + 出力 JSON。
"""
import json

import pytest

import mf_invoice_csv_match as cm


# --- pick_column ---

def test_pick_column_partial_match_first_hit():
    headers = ["No", "取引先名（正式）", "請求日", "メモ"]
    assert cm.pick_column(headers, ["取引先名", "得意先"]) == "取引先名（正式）"
    # candidates の最初に一致するものを優先 (順序が効く)。
    assert cm.pick_column(headers, ["請求日", "取引先名"]) == "請求日"


def test_pick_column_returns_none_when_no_match():
    assert cm.pick_column(["a", "b"], ["xyz"]) is None


# --- to_ym ---

def test_to_ym_normalizes_separators():
    assert cm.to_ym("2026/05/01") == "2026-05"
    assert cm.to_ym("2026.5") == "2026-05"                  # ドット区切り + 1桁月 ゼロ埋め
    assert cm.to_ym("2026-12-31") == "2026-12"


def test_to_ym_invalid_and_empty():
    assert cm.to_ym("") is None
    assert cm.to_ym(None) is None
    assert cm.to_ym("不正な日付") is None


# --- read_csv ---

def test_read_csv_utf8_sig(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("取引先名,請求日\nA社,2026-05-01\n", encoding="utf-8-sig")
    rows, headers = cm.read_csv(str(p))
    assert headers == ["取引先名", "請求日"]
    assert rows[0]["取引先名"] == "A社"


def test_read_csv_cp932(tmp_path):
    p = tmp_path / "s.csv"
    p.write_bytes("取引先名,請求日\nＢ社,2026-04-01\n".encode("cp932"))
    rows, headers = cm.read_csv(str(p))
    assert rows[0]["請求日"] == "2026-04-01"


def test_read_csv_raises_on_empty(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        cm.read_csv(str(p))


# --- main(): VERIFIED fail-closed (WP-A 追加ガード) ---

def _write_csv(tmp_path):
    p = tmp_path / "invoices.csv"
    p.write_text("取引先名,請求日\nサンプル株式会社,2026-03-01\nサンプル株式会社,2026-05-01\n",
                 encoding="utf-8")
    return str(p)


def _point_eval_log(monkeypatch, tmp_path):
    """cm.EVAL_LOG / cm.VERIFIED を tmp に向ける (本物の eval-log を汚さない)。"""
    eval_log = tmp_path / "eval-log"
    verified = eval_log / "mfk-gap-verified.json"
    monkeypatch.setattr(cm, "EVAL_LOG", str(eval_log))
    monkeypatch.setattr(cm, "VERIFIED", str(verified))
    return eval_log, verified


def test_main_fails_closed_when_verified_absent(monkeypatch, tmp_path):
    csv_path = _write_csv(tmp_path)
    _point_eval_log(monkeypatch, tmp_path)                  # VERIFIED は作らない
    monkeypatch.setattr(cm.sys, "argv", ["mf_invoice_csv_match.py", csv_path])
    # CSV は有効だが確定リスト不在 → fail-closed で return 2。
    assert cm.main() == 2


def test_main_happy_path_writes_output(monkeypatch, tmp_path):
    csv_path = _write_csv(tmp_path)
    eval_log, verified = _point_eval_log(monkeypatch, tmp_path)
    eval_log.mkdir(parents=True, exist_ok=True)
    # 確定リスト (名寄せ対象の顧客源) を用意。CSV の取引先と名寄せでマッチする社名。
    verified.write_text(json.dumps([
        {"customer_id": "c1", "company_name": "サンプル株式会社"},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cm.sys, "argv", ["mf_invoice_csv_match.py", csv_path])
    assert cm.main() == 0
    # 結果 JSON が eval-log に出力される。
    out = eval_log / "mf-invoice-csv-match.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["matched"] == 1
    # 最古請求月 2026-03 が名寄せされている。
    assert data["results"][0]["oldest_billing_month"] == "2026-03"


def test_main_returns_2_when_no_csv_arg(monkeypatch):
    monkeypatch.setattr(cm.sys, "argv", ["mf_invoice_csv_match.py"])
    assert cm.main() == 2


def test_main_returns_2_when_csv_missing(monkeypatch, tmp_path):
    missing = str(tmp_path / "nope.csv")
    monkeypatch.setattr(cm.sys, "argv", ["mf_invoice_csv_match.py", missing])
    assert cm.main() == 2
