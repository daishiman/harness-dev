#!/usr/bin/env python3
"""MFクラウド請求書 API v3 読み取りクライアント (refresh_token 自動更新, GET 専用)。

集中取得型: 取得担当マシンの Keychain (mf_invoice_oauth.py が保存) から refresh_token を読み、
実行のたびに access_token を自動更新する。請求書の作成/更新はせず GET のみ
(初回請求月の算出に必要な /partners と /billings の参照だけ)。標準ライブラリのみ。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mf_invoice_oauth as oauth  # 同ディレクトリの refresh ロジックを再利用  # noqa: E402

BASE = "https://invoice.moneyforward.com/api/v3"

_ACCESS_TOKEN = {"value": None}  # プロセス内キャッシュ (毎リクエストでの refresh を避ける)


def _access_token(force=False):
    if force or not _ACCESS_TOKEN["value"]:
        _ACCESS_TOKEN["value"] = oauth.refresh_access_token()
    return _ACCESS_TOKEN["value"]


def _get(path, params=None, _retried=False):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {_access_token()}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401 and not _retried:  # access_token 失効 → 1回だけ強制 refresh して再試行
            _access_token(force=True)
            return _get(path, params, _retried=True)
        if e.code == 429:  # レートリミット → バックオフして1回再試行
            time.sleep(2)
            if not _retried:
                return _get(path, params, _retried=True)
        raise SystemExit(f"MFクラウド請求書 HTTP {e.code} {path}: {e.read().decode('utf-8','replace')[:300]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"接続失敗 {path}: {e.reason}")


def _rows(resp):
    if isinstance(resp, list):
        return resp
    for k in ("data", "partners", "billings", "items"):
        if isinstance(resp.get(k), list):
            return resp[k]
    return []


def _total_pages(resp, per_page):
    pg = resp.get("pagination") if isinstance(resp, dict) else None
    if isinstance(pg, dict):
        for k in ("total_pages", "total_page"):
            if isinstance(pg.get(k), int):
                return pg[k]
        if isinstance(pg.get("total_count"), int):
            return max(1, (pg["total_count"] + per_page - 1) // per_page)
    return None


def iter_all(path, params=None, per_page=100):
    page = 1
    while True:
        resp = _get(path, dict(params or {}, page=page, per_page=per_page))
        rows = _rows(resp)
        for r in rows:
            yield r
        tp = _total_pages(resp, per_page)
        if tp is not None:
            if page >= tp:
                break
        elif len(rows) < per_page:
            break
        page += 1
        if page > 500:  # 暴走防止
            break


def all_partners():
    """全取引先を取得し、id と name を持つ dict のリストで返す。"""
    return list(iter_all("/partners"))


def oldest_billing_month(partner_id):
    """取引先の全請求書から最古 billing_date の YYYY-MM を返す (件数も)。"""
    oldest, count = None, 0
    for b in iter_all("/billings", params={"partner_id": partner_id}):
        count += 1
        d = b.get("billing_date") or b.get("sales_date") or ""
        if isinstance(d, str) and re.match(r"\d{4}-\d{2}", d):
            ym = d[:7]
            if oldest is None or ym < oldest:
                oldest = ym
    return oldest, count


if __name__ == "__main__":
    # 簡易疎通: /partners 件数を出す (トークン未取得なら oauth 側で停止)。
    ps = all_partners()
    print(f"OK: /partners {len(ps)}件取得")
    if ps:
        print("partner サンプル keys:", list(ps[0].keys()))
