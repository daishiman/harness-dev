#!/usr/bin/env python3
"""notion_transport.py の Notion HTTP transport 層を urllib mock で検証する。

検証範囲:
  - _req: 通常成功 / ヘッダ付与 / 429 リトライ (Retry-After 尊重 + 指数バックオフ) /
          TimeoutError・URLError の指数バックオフ・リトライ (今回の追加点) /
          再試行枯渇で RuntimeError / 非リトライ HTTP は即 raise。
  - _notion_token / _notion_service / _notion_account: env > config > default の解決順。
  - _rich_text_plain / _select_name: Notion プロパティの plain 読取。
ネットワークは一切叩かない (urlopen / fetch_secret を mock)。
"""
import json

import pytest

import mfk_api
import mfk_keychain as kc
import notion_transport as nt


class _FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _clear_notion_env(monkeypatch):
    for k in ("NOTION_API_KEY", "NOTION_KEYCHAIN_SERVICE", "NOTION_KEYCHAIN_ACCOUNT"):
        monkeypatch.delenv(k, raising=False)


# --- _req: 正常系 -----------------------------------------------------------------

def test_req_success_returns_parsed_json(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, timeout))
        return _FakeHTTPResponse({"ok": True, "n": 1})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    assert nt._req("GET", "/pages/x", "tok") == {"ok": True, "n": 1}
    assert len(calls) == 1
    assert calls[0][0] == "https://api.notion.com/v1/pages/x"
    assert calls[0][1] == nt._TIMEOUT


