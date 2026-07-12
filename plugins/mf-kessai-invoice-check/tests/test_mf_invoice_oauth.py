#!/usr/bin/env python3
"""mf_invoice_oauth.py の OAuth ブートストラップを subprocess/urllib mock で検証する。

最重要 (security 回帰固定): _kc_save が secret (token JSON) を argv に載せず stdin で渡すこと
を機械担保する。argv に payload 文字列が混入したら Keychain 保存経路から secret が
プロセスリスト/ログに漏れうるため、構造で禁止する。

その他の契約 (network/Keychain 不要):
- _kc_load: 成功/失敗/不正 JSON → None。
- _cfg: env 不足 → SystemExit(2) / 揃い → tuple。
- _post_token: 成功 JSON / HTTPError → SystemExit(2) / Basic ヘッダ生成。
- exchange: refresh_token あり → _kc_save 呼出 + return 0 / 無し → return 2。
- refresh_access_token: 保存なし → SystemExit(2) / 成功 → access_token 返却 + 再保存。
- authorize_url: URL 生成 + return 0。
"""
import base64
import json
import types

import pytest

import mf_invoice_oauth as oauth


@pytest.fixture(autouse=True)
def _tenant_keychain_env(monkeypatch):
    # tenant 分離後の _kc_ref は HARNESS_KEYCHAIN_PREFIX (または明示 service/account) を要求する。
    # 他の keychain テスト (test_mfk_keychain.py 等) と同じ test-tenant 規約で解決させる。
    monkeypatch.setenv("HARNESS_KEYCHAIN_PREFIX", "test-tenant")


def _fake_run(returncode=0, stdout=""):
    """subprocess.run のスタブ。呼び出し引数を記録できるよう records に追記する。"""
    records = []

    def run(args, input=None, capture_output=None, text=None, **kwargs):
        records.append({"args": list(args), "input": input})
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

    run.records = records
    return run


# --- _kc_save: secret 非露出 (最重要) ---

def test_kc_save_never_puts_secret_in_argv_and_uses_stdin(monkeypatch):
    fake = _fake_run(returncode=0)
    monkeypatch.setattr(oauth.subprocess, "run", fake)
    secret_obj = {"refresh_token": "RT-super-secret", "access_token": "AT-secret",
                  "client_id": "cid", "client_secret": "SEC"}
    oauth._kc_save(secret_obj)
    payload = json.dumps(secret_obj)

    # delete → add の2回呼ばれる。
    assert len(fake.records) == 2
    add_call = fake.records[1]                              # add-generic-password
    assert "add-generic-password" in add_call["args"]
    # (1) argv (list) に payload 文字列が一切含まれない (secret 非露出)。
    assert payload not in add_call["args"]
    # secret 断片すら argv に乗らない。
    for token in ("RT-super-secret", "AT-secret", "SEC"):
        assert all(token not in str(a) for a in add_call["args"])
    # (2) payload は stdin で渡す。
    assert add_call["input"] == payload
    # (3) argv 末尾が -w (man security: 値なし -w は非tty時に stdin から読む)。
    assert add_call["args"][-1] == "-w"


def test_kc_save_exits_2_on_keychain_failure(monkeypatch):
    monkeypatch.setattr(oauth.subprocess, "run", _fake_run(returncode=1))
    with pytest.raises(SystemExit) as ei:
        oauth._kc_save({"refresh_token": "x"})
    assert ei.value.code == 2


# --- _kc_load ---

def test_kc_load_success(monkeypatch):
    obj = {"refresh_token": "rt", "client_id": "c", "client_secret": "s"}
    monkeypatch.setattr(oauth.subprocess, "run",
                        _fake_run(returncode=0, stdout=json.dumps(obj) + "\n"))
    assert oauth._kc_load() == obj


def test_kc_load_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(oauth.subprocess, "run", _fake_run(returncode=1, stdout=""))
    assert oauth._kc_load() is None


def test_kc_load_returns_none_on_invalid_json(monkeypatch):
    monkeypatch.setattr(oauth.subprocess, "run",
                        _fake_run(returncode=0, stdout="not-json{"))
    assert oauth._kc_load() is None


# --- _cfg ---

def test_cfg_exits_2_when_env_missing(monkeypatch):
    for k in ("MF_INVOICE_CLIENT_ID", "MF_INVOICE_CLIENT_SECRET",
              "MF_INVOICE_REDIRECT_URI", "MF_INVOICE_SCOPE"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit) as ei:
        oauth._cfg()
    assert ei.value.code == 2


