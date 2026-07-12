# /// script
# name: test_gmail_client
# purpose: Gmail 送信の retry 分類 (rateLimit のみ retry / 接続・timeout・2xx後処理失敗は SendOutcomeUnknown) を検証する (F3/F9)。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""gmail_client._post_send の retry 分類テスト (二重送信防止の核)。

実ネットワークは使わず urlopen を差し替える。__init__ (google-auth 依存) を回避するため
__new__ でインスタンスを作り必要属性のみ注入する。"""
import io
import urllib.error

import pytest

from lib import gmail_client


class _Creds:
    valid = True
    token = "fake-token"


def _client():
    c = gmail_client.GmailClient.__new__(gmail_client.GmailClient)
    c._creds = _Creds()
    c._max_retry = 1
    c._backoff_initial = 0.0  # sleep を実質ゼロに
    c._backoff_cap = 0.0
    c._rate_delay = 0.0
    return c


class _Resp:
    def __init__(self, body):
        self._b = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def test_success_returns_message_id(monkeypatch):
    monkeypatch.setattr(gmail_client.urllib.request, "urlopen",
                        lambda req, timeout=30: _Resp(b'{"id": "msg-1"}'))
    assert _client()._post_send("rawdata") == "msg-1"


def test_send_uses_gmail_messages_send_endpoint_for_sender_sent_history(monkeypatch):
    seen = {}

    def _ok(req, timeout=30):
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        seen["body"] = req.data
        return _Resp(b'{"id": "msg-1"}')

    monkeypatch.setattr(gmail_client.urllib.request, "urlopen", _ok)
    assert _client()._post_send("rawdata") == "msg-1"
    assert seen["url"] == gmail_client.SEND_URL
    assert seen["url"].endswith("/gmail/v1/users/me/messages/send")
    assert seen["method"] == "POST"
    assert seen["body"] == b'{"raw": "rawdata"}'


def test_urlerror_is_outcome_unknown_no_retry(monkeypatch):
    calls = {"n": 0}

    def _boom(req, timeout=30):
        calls["n"] += 1
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(gmail_client.urllib.request, "urlopen", _boom)
    with pytest.raises(gmail_client.SendOutcomeUnknown):
        _client()._post_send("rawdata")
    assert calls["n"] == 1  # 接続失敗は retry しない (成否不明 → 自動再送禁止)


def test_2xx_then_bad_json_is_outcome_unknown(monkeypatch):
    monkeypatch.setattr(gmail_client.urllib.request, "urlopen",
                        lambda req, timeout=30: _Resp(b'not-json<<<'))
    with pytest.raises(gmail_client.SendOutcomeUnknown):
        _client()._post_send("rawdata")  # 送信受理後の解析失敗 = messageId 不明・送信済の可能性


def test_ratelimit_retries_then_quota_stopped(monkeypatch):
    calls = {"n": 0}

    def _rate(req, timeout=30):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 429, "Too Many", None,
                                     io.BytesIO(b'{"error":"rateLimit exceeded"}'))

    monkeypatch.setattr(gmail_client.urllib.request, "urlopen", _rate)
    with pytest.raises(gmail_client.QuotaStopped):
        _client()._post_send("rawdata")
    assert calls["n"] == 2  # max_retry=1 → 初回+retry1 の2回後に安全停止


def test_4xx_nonrate_is_runtime_error_not_unknown(monkeypatch):
    def _badreq(req, timeout=30):
        raise urllib.error.HTTPError("u", 400, "Bad", None, io.BytesIO(b'{"error":"invalid raw"}'))

    monkeypatch.setattr(gmail_client.urllib.request, "urlopen", _badreq)
    with pytest.raises(RuntimeError):  # 4xx 非rate = クライアント起因・未送信確定
        _client()._post_send("rawdata")


def test_5xx_is_outcome_unknown(monkeypatch):
    def _server_err(req, timeout=30):
        raise urllib.error.HTTPError("u", 503, "Unavailable", None, io.BytesIO(b'{"error":"backend"}'))

    monkeypatch.setattr(gmail_client.urllib.request, "urlopen", _server_err)
    with pytest.raises(gmail_client.SendOutcomeUnknown):  # 5xx は成否不明
        _client()._post_send("rawdata")
