#!/usr/bin/env python3
"""mfk_doctor.py のセットアップ自己診断ロジックを mock で検証する (network/Keychain 不要)。

守る契約:
  - 各チェックの OK/WARN/SKIP 判定が入力状態に一致する。
  - 鍵・トークン本体は出力に一切出さない (mask 済みのみ)。
  - install 位置は __file__ 相対で自己解決し $CLAUDE_PLUGIN_ROOT に依存しない。
  - WARN-not-FAIL: 個別失敗が全て WARN でも doctor 全体は exit 0 で穏当に終える。
  - MF API は GET のみ (書き込みしない=参照専用と整合)。
"""
import os

import pytest

import mfk_api
import mfk_doctor as doc
import mfk_keychain as kc
import notion_transport as nt


_RAW_KEY = "s3cr3tKEYVALUE0000"      # 生の APIキー (絶対に出力に出さないことを検証する)
_RAW_TOKEN = "secret_notion_TOKEN99"  # 生の Notion トークン (同上)


# --- (1) MF掛け払い APIキー (Keychain) ---

def test_check_mf_keychain_ok_masks_and_never_leaks(monkeypatch):
    monkeypatch.setattr(kc, "get_api_key", lambda cfg=None: _RAW_KEY)
    item = doc.check_mf_keychain({})
    assert item["status"] == "OK"
    assert _RAW_KEY not in item["detail"]          # 生値は出さない
    assert "(len=" in item["detail"]               # マスク表示になっている


def test_check_mf_keychain_warn_on_keychain_error(monkeypatch):
    def boom(cfg=None):
        raise kc.KeychainError("Keychain lookup failed", exit_code=44)
    monkeypatch.setattr(kc, "get_api_key", boom)
    item = doc.check_mf_keychain({})
    assert item["status"] == "WARN"
    assert item["action"]                          # 次アクションを提示する


# --- (2) MF掛け払い API 疎通 (GET のみ) ---

def test_check_mf_api_skip_when_key_missing():
    item = doc.check_mf_api({}, key_ok=False)
    assert item["status"] == "SKIP"


def test_check_mf_api_ok_reports_total(monkeypatch):
    monkeypatch.setattr(mfk_api, "get", lambda path, params, cfg=None: {"pagination": {"total": 121}})
    monkeypatch.setattr(mfk_api, "base_url", lambda cfg=None: "https://api.mfkessai.co.jp/v2")
    item = doc.check_mf_api({}, key_ok=True)
    assert item["status"] == "OK"
    assert "total=121" in item["detail"]


def test_check_mf_api_uses_get_only(monkeypatch):
    """doctor の MF 疎通は mfk_api.get (GET 専用ラッパ) だけを呼ぶ (書き込み経路を踏まない)。"""
    calls = {}

    def fake_get(path, params, cfg=None):
        calls["path"] = path
        calls["params"] = params
        return {"pagination": {"total": 3}}
    monkeypatch.setattr(mfk_api, "get", fake_get)
    monkeypatch.setattr(mfk_api, "base_url", lambda cfg=None: "https://x")
    doc.check_mf_api({}, key_ok=True)
    assert calls["path"] == "/customers"           # 参照エンドポイント
    assert calls["params"] == {"limit": 1}


def test_check_mf_api_warn_on_http_systemexit(monkeypatch):
    def boom(path, params, cfg=None):
        raise SystemExit("HTTP 401 /customers: unauthorized")
    monkeypatch.setattr(mfk_api, "get", boom)
    item = doc.check_mf_api({}, key_ok=True)
    assert item["status"] == "WARN"
    assert "401" in item["detail"]


def test_check_mf_api_warn_on_keychain_error(monkeypatch):
    def boom(path, params, cfg=None):
        raise kc.KeychainError("missing", exit_code=44)
    monkeypatch.setattr(mfk_api, "get", boom)
    item = doc.check_mf_api({}, key_ok=True)
    assert item["status"] == "WARN"


def test_check_mf_api_warn_on_unexpected(monkeypatch):
    def boom(path, params, cfg=None):
        raise ValueError("boom")
    monkeypatch.setattr(mfk_api, "get", boom)
    item = doc.check_mf_api({}, key_ok=True)
    assert item["status"] == "WARN"
    assert "ValueError" in item["detail"]


# --- (3) Notion トークン ---

def test_check_notion_token_ok_masks_and_never_leaks(monkeypatch):
    monkeypatch.setattr(nt, "_notion_token", lambda cfg=None: _RAW_TOKEN)
    item, token = doc.check_notion_token({})
    assert item["status"] == "OK"
    assert token == _RAW_TOKEN                      # reach へ渡すため生値を返す
    assert _RAW_TOKEN not in item["detail"]         # 表示はマスクのみ
    assert "(len=" in item["detail"]


def test_check_notion_token_warn_on_lookup_failure(monkeypatch):
    def boom(cfg=None):
        raise RuntimeError("Notion token lookup failed")
    monkeypatch.setattr(nt, "_notion_token", boom)
    item, token = doc.check_notion_token({})
    assert item["status"] == "WARN"
    assert token is None