def test_req_sets_auth_version_and_body(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["auth"] = req.get_header("Authorization")
        captured["version"] = req.get_header("Notion-version")
        captured["content_type"] = req.get_header("Content-type")
        captured["data"] = req.data
        captured["method"] = req.get_method()
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    nt._req("POST", "/pages", "secret-tok", {"a": 1})
    assert captured["auth"] == "Bearer secret-tok"
    assert captured["version"] == nt.NOTION_VERSION
    assert captured["content_type"] == "application/json"
    assert json.loads(captured["data"].decode()) == {"a": 1}
    assert captured["method"] == "POST"


def test_req_no_body_sends_no_data(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["data"] = req.data
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    nt._req("GET", "/databases/x", "tok")
    assert captured["data"] is None


# --- _req: HTTP リトライ (既存挙動) ------------------------------------------------

def test_req_retries_429_with_retry_after_then_success(monkeypatch):
    """429 は Retry-After を尊重して再試行し、成功レスポンスを返す (既存挙動を維持)。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise nt.urllib.error.HTTPError(
                req.full_url, 429, "rate limited", {"Retry-After": "0"}, None)
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req("GET", "/pages/x", "tok") == {"ok": True}
    assert len(calls) == 2
    assert sleeps == [0.0]


def test_req_429_without_retry_after_uses_exponential_backoff(monkeypatch):
    """Retry-After が無い 429 は 2**attempt の指数バックオフ (上限8秒) で待つ。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) <= 2:
            raise nt.urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req("GET", "/x", "tok") == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [1, 2]  # 2**0, 2**1


def test_req_http_retryable_exhausts_raises(monkeypatch):
    """503 が続けば既存挙動どおり最大4試行で打ち切り RuntimeError (HTTP は3リトライ)。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        raise nt.urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        nt._req("GET", "/x", "tok")
    assert len(calls) == 4          # 1 + 3 retries
    assert sleeps == [1, 2, 4]      # capped at 8 but never reached here


def test_req_non_retryable_http_raises_immediately(monkeypatch):
    """400 など非リトライ HTTP は再試行せず即 RuntimeError を送出する。"""
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        raise nt.urllib.error.HTTPError(req.full_url, 400, "bad request", {}, None)

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="HTTP 400"):
        nt._req("POST", "/pages", "tok", {"x": 1})
    assert len(calls) == 1


# --- _req: TimeoutError / URLError リトライ (今回の追加点) -------------------------

def test_req_timeout_then_success(monkeypatch):
    """read timeout (TimeoutError) は指数バックオフで再試行し、回復後に成功を返す。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise TimeoutError("read timed out")
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req("GET", "/pages/x", "tok") == {"ok": True}
    assert len(calls) == 2
    assert sleeps == [1]  # 2**0


def test_req_url_error_then_success(monkeypatch):
    """一時的なネットワーク断 (URLError) も指数バックオフで再試行して回復する。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) <= 2:
            raise nt.urllib.error.URLError("connection refused")
        return _FakeHTTPResponse({"ok": True})

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req("GET", "/x", "tok") == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_req_timeout_exhausts_raises_after_max_attempts(monkeypatch):
    """timeout が続けば最大6試行で打ち切り RuntimeError。バックオフは上限10秒で頭打ち。"""
    calls = []
    sleeps = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        raise TimeoutError("read timed out")

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    with pytest.raises(RuntimeError, match="TimeoutError"):
        nt._req("GET", "/x", "tok")
    assert len(calls) == nt._MAX_ATTEMPTS            # 6 試行
    assert sleeps == [1, 2, 4, 8, 10]                # 2**attempt capped at 10, 5 回


# --- _req: 書き込み系レート間隔 (今回の追加点) ------------------------------------

def _ok_urlopen(req, timeout):
    return _FakeHTTPResponse({"ok": True})


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_req_write_method_sleeps_after_success(monkeypatch, method):
    """書き込み系 (POST/PATCH/PUT/DELETE) は成功直後に env 間隔だけ sleep する。"""
    sleeps = []
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0.34")
    monkeypatch.setattr(nt.urllib.request, "urlopen", _ok_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req(method, "/pages/x", "tok", {"a": 1}) == {"ok": True}
    assert sleeps == [0.34]  # 書き込み成功後に 1 回だけ間隔を空ける


def test_req_get_method_has_no_write_gap(monkeypatch):
    """読み取り (GET) は成功してもレート間隔を入れない (検索/全件 query を遅くしない)。"""
    sleeps = []
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0.34")
    monkeypatch.setattr(nt.urllib.request, "urlopen", _ok_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    assert nt._req("GET", "/databases/x", "tok") == {"ok": True}
    assert sleeps == []


def test_req_write_gap_disabled_when_env_zero(monkeypatch):
    """MFK_NOTION_WRITE_GAP=0 なら書き込み後も sleep を一切呼ばない (テスト高速化)。"""
    sleeps = []
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0")
    monkeypatch.setattr(nt.urllib.request, "urlopen", _ok_urlopen)
    monkeypatch.setattr(nt.time, "sleep", lambda d: sleeps.append(d))
    nt._req("POST", "/pages", "tok", {"a": 1})
    assert sleeps == []


def test_write_gap_default_and_invalid(monkeypatch):
    """_write_gap: env 未指定は既定 0.34 / 負値・解析不能・0 は 0.0 に倒す。"""
    monkeypatch.delenv("MFK_NOTION_WRITE_GAP", raising=False)
    assert nt._write_gap() == float(nt._DEFAULT_WRITE_GAP) == 0.34
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "-1")
    assert nt._write_gap() == 0.0
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "abc")
    assert nt._write_gap() == 0.0
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "0")
    assert nt._write_gap() == 0.0
    monkeypatch.setenv("MFK_NOTION_WRITE_GAP", "1.5")
    assert nt._write_gap() == 1.5


# --- トークン / service / account 解決 ---------------------------------------------

def test_notion_token_env_api_key_short_circuits(monkeypatch):
    """NOTION_API_KEY があれば Keychain を呼ばず env トークンを strip して返す。"""
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("NOTION_API_KEY", "  env-token  ")
    monkeypatch.setattr(kc, "fetch_secret",
                        lambda *a, **k: pytest.fail("env があれば Keychain を呼ぶべきでない"))
    assert nt._notion_token({}) == "env-token"


def test_notion_token_via_keychain_with_resolved_service(monkeypatch):
    """env が無ければ config 解決した service/account で fetch_secret を呼ぶ。"""
    _clear_notion_env(monkeypatch)
    captured = {}

    def fake_fetch(service, account):
        captured["service"] = service
        captured["account"] = account
        return "tok-from-keychain"

    monkeypatch.setattr(kc, "fetch_secret", fake_fetch)
    cfg = {"notion": {"keychain_service": "svc-x", "keychain_account": "acc-x"}}
    assert nt._notion_token(cfg) == "tok-from-keychain"
    assert captured == {"service": "svc-x", "account": "acc-x"}


def test_notion_token_raises_when_keychain_miss(monkeypatch):
    """env も Keychain も無ければ service/account を含む RuntimeError。"""
    _clear_notion_env(monkeypatch)
    monkeypatch.setattr(kc, "fetch_secret", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="Notion token lookup failed"):
        nt._notion_token({})


def test_notion_service_account_defaults(monkeypatch):
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("HARNESS_KEYCHAIN_PREFIX", "test-tenant")
    assert nt._notion_service({}) == "notion-api-key.test-tenant"
    assert nt._notion_account({}) == "test-tenant"


def test_notion_service_account_from_config(monkeypatch):
    _clear_notion_env(monkeypatch)
    cfg = {"notion": {"keychain_service": "svc-cfg", "keychain_account": "acc-cfg"}}
    assert nt._notion_service(cfg) == "svc-cfg"
    assert nt._notion_account(cfg) == "acc-cfg"


def test_notion_service_env_overrides_config(monkeypatch):
    _clear_notion_env(monkeypatch)
    monkeypatch.setenv("NOTION_KEYCHAIN_SERVICE", "svc-env")
    monkeypatch.setenv("NOTION_KEYCHAIN_ACCOUNT", "acc-env")
    cfg = {"notion": {"keychain_service": "svc-cfg", "keychain_account": "acc-cfg"}}
    assert nt._notion_service(cfg) == "svc-env"
    assert nt._notion_account(cfg) == "acc-env"


# --- _notion_cfg (cfg=None の load_config 経路) ------------------------------------

def test_notion_cfg_explicit_dict():
    assert nt._notion_cfg({"notion": {"k": "v"}}) == {"k": "v"}
    assert nt._notion_cfg({}) == {}


def test_notion_cfg_loads_from_config_when_none(monkeypatch):
    monkeypatch.setattr(mfk_api, "load_config", lambda: {"notion": {"k": "loaded"}})
    assert nt._notion_cfg() == {"k": "loaded"}


def test_notion_cfg_swallows_load_config_failure(monkeypatch):
    def boom():
        raise RuntimeError("config 読込失敗")

    monkeypatch.setattr(mfk_api, "load_config", boom)
    assert nt._notion_cfg() == {}


# --- プロパティ読取 ---------------------------------------------------------------

def test_rich_text_plain_concatenates():
    prop = {"rich_text": [{"text": {"content": "あ"}}, {"plain_text": "い"}]}
    assert nt._rich_text_plain(prop) == "あい"


def test_rich_text_plain_empty_and_non_dict():
    assert nt._rich_text_plain({}) == ""
    assert nt._rich_text_plain(None) == ""
    assert nt._rich_text_plain("x") == ""


def test_select_name_reads_name():
    assert nt._select_name({"select": {"name": "年間払い"}}) == "年間払い"


def test_select_name_empty_and_non_dict():
    assert nt._select_name({}) == ""
    assert nt._select_name({"select": None}) == ""
    assert nt._select_name(None) == ""
