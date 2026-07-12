#!/usr/bin/env python3
"""mf_invoice_api.py (MFクラウド請求書 GET クライアント) を urllib mock で検証する (network 不要)。

守る契約:
- _rows: list/data/partners/billings/items の各形と空を正しく剥く。
- _total_pages: total_pages/total_page/total_count(→ceil)/None を解釈する。
- iter_all: total_pages に追従し、tp 無しは短ページで打ち切る (暴走しない)。
- _get: 401→強制 refresh して1回再試行 / 429→backoff して1回再試行 / その他→SystemExit。
- _access_token: プロセス内キャッシュし毎リクエスト refresh を避ける。
"""
import io
import json
import urllib.error

import pytest

import mf_invoice_api as inv


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """各テスト前後でトークンキャッシュを初期化し、テスト間干渉を防ぐ。"""
    inv._ACCESS_TOKEN["value"] = None
    yield
    inv._ACCESS_TOKEN["value"] = None


class _FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._data


# --- _rows ---

def test_rows_handles_list_and_each_key_and_empty():
    assert inv._rows([{"id": 1}]) == [{"id": 1}]            # 素の list
    assert inv._rows({"data": [{"id": 1}]}) == [{"id": 1}]
    assert inv._rows({"partners": [{"id": 2}]}) == [{"id": 2}]
    assert inv._rows({"billings": [{"id": 3}]}) == [{"id": 3}]
    assert inv._rows({"items": [{"id": 4}]}) == [{"id": 4}]
    assert inv._rows({"other": 1}) == []                    # 既知キーなし → 空
    assert inv._rows({}) == []


# --- _total_pages ---

def test_total_pages_prefers_explicit_then_ceils_count_then_none():
    assert inv._total_pages({"pagination": {"total_pages": 7}}, 100) == 7
    assert inv._total_pages({"pagination": {"total_page": 4}}, 100) == 4
    # total_count → ceil(count / per_page)。
    assert inv._total_pages({"pagination": {"total_count": 250}}, 100) == 3
    assert inv._total_pages({"pagination": {"total_count": 0}}, 100) == 1  # 最低1
    # pagination 無し / dict でない → None。
    assert inv._total_pages({"items": []}, 100) is None
    assert inv._total_pages([], 100) is None


# --- iter_all ---

def test_iter_all_follows_total_pages(monkeypatch):
    pages = {
        1: {"data": [{"id": 1}, {"id": 2}], "pagination": {"total_pages": 2}},
        2: {"data": [{"id": 3}], "pagination": {"total_pages": 2}},
    }
    seen = []

    def fake_get(path, params=None, _retried=False):
        seen.append(params["page"])
        return pages[params["page"]]

    monkeypatch.setattr(inv, "_get", fake_get)
    out = list(inv.iter_all("/partners"))
    assert [r["id"] for r in out] == [1, 2, 3]
    assert seen == [1, 2]                                   # tp=2 で止まる


def test_iter_all_stops_on_short_page_when_no_total_pages(monkeypatch):
    # total_pages が無いときは per_page 未満のページで打ち切る。
    calls = []

    def fake_get(path, params=None, _retried=False):
        calls.append(params["page"])
        # per_page=2 に対し 1件 (< per_page) を返す → 1ページで打ち切り。
        return {"items": [{"id": 99}]}

    monkeypatch.setattr(inv, "_get", fake_get)
    out = list(inv.iter_all("/billings", per_page=2))
    assert [r["id"] for r in out] == [99]
    assert calls == [1]                                    # 2ページ目を叩かない


# --- all_partners ---

def test_all_partners_returns_list(monkeypatch):
    monkeypatch.setattr(inv, "iter_all",
                        lambda path, *a, **k: iter([{"id": "p1"}, {"id": "p2"}]))
    assert inv.all_partners() == [{"id": "p1"}, {"id": "p2"}]


# --- oldest_billing_month ---

def test_oldest_billing_month_picks_earliest_and_counts(monkeypatch):
    billings = [
        {"billing_date": "2026-05-10"},
        {"billing_date": "2026-03-01"},   # 最古
        {"billing_date": "2026-08-20"},
    ]
    monkeypatch.setattr(inv, "iter_all", lambda path, params=None: iter(billings))
    ym, cnt = inv.oldest_billing_month("p1")
    assert ym == "2026-03"
    assert cnt == 3


