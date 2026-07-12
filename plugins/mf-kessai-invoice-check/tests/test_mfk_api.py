#!/usr/bin/env python3
"""mfk_api.py の GET 薄ラッパを urllib を mock して検証する (network 不要)。

守る契約 (mock でも検出力を持たせる):
- URL 組み立て: base_url + path、list パラメータは doseq で同名キー複数展開 (status=a&status=b)。
- 認証ヘッダ apikey が載る (Bearer でない)。
- iter_all のカーソルページネーション: pagination.end を after に渡して has_next=false まで辿る。
  has_next なのに end 欠落なら部分取得を防ぐため fail-closed で停止する。
- HTTP/接続エラーは SystemExit に変換 (黙って握りつぶさない)。
- load_config の空文字は既定を温存する 2 層マージ。
"""
import io
import json
import urllib.error

import pytest

import mfk_api as api


class _FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


def _patch_urlopen(monkeypatch, payloads):
    """urlopen を payloads の順に返すよう差し替え、渡された Request を calls に記録する。"""
    calls = []
    seq = iter(payloads)

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResp(next(seq))

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    return calls


# --- _deep_merge / load_config ---

def test_deep_merge_preserves_base_on_empty_values():
    base = {"base_url": "B", "notion": {"database_id": "keep", "parent_page_id": "p"}}
    over = {"base_url": "", "notion": {"database_id": None}}   # 空文字/None は上書きしない
    merged = api._deep_merge(base, over)
    assert merged["base_url"] == "B"
    assert merged["notion"]["database_id"] == "keep"
    assert merged["notion"]["parent_page_id"] == "p"


def test_deep_merge_overrides_nonempty():
    merged = api._deep_merge({"a": 1, "n": {"x": 1}}, {"a": 2, "n": {"x": 9}})
    assert merged == {"a": 2, "n": {"x": 9}}


def test_load_config_reads_distributed_default():
    cfg = api.load_config()
    assert isinstance(cfg, dict)
    # 配布既定 mf-kessai-config.default.json が読まれていること (notion or base_url を含む)。
    assert ("notion" in cfg) or ("base_url" in cfg) or ("environment" in cfg)


def test_load_config_maps_active_tenant_notion_overlay(monkeypatch, tmp_path):
    overlay = tmp_path / "notion-config.json"
    overlay.write_text(json.dumps({
        "databases": {
            "mf-kessai-output": {"db_id": "output-db"},
            "mf-kessai-sheet": {"db_id": "sheet-db"},
            "mf-kessai-reconcile-1": {"db_id": "reconcile-1"},
            "mf-kessai-reconcile-2": {"db_id": "reconcile-2"},
        },
        "mf_kessai": {
            "report_parent_page": "parent-page",
            "report_toggle_block": "toggle-block",
            "report_database_id": "report-db",
        },
    }))
    monkeypatch.setenv("NOTION_CONFIG_PATH", str(overlay))
    cfg = api.load_config()
    assert cfg["notion"] == {
        "database_id": "output-db",
        "keychain_service": "",
        "keychain_account": "",
        "sheet_db_id": "sheet-db",
        "reconcile_db1_id": "reconcile-1",
        "reconcile_db2_id": "reconcile-2",
        "report_parent_page": "parent-page",
        "report_toggle_block": "toggle-block",
        "report_database_id": "report-db",
    }


# --- base_url ---

def test_base_url_env_override(monkeypatch):
    monkeypatch.setenv("MFK_BASE_URL", "https://override.example/v2/")
    assert api.base_url({"environment": "sandbox"}) == "https://override.example/v2"


def test_base_url_sandbox_and_default(monkeypatch):
    monkeypatch.delenv("MFK_BASE_URL", raising=False)
    assert api.base_url({"environment": "sandbox"}) == api.SANDBOX_BASE_URL
    assert api.base_url({}) == api.DEFAULT_BASE_URL
    assert api.base_url({"base_url": "https://x/v2/"}) == "https://x/v2"


# --- get ---

