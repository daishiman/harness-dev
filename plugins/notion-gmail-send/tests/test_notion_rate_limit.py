# /// script
# name: test_notion_rate_limit
# purpose: NotionClient._request の予防的スロットル(最小呼び出し間隔で一定間隔プッシュ)と 429 リトライ(Retry-After尊重/指数バックオフ/上限/非429は非リトライ)を urlopen/sleep/monotonic モックで決定論検証する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""NotionClient のレート制御 (一定間隔プッシュ + 429 リトライ) を HTTP 層モックで検証。

Notion API は公称 ~3 req/sec。送信ログDBへ密に書き込むと 429 で受理されないため、
notion_client が (1) 最小呼び出し間隔を空けてプッシュし (2) 429 は Retry-After を
尊重して再試行する。本テストは time.sleep/time.monotonic をモックし、待ち秒数を
記録して挙動を秒単位で機械検証する (実時間に依存させない)。
"""
import email.message
import io
import json
import urllib.error

import pytest

from lib import notion_client


class _FakeResp:
    """urlopen の戻り値 (コンテキストマネージャ + read())。"""

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _http_429(retry_after=None):
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://api.notion.com/v1/x", 429,
                                  "Too Many Requests", hdrs,
                                  io.BytesIO(b'{"message":"rate_limited"}'))


def _http_400():
    return urllib.error.HTTPError("https://api.notion.com/v1/x", 400,
                                  "Bad Request", email.message.Message(),
                                  io.BytesIO(b'{"message":"bad"}'))


@pytest.fixture
def sleeps(monkeypatch):
    """sleep 呼び出し秒を記録し、monotonic を固定して throttle 計算を決定論にする。"""
    recorded = []
    monkeypatch.setattr(notion_client.time, "sleep", lambda s: recorded.append(s))
    monkeypatch.setattr(notion_client.time, "monotonic", lambda: 1000.0)
    return recorded


def _install_urlopen(monkeypatch, responses):
    """responses の各要素を順に返す/raise する urlopen を差し込む (尽きたら末尾を反復)。"""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        i = calls["n"]
        calls["n"] += 1
        r = responses[min(i, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return _FakeResp(r)

    monkeypatch.setattr(notion_client.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_throttle_spaces_consecutive_requests(monkeypatch, sleeps):
    # monotonic 固定 → 初回は _last=0 で待たず (1000-0 > 0.34)、以降は min_interval 分だけ待つ
    _install_urlopen(monkeypatch, [{"ok": 1}])
    c = notion_client.NotionClient("k", min_interval_sec=0.34, max_retries=0)
    c._request("GET", "/a")
    c._request("GET", "/b")
    c._request("GET", "/c")
    assert sleeps == pytest.approx([0.34, 0.34])


def test_no_throttle_when_interval_zero(monkeypatch, sleeps):
    _install_urlopen(monkeypatch, [{"ok": 1}])
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=0)
    c._request("GET", "/a")
    c._request("GET", "/b")
    assert sleeps == []  # スロットル無効化なら sleep しない


def test_429_retries_and_honors_retry_after(monkeypatch, sleeps):
    calls = _install_urlopen(monkeypatch, [_http_429(retry_after=2), {"ok": 1}])
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=3)
    out = c._request("POST", "/pages", {"x": 1})
    assert out == {"ok": 1}
    assert calls["n"] == 2     # 1回 429 + 1回成功
    assert sleeps == [2.0]     # Retry-After=2 を尊重


def test_429_without_retry_after_uses_exponential_backoff(monkeypatch, sleeps):
    _install_urlopen(monkeypatch, [_http_429(), _http_429(), {"ok": 1}])
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=3)
    out = c._request("GET", "/a")
    assert out == {"ok": 1}
    assert sleeps == [1.0, 2.0]  # base=1.0 → attempt0:1.0, attempt1:2.0


def test_429_exhausts_retries_then_raises(monkeypatch, sleeps):
    _install_urlopen(monkeypatch, [_http_429(retry_after=1)])  # 常に 429
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=2)
    with pytest.raises(notion_client.NotionError) as ei:
        c._request("GET", "/a")
    assert "HTTP 429" in str(ei.value)
    assert len(sleeps) == 2  # max_retries=2 回だけ待って諦める


def test_non_429_http_error_not_retried(monkeypatch, sleeps):
    calls = _install_urlopen(monkeypatch, [_http_400()])
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=3)
    with pytest.raises(notion_client.NotionError) as ei:
        c._request("GET", "/a")
    assert "HTTP 400" in str(ei.value)
    assert calls["n"] == 1   # リトライしない
    assert sleeps == []


def test_retry_after_capped_at_backoff_cap(monkeypatch, sleeps):
    _install_urlopen(monkeypatch, [_http_429(retry_after=999), {"ok": 1}])
    c = notion_client.NotionClient("k", min_interval_sec=0, max_retries=2)
    c._request("GET", "/a")
    assert sleeps == [notion_client.RETRY_BACKOFF_CAP_SEC]  # 際限なく待たない