def test_oldest_billing_month_falls_back_to_sales_date(monkeypatch):
    # billing_date 欠落時は sales_date を使う。
    billings = [{"sales_date": "2025-12-31"}, {"billing_date": "2026-02-01"}]
    monkeypatch.setattr(inv, "iter_all", lambda path, params=None: iter(billings))
    ym, cnt = inv.oldest_billing_month("p1")
    assert ym == "2025-12"
    assert cnt == 2


def test_oldest_billing_month_ignores_invalid_and_empty(monkeypatch):
    # 不正日付 (パターン外) はカウントするが ym 算出には使わない。
    billings = [{"billing_date": "bad"}, {"billing_date": ""}, {}]
    monkeypatch.setattr(inv, "iter_all", lambda path, params=None: iter(billings))
    ym, cnt = inv.oldest_billing_month("p1")
    assert ym is None
    assert cnt == 3

    # 完全な空 → (None, 0)。
    monkeypatch.setattr(inv, "iter_all", lambda path, params=None: iter([]))
    assert inv.oldest_billing_month("p1") == (None, 0)


# --- _access_token キャッシュ ---

def test_access_token_caches_and_force_refreshes(monkeypatch):
    calls = {"n": 0}

    def fake_refresh():
        calls["n"] += 1
        return f"tok{calls['n']}"

    monkeypatch.setattr(inv.oauth, "refresh_access_token", fake_refresh)
    inv._ACCESS_TOKEN["value"] = None
    assert inv._access_token() == "tok1"
    assert inv._access_token() == "tok1"                   # 2回目はキャッシュ (refresh しない)
    assert calls["n"] == 1
    assert inv._access_token(force=True) == "tok2"         # force で再取得
    assert calls["n"] == 2


# --- _get の retry / error ---

def _http_error(code, body=b'{"error":"x"}'):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))


def test_get_retries_once_on_401_with_forced_refresh(monkeypatch):
    monkeypatch.setattr(inv.oauth, "refresh_access_token", lambda: "tok")
    inv._ACCESS_TOKEN["value"] = "stale"
    seq = iter([_http_error(401), _FakeResp({"ok": True})])

    def fake_urlopen(req, timeout=None):
        nxt = next(seq)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    refreshed = {"forced": False}
    real_access = inv._access_token

    def spy_access(force=False):
        if force:
            refreshed["forced"] = True
        return real_access(force=force)

    monkeypatch.setattr(inv, "_access_token", spy_access)
    monkeypatch.setattr(inv.urllib.request, "urlopen", fake_urlopen)
    assert inv._get("/partners") == {"ok": True}
    assert refreshed["forced"] is True                     # 401 で強制 refresh が走った


def test_get_retries_once_on_429_after_sleep(monkeypatch):
    monkeypatch.setattr(inv.oauth, "refresh_access_token", lambda: "tok")
    slept = {"n": 0}
    monkeypatch.setattr(inv.time, "sleep", lambda s: slept.__setitem__("n", slept["n"] + 1))
    seq = iter([_http_error(429), _FakeResp({"ok": 429})])

    def fake_urlopen(req, timeout=None):
        nxt = next(seq)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    monkeypatch.setattr(inv.urllib.request, "urlopen", fake_urlopen)
    assert inv._get("/partners") == {"ok": 429}
    assert slept["n"] == 1                                 # backoff が1回入った


def test_get_raises_systemexit_on_other_http_error(monkeypatch):
    monkeypatch.setattr(inv.oauth, "refresh_access_token", lambda: "tok")

    def fake_urlopen(req, timeout=None):
        raise _http_error(500, b'{"error":"boom"}')

    monkeypatch.setattr(inv.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as ei:
        inv._get("/partners")
    assert "500" in str(ei.value)


def test_get_raises_systemexit_on_url_error(monkeypatch):
    monkeypatch.setattr(inv.oauth, "refresh_access_token", lambda: "tok")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("dns boom")

    monkeypatch.setattr(inv.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as ei:
        inv._get("/partners")
    assert "接続失敗" in str(ei.value)