def test_get_builds_url_with_doseq_and_apikey_header(monkeypatch):
    calls = _patch_urlopen(monkeypatch, [{"items": [], "ok": True}])
    out = api.get("/billings/qualified",
                  {"status": ["a", "b"], "limit": 5},
                  cfg={"base_url": "https://api.example/v2"},
                  api_key="KEY123")
    assert out == {"items": [], "ok": True}
    req = calls[0]
    assert req.full_url.startswith("https://api.example/v2/billings/qualified?")
    # list は doseq で同名キー複数展開。
    assert "status=a&status=b" in req.full_url
    assert "limit=5" in req.full_url
    # 認証は apikey ヘッダ (Bearer でない)。urllib はヘッダ名を capitalize する。
    assert req.get_header("Apikey") == "KEY123"
    assert req.get_method() == "GET"


def test_get_raises_systemexit_on_http_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {},
                                     io.BytesIO(b'{"error":"missing"}'))
    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as ei:
        api.get("/x", cfg={"base_url": "https://h/v2"}, api_key="k")
    assert "404" in str(ei.value)


def test_get_raises_systemexit_on_url_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("dns boom")
    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as ei:
        api.get("/x", cfg={"base_url": "https://h/v2"}, api_key="k")
    assert "接続失敗" in str(ei.value)


# --- iter_all (ページネーション) ---

def test_iter_all_follows_cursor_until_no_next(monkeypatch):
    page1 = {"items": [{"id": 1}, {"id": 2}], "pagination": {"end": "C2", "has_next": True}}
    page2 = {"items": [{"id": 3}], "pagination": {"end": "C3", "has_next": False}}
    calls = _patch_urlopen(monkeypatch, [page1, page2])
    items = list(api.iter_all("/billings/qualified", {"status": "invoice_issued"},
                              cfg={"base_url": "https://h/v2"}, api_key="k"))
    assert [i["id"] for i in items] == [1, 2, 3]
    # 1 回目に limit=200 が注入され、2 回目は after=C2 が載る。
    assert "limit=200" in calls[0].full_url
    assert "after=C2" in calls[1].full_url


def test_iter_all_fails_when_has_next_but_no_end(monkeypatch):
    # has_next=True でも end が無ければ部分取得のまま続行しない。
    page = {"items": [{"id": 1}], "pagination": {"has_next": True}}
    calls = _patch_urlopen(monkeypatch, [page])
    with pytest.raises(SystemExit) as ei:
        list(api.iter_all("/x", cfg={"base_url": "https://h/v2"}, api_key="k"))
    assert "ページング異常" in str(ei.value)
    assert len(calls) == 1                          # 2 回目を叩かない


# --- smoke / main ---

def test_smoke_prints_total_and_returns_zero(monkeypatch, capsys):
    _patch_urlopen(monkeypatch, [{"items": [{"id": "x"}], "pagination": {"total": 121}}])
    monkeypatch.setattr(api, "get_api_key", lambda cfg=None: "KEY")
    rc = api.smoke({"base_url": "https://h/v2"})
    assert rc == 0
    out = capsys.readouterr().out
    assert "total=121" in out
    assert "KEY" not in out                          # 生キーは出さない


def test_main_path_prints_json(monkeypatch, capsys):
    _patch_urlopen(monkeypatch, [{"items": [{"id": "b1"}]}])
    monkeypatch.setattr(api, "get_api_key", lambda cfg=None: "KEY")
    monkeypatch.setattr(api, "load_config", lambda path=None: {"base_url": "https://h/v2"})
    monkeypatch.setattr(api.sys, "argv",
                        ["mfk_api.py", "--path", "/billings/qualified", "--param", "limit=5"])
    assert api.main() == 0
    assert '"b1"' in capsys.readouterr().out


def test_main_smoke_path(monkeypatch):
    _patch_urlopen(monkeypatch, [{"items": [], "pagination": {"total": 0}}])
    monkeypatch.setattr(api, "get_api_key", lambda cfg=None: "KEY")
    monkeypatch.setattr(api, "load_config", lambda path=None: {"base_url": "https://h/v2"})
    monkeypatch.setattr(api.sys, "argv", ["mfk_api.py", "--smoke"])
    assert api.main() == 0


def test_main_returns_keychain_error_exit_code(monkeypatch):
    from mfk_keychain import KeychainError
    def boom(cfg=None):
        raise KeychainError("no key", exit_code=44)
    monkeypatch.setattr(api, "get_api_key", boom)
    monkeypatch.setattr(api, "load_config", lambda path=None: {"base_url": "https://h/v2"})
    monkeypatch.setattr(api.sys, "argv", ["mfk_api.py", "--smoke"])
    assert api.main() == 44