def test_cfg_returns_tuple_when_env_present(monkeypatch):
    monkeypatch.setenv("MF_INVOICE_CLIENT_ID", "cid")
    monkeypatch.setenv("MF_INVOICE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("MF_INVOICE_REDIRECT_URI", "https://cb")
    monkeypatch.setenv("MF_INVOICE_SCOPE", "read")
    assert oauth._cfg() == ("cid", "sec", "https://cb", "read")


# --- _post_token ---

class _FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


def test_post_token_success_and_basic_header(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return _FakeResp({"access_token": "AT", "refresh_token": "RT"})

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen)
    out = oauth._post_token({"grant_type": "authorization_code"}, "cid", "sec")
    assert out == {"access_token": "AT", "refresh_token": "RT"}
    # Basic 認証ヘッダが client_id:client_secret の base64。
    expected = "Basic " + base64.b64encode(b"cid:sec").decode()
    assert captured["auth"] == expected


def test_post_token_exits_2_on_http_error(monkeypatch):
    import io
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError("https://t", 400, "bad", {},
                                     io.BytesIO(b'{"error":"invalid"}'))

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as ei:
        oauth._post_token({"grant_type": "x"}, "cid", "sec")
    assert ei.value.code == 2


# --- exchange ---

def test_exchange_saves_when_refresh_token_present(monkeypatch):
    monkeypatch.setenv("MF_INVOICE_CLIENT_ID", "cid")
    monkeypatch.setenv("MF_INVOICE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("MF_INVOICE_REDIRECT_URI", "https://cb")
    monkeypatch.setattr(oauth, "_post_token",
                        lambda data, cid, sec: {"refresh_token": "RT", "access_token": "AT"})
    saved = {}
    monkeypatch.setattr(oauth, "_kc_save", lambda obj: saved.update(obj))
    assert oauth.exchange("CODE") == 0
    assert saved["refresh_token"] == "RT"
    assert saved["client_id"] == "cid"


def test_exchange_returns_2_when_no_refresh_token(monkeypatch):
    monkeypatch.setenv("MF_INVOICE_CLIENT_ID", "cid")
    monkeypatch.setenv("MF_INVOICE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("MF_INVOICE_REDIRECT_URI", "https://cb")
    monkeypatch.setattr(oauth, "_post_token",
                        lambda data, cid, sec: {"access_token": "AT"})  # refresh_token なし
    called = {"saved": False}
    monkeypatch.setattr(oauth, "_kc_save", lambda obj: called.__setitem__("saved", True))
    assert oauth.exchange("CODE") == 2
    assert called["saved"] is False                        # 保存しない


# --- refresh_access_token ---

def test_refresh_access_token_exits_2_when_nothing_saved(monkeypatch):
    monkeypatch.setattr(oauth, "_kc_load", lambda: None)
    with pytest.raises(SystemExit) as ei:
        oauth.refresh_access_token()
    assert ei.value.code == 2


def test_refresh_access_token_returns_token_and_rotates(monkeypatch):
    saved = {"refresh_token": "RT-old", "client_id": "cid", "client_secret": "sec",
             "access_token": "AT-old"}
    monkeypatch.setattr(oauth, "_kc_load", lambda: dict(saved))
    monkeypatch.setattr(oauth, "_post_token",
                        lambda data, cid, sec: {"access_token": "AT-new", "refresh_token": "RT-new"})
    rotated = {}
    monkeypatch.setattr(oauth, "_kc_save", lambda obj: rotated.update(obj))
    assert oauth.refresh_access_token() == "AT-new"
    # ローテーションされた refresh_token を再保存している。
    assert rotated["refresh_token"] == "RT-new"
    assert rotated["access_token"] == "AT-new"


def test_refresh_access_token_exits_2_when_no_access_token(monkeypatch):
    monkeypatch.setattr(oauth, "_kc_load",
                        lambda: {"refresh_token": "RT", "client_id": "c", "client_secret": "s"})
    monkeypatch.setattr(oauth, "_post_token", lambda data, cid, sec: {"error": "boom"})
    with pytest.raises(SystemExit) as ei:
        oauth.refresh_access_token()
    assert ei.value.code == 2


# --- authorize_url ---

def test_authorize_url_builds_url_and_returns_0(monkeypatch, capsys):
    monkeypatch.setenv("MF_INVOICE_CLIENT_ID", "cid")
    monkeypatch.setenv("MF_INVOICE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("MF_INVOICE_REDIRECT_URI", "https://cb")
    monkeypatch.setenv("MF_INVOICE_SCOPE", "read write")
    assert oauth.authorize_url() == 0
    out = capsys.readouterr().out
    assert oauth.AUTHORIZE_URL in out
    assert "response_type=code" in out
    assert "client_id=cid" in out
    assert "scope=" in out                                 # scope ありなので載る


# --- smoke ---

def test_smoke_success_returns_0(monkeypatch, capsys):
    monkeypatch.setattr(oauth, "refresh_access_token", lambda: "AT")
    monkeypatch.setattr(oauth.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(
                            {"data": [{"id": "p1"}], "pagination": {"total_count": 42}}))
    assert oauth.smoke() == 0
    out = capsys.readouterr().out
    assert "total=42" in out
    assert "AT" not in out                                 # 生 access_token は出さない


def test_smoke_returns_2_on_http_error(monkeypatch):
    import io
    import urllib.error
    monkeypatch.setattr(oauth, "refresh_access_token", lambda: "AT")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError("https://i", 403, "forbidden", {},
                                     io.BytesIO(b'{"error":"scope"}'))

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen)
    assert oauth.smoke() == 2


# --- main (CLI dispatch) ---

def test_main_dispatches_authorize_url(monkeypatch):
    monkeypatch.setattr(oauth, "authorize_url", lambda: 0)
    monkeypatch.setattr(oauth.sys, "argv", ["mf_invoice_oauth.py", "--authorize-url"])
    assert oauth.main() == 0


def test_main_dispatches_exchange(monkeypatch):
    seen = {}

    def fake_exchange(code):
        seen["code"] = code
        return 0

    monkeypatch.setattr(oauth, "exchange", fake_exchange)
    monkeypatch.setattr(oauth.sys, "argv", ["mf_invoice_oauth.py", "--exchange", "CODE123"])
    assert oauth.main() == 0
    assert seen["code"] == "CODE123"


def test_main_dispatches_smoke(monkeypatch):
    monkeypatch.setattr(oauth, "smoke", lambda: 0)
    monkeypatch.setattr(oauth.sys, "argv", ["mf_invoice_oauth.py", "--smoke"])
    assert oauth.main() == 0


def test_main_prints_help_when_no_args(monkeypatch, capsys):
    monkeypatch.setattr(oauth.sys, "argv", ["mf_invoice_oauth.py"])
    assert oauth.main() == 0
    out = capsys.readouterr().out
    assert "--authorize-url" in out                        # ヘルプが出る
