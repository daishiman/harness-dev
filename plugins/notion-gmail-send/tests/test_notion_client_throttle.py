# /// script
# name: test_notion_client_throttle
# purpose: NotionClient のレート制御 (最小送出間隔スロットル + 429 Retry-After リトライ) を検証する。一度に全件を push せず一定間隔でプッシュし、Notion の公称 ~3 req/sec 制限で弾かれないことを機械固定する。
# inputs: []
# outputs: []
# contexts: [C]
# network: false
# write-scope: none
# dependencies: ["pytest"]
# requires-python: ">=3.9"
# ///
"""NotionClient のレート制御テスト。

全 Notion リクエストが NotionClient._request の単一経路を通る前提で、
(1) 連続リクエスト間に最小送出間隔を空ける (バースト抑制=一定間隔プッシュ)
(2) 429 を受けたら Retry-After を尊重して再試行し、上限超過で NotionError
(3) min_interval_sec=0 で無効化でき、既定では有効 (呼び出し側が自動で律速される)
を、time を差し替えた決定論テストで固定する。dry-run の読込バースト・send の書込密集の
両方がここ1点で律速されることを保証する。"""
import urllib.error

import pytest

from lib import notion_client as nc


class _FakeResp:
    """urlopen の戻り値 (context manager) を模す。"""

    def __init__(self, payload: bytes = b'{"ok": true}'):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeClock:
    """monotonic/sleep を差し替える擬似時計。sleep で時刻が進む (実時間は消費しない)。

    初期時刻を十分大きく取り、初回 _throttle が誤って sleep しないようにする
    (実環境の time.monotonic() も常に大きな値を返すため、_last_request_ts=0.0 起点では
     初回は待たない)。"""

    def __init__(self, start: float = 10_000.0):
        self.t = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        if s > 0:
            self.t += s


def _patch_time(monkeypatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(nc.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(nc.time, "sleep", clock.sleep)
    return clock


def _patch_urlopen(monkeypatch, handler):
    monkeypatch.setattr(nc.urllib.request, "urlopen", handler)


# ============ (1) 最小送出間隔スロットル ============
def test_default_client_has_throttle_enabled():
    # 呼び出し側 (build-plan/send-campaign) は既定引数で生成するため、既定で律速される。
    c = nc.NotionClient("k")
    assert c._min_interval == nc.DEFAULT_MIN_INTERVAL_SEC
    assert c._min_interval > 0


def test_default_interval_stays_under_3rps():
    # 公称 ~3 req/sec を超えない (= 1/3 秒以上) が、過度には空けない (最大化しない)。
    assert nc.DEFAULT_MIN_INTERVAL_SEC >= 1.0 / 3.0
    assert nc.DEFAULT_MIN_INTERVAL_SEC <= 1.0  # 控えめ: 1秒以上は空けない


def test_consecutive_requests_are_spaced_by_min_interval(monkeypatch):
    clock = _patch_time(monkeypatch)
    calls: list[str] = []

    def handler(req, timeout=None):
        calls.append(req.get_full_url())
        return _FakeResp()

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0.34)
    c.retrieve_database("db1")  # 初回: 待たない
    c.retrieve_database("db2")  # 2回目: 直前から間隔を空ける
    c.retrieve_database("db3")  # 3回目: 同上

    assert len(calls) == 3
    positive = [s for s in clock.sleeps if s > 0]
    assert len(positive) == 2, "初回以外は最小間隔だけ待つ (一定間隔プッシュ)"
    assert all(abs(s - 0.34) < 1e-9 for s in positive)


def test_zero_interval_disables_throttle(monkeypatch):
    clock = _patch_time(monkeypatch)
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp())
    c = nc.NotionClient("k", min_interval_sec=0)
    for db in ("a", "b", "c"):
        c.retrieve_database(db)
    assert [s for s in clock.sleeps if s > 0] == [], "min_interval_sec=0 はスロットル無効"


def test_query_all_paces_each_page(monkeypatch):
    # ページネーション (has_more) でも各ページ取得が _request を通り律速される。
    clock = _patch_time(monkeypatch)
    pages = [
        {"results": [{"id": "1"}], "has_more": True, "next_cursor": "c1"},
        {"results": [{"id": "2"}], "has_more": False},
    ]

    def handler(req, timeout=None):
        return _FakeResp(__import__("json").dumps(pages.pop(0)).encode())

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0.34)
    rows = c.query_all("db")
    assert [r["id"] for r in rows] == ["1", "2"]
    assert len([s for s in clock.sleeps if s > 0]) == 1, "2ページ目の取得が律速される"


# ============ (2) 429 Retry-After リトライ ============
def _http_429(retry_after: str | None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return urllib.error.HTTPError("https://api.notion.com/v1/x", 429, "rate limited", headers, None)


def test_429_is_retried_honoring_retry_after(monkeypatch):
    clock = _patch_time(monkeypatch)
    seq = ["429", "ok"]

    def handler(req, timeout=None):
        if seq.pop(0) == "429":
            raise _http_429("0.1")
        return _FakeResp()

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0)  # 間隔は0にしてリトライ待ちだけを観測
    out = c.retrieve_database("db")
    assert out == {"ok": True}
    assert 0.1 in clock.sleeps, "Retry-After(0.1秒) を尊重して待ってから再送する"


def test_429_without_retry_after_uses_capped_backoff(monkeypatch):
    clock = _patch_time(monkeypatch)
    seq = ["429", "ok"]

    def handler(req, timeout=None):
        if seq.pop(0) == "429":
            raise _http_429(None)
        return _FakeResp()

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0)
    out = c.retrieve_database("db")
    assert out == {"ok": True}
    waited = [s for s in clock.sleeps if s > 0]
    assert waited, "Retry-After 不在でもバックオフして待つ"
    assert all(s <= nc.RETRY_BACKOFF_CAP_SEC for s in waited), "待機は cap を超えない"


def test_429_exhausts_retries_then_raises(monkeypatch):
    _patch_time(monkeypatch)

    def handler(req, timeout=None):
        raise _http_429("0.01")

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0, max_retries=2)
    with pytest.raises(nc.NotionError) as ei:
        c.retrieve_database("db")
    assert "429" in str(ei.value), "リトライ上限超過は 429 として fail-closed"


def test_non_429_http_error_is_not_retried(monkeypatch):
    _patch_time(monkeypatch)
    attempts = {"n": 0}

    def handler(req, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError("https://api.notion.com/v1/x", 400, "bad", {}, None)

    _patch_urlopen(monkeypatch, handler)
    c = nc.NotionClient("k", min_interval_sec=0, max_retries=3)
    with pytest.raises(nc.NotionError):
        c.retrieve_database("db")
    assert attempts["n"] == 1, "429 以外 (4xx 等) は再試行しない"