# --- (4) Notion 既定 DB 到達 ---

def test_check_notion_reach_skip_without_token():
    item = doc.check_notion_reach({"notion": {"database_id": "abc12345"}}, token=None)
    assert item["status"] == "SKIP"


def test_check_notion_reach_skip_without_db_id():
    item = doc.check_notion_reach({"notion": {}}, token="tok")
    assert item["status"] == "SKIP"


def test_check_notion_reach_ok(monkeypatch):
    monkeypatch.setattr(nt, "_req",
                        lambda method, path, token: {"title": [{"plain_text": "請求書チェック_DB"}]})
    item = doc.check_notion_reach({"notion": {"database_id": "44444444d18c80eca872"}}, token="tok")
    assert item["status"] == "OK"
    assert "アクセス可" in item["detail"]
    assert "請求書チェック_DB" in item["detail"]


def test_check_notion_reach_warn_on_error(monkeypatch):
    def boom(method, path, token):
        raise RuntimeError("HTTP 404 object_not_found")
    monkeypatch.setattr(nt, "_req", boom)
    item = doc.check_notion_reach({"notion": {"database_id": "abc12345"}}, token="tok")
    assert item["status"] == "WARN"
    assert "404" in item["detail"]


def test_check_notion_reach_get_only(monkeypatch):
    """DB 到達は GET /databases/{id} だけを叩く (書き込みメソッドを踏まない)。"""
    seen = {}
    monkeypatch.setattr(nt, "_req",
                        lambda method, path, token: seen.update(method=method, path=path) or {"title": []})
    doc.check_notion_reach({"notion": {"database_id": "abcd1234"}}, token="tok")
    assert seen["method"] == "GET"
    assert seen["path"].startswith("/databases/")


# --- 統合: WARN-not-FAIL で exit 0・生値非漏洩・install 自己解決 ---

def _all_fail(monkeypatch):
    """全チェックを WARN/失敗側へ倒す (Keychain 未登録・API/Notion 全滅を模す)。"""
    def key_boom(cfg=None):
        raise kc.KeychainError("no key", exit_code=44)
    def token_boom(cfg=None):
        raise RuntimeError("no notion token")
    monkeypatch.setattr(kc, "get_api_key", key_boom)
    monkeypatch.setattr(nt, "_notion_token", token_boom)


def test_main_exits_zero_even_when_all_warn(monkeypatch, capsys):
    """WARN-not-FAIL: Keychain 未登録等で全項目が WARN/SKIP でも exit 0 で穏当に終える。"""
    _all_fail(monkeypatch)
    rc = doc.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "FAIL" not in out                        # FAIL は一切出さない (濫発しない)


def test_main_json_exits_zero_and_never_leaks_secrets(monkeypatch, capsys):
    """--json でも生の鍵/トークンは出力に出さず、exit 0 で終える。"""
    monkeypatch.setattr(kc, "get_api_key", lambda cfg=None: _RAW_KEY)
    monkeypatch.setattr(mfk_api, "get", lambda path, params, cfg=None: {"pagination": {"total": 7}})
    monkeypatch.setattr(mfk_api, "base_url", lambda cfg=None: "https://api.mfkessai.co.jp/v2")
    monkeypatch.setattr(nt, "_notion_token", lambda cfg=None: _RAW_TOKEN)
    monkeypatch.setattr(nt, "_req", lambda method, path, token: {"title": [{"plain_text": "DB"}]})
    rc = doc.main(["--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert _RAW_KEY not in out
    assert _RAW_TOKEN not in out
    assert '"status"' in out                        # JSON 構造で出力


def test_doctor_checks_returns_four_items(monkeypatch):
    _all_fail(monkeypatch)
    items = doc.doctor_checks()
    # (1)キー (2)API疎通 (3)Notionトークン (4)DB到達 の4項目。
    assert len(items) == 4
    labels = " ".join(it["label"] for it in items)
    assert "APIキー" in labels and "API 疎通" in labels
    assert "Notion トークン" in labels and "DB 到達" in labels


def test_install_location_self_resolves_without_plugin_root():
    """install 位置は __file__ 相対で自己解決し $CLAUDE_PLUGIN_ROOT に依存しない。

    生ターミナルで $CLAUDE_PLUGIN_ROOT が空展開して /lib/... になる事故を構造的に排除する。
    install 位置解決に環境変数を一切読まない (os.environ を使わない) こと + _LIB_DIR が
    __file__ 相対で lib/ を指すことを固定する。
    """
    src = open(doc.__file__, encoding="utf-8").read()
    # install 位置解決に環境変数を読まない (CLAUDE_PLUGIN_ROOT はもちろん一切の env も)。
    assert "os.environ" not in src
    assert "getenv" not in src
    assert os.path.basename(doc._LIB_DIR) == "lib"   # 自分の lib/ を自己解決している
    assert os.path.isfile(os.path.join(doc._LIB_DIR, "mfk_doctor.py"))
