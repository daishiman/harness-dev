#!/usr/bin/env python3
# /// script
# name: mfk_api
# purpose: マネーフォワード掛け払い API v2 への読み取り(GET)薄ラッパ + 疎通確認 CLI。
# inputs:
#   - argv: --smoke / --path <path> / --param key=value / --config <path>
#   - config: .mf-kessai-config.json (base_url / environment)
# outputs:
#   - stdout: JSON または疎通サマリ
#   - exit: 0=OK / 非0=失敗
# contexts: [C, E]
# network: true   # api.mfkessai.co.jp への HTTPS GET のみ
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""マネーフォワード掛け払い (MF KESSAI) API v2 の読み取り薄ラッパ。

- 認証: mfk_keychain.get_api_key() のキーを HTTP ヘッダ `apikey` に載せる
- base_url: .mf-kessai-config.json の "base_url" (既定: 本番 https://api.mfkessai.co.jp/v2)
- GET のみ。副作用のある POST/PATCH/DELETE は実装しない (発行漏れチェックは参照専用)

使い方:
  python3 lib/mfk_api.py --smoke
  python3 lib/mfk_api.py --path /billings/qualified --param issue_date_from=2026-05-01 \
      --param issue_date_to=2026-05-31 --param status=invoice_issued --param limit=5
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mfk_keychain import KeychainError, get_api_key  # noqa: E402

DEFAULT_BASE_URL = "https://api.mfkessai.co.jp/v2"
SANDBOX_BASE_URL = "https://sandbox-api.mfkessai.co.jp/v2"


def _deep_merge(base, over):
    """over を base に重ねる。空文字/None は「未設定」とみなし base を温存する
    (ローカル config の空欄が配布既定の database_id 等を潰さないため)。"""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        elif v not in ("", None):
            out[k] = v
    return out


def load_config(path=None):
    """設定を 2 層で読む。

    1. コミット済み配布既定 `mf-kessai-config.default.json` (導入者はゼロ設定で動く)
    2. gitignore のローカル `.mf-kessai-config.json` または明示 path (差分上書き)

    空文字値は上書きしないので、ローカルを空にしても既定 (Notion database_id 等) が残る。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.path.dirname(here)
    cfg = {}
    default_path = os.path.join(plugin_root, "mf-kessai-config.default.json")
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            cfg = json.load(f)
    # Active tenant values live in the shared Notion overlay.  Map only the
    # MF-owned fields; never fall back to another tenant or to baked-in IDs.
    notion_overlay_path = os.environ.get("NOTION_CONFIG_PATH", "").strip()
    if notion_overlay_path and os.path.exists(notion_overlay_path):
        with open(notion_overlay_path, encoding="utf-8") as f:
            tenant_overlay = json.load(f)
        databases = tenant_overlay.get("databases") or {}
        mf_values = tenant_overlay.get("mf_kessai") or {}
        mapped = {
            "notion": {
                "database_id": (databases.get("mf-kessai-output") or {}).get("db_id"),
                "sheet_db_id": (databases.get("mf-kessai-sheet") or {}).get("db_id"),
                "reconcile_db1_id": (databases.get("mf-kessai-reconcile-1") or {}).get("db_id"),
                "reconcile_db2_id": (databases.get("mf-kessai-reconcile-2") or {}).get("db_id"),
                "report_parent_page": mf_values.get("report_parent_page"),
                "report_toggle_block": mf_values.get("report_toggle_block"),
                "report_database_id": mf_values.get("report_database_id"),
            }
        }
        cfg = _deep_merge(cfg, mapped)
    for c in [path, os.path.join(plugin_root, ".mf-kessai-config.json")]:
        if c and os.path.exists(c):
            with open(c, encoding="utf-8") as f:
                cfg = _deep_merge(cfg, json.load(f))
            break
    env_overrides = {
        "database_id": os.environ.get("MFK_DATABASE_ID"),
        "sheet_db_id": os.environ.get("MFK_SHEET_DB_ID"),
        "reconcile_db1_id": os.environ.get("MFK_RECONCILE_DB1_ID"),
        "reconcile_db2_id": os.environ.get("MFK_RECONCILE_DB2_ID"),
    }
    cfg = _deep_merge(cfg, {"notion": env_overrides})
    return cfg


def base_url(cfg=None):
    cfg = cfg or {}
    env = os.environ.get("MFK_BASE_URL")
    if env:
        return env.rstrip("/")
    if cfg.get("environment") == "sandbox":
        return SANDBOX_BASE_URL
    return (cfg.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def get(path, params=None, cfg=None, api_key=None):
    """GET <base_url><path>?<params> を叩いて JSON を返す。

    params の値が list の場合は doseq で同名キー複数展開 (例: status=a&status=b)。
    """
    cfg = cfg if cfg is not None else load_config()
    api_key = api_key or get_api_key(cfg=cfg)
    url = base_url(cfg) + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", api_key)
    req.add_header("accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} {path}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"接続失敗 {path}: {e.reason} (base_url={base_url(cfg)} を確認)")


def _record_trace(trace_sink, site, path, page, params, page_index):
    """1 ページ分の pagination trace を trace_sink(list)へ append する(fetch fidelity 監査 C06 の入力)。

    trace 1 件 = {site, path, page_index, has_next, end, total, items_count, params}。
    C06(mfk_fetch_audit.py)がこの trace から pagination 完全性(has_next↔end)・total 件数突合・
    issue_date 範囲・stale を機械検証する。trace_sink=None なら何もしない(iter_all 完全同一挙動を保つ)。
    """
    if trace_sink is None:
        return
    pg = page.get("pagination", {}) or {}
    trace_sink.append({
        "site": site or path,
        "path": path,
        "page_index": page_index,
        "has_next": bool(pg.get("has_next")),
        "end": pg.get("end"),
        "total": pg.get("total"),
        "items_count": len(page.get("items", []) or []),
        # after(カーソル)は毎ページ変わる内部値ゆえ trace の params からは除外し、
        # issue_date_from/to・status 等の request 意図だけを残す(C06 の issue_date 範囲照合用)。
        "params": {k: v for k, v in (params or {}).items() if k != "after"},
    })


def iter_all(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
    """カーソルページングで path の全 items を yield する (limit=200 固定・GET 専用)。

    trace_sink(list)を渡すと各ページの pagination metadata を C06 fetch fidelity 監査用に記録する。
    trace_sink=None(既定)は従来と完全同一挙動で、既存呼出側(reconcile_invoices 等)を byte 不変に保つ。
    """
    params = dict(params or {}, limit=200)
    page_index = 0
    while True:
        page = get(path, params, cfg=cfg, api_key=api_key)
        _record_trace(trace_sink, site, path, page, params, page_index)
        for item in page.get("items", []):
            yield item
        pg = page.get("pagination", {})
        if not pg.get("has_next"):
            break
        nxt = pg.get("end")
        if not nxt:
            raise SystemExit(
                f"ページング異常 {path}: pagination.has_next=true だが pagination.end が空です。"
                "部分取得のまま続行しないため停止します。"
            )
        params["after"] = nxt
        page_index += 1


def get_with_trace(path, params=None, cfg=None, api_key=None, trace_sink=None, site=None):
    """get() の trace 変種(単一ページ GET・/customers?ids= 等の非ページング fetch site 用)。

    返り値は get() と同一の JSON。trace_sink を渡すと 1 件の pagination trace を記録する
    (customer-name 解決のような単発 GET も C06 が『取得できているか』を監査できるようにする)。GET 専用。
    """
    page = get(path, params, cfg=cfg, api_key=api_key)
    _record_trace(trace_sink, site, path, page, params, 0)
    return page


def smoke(cfg=None):
    """疎通確認: /customers?limit=1 を叩いて HTTP 200 と顧客総数を表示。キー本体は出さない。"""
    cfg = cfg if cfg is not None else load_config()
    bu = base_url(cfg)
    print(f"base_url = {bu}")
    data = get("/customers", {"limit": 1}, cfg=cfg)
    total = data.get("pagination", {}).get("total")
    print(f"OK: /customers 到達 (HTTP 200)。顧客総数 total={total}")
    print("→ APIキーは Keychain から取得し、ヘッダ apikey に載りました (本体は非表示)")
    return 0


def main():
    p = argparse.ArgumentParser(description="MF掛け払い API 読み取りクライアント (GET 専用)")
    p.add_argument("--smoke", action="store_true", help="疎通確認 (/customers?limit=1)")
    p.add_argument("--path", help="任意の GET パス (例: /billings/qualified)")
    p.add_argument("--param", action="append", default=[], help="key=value 形式 (複数可)")
    p.add_argument("--config")
    a = p.parse_args()
    cfg = load_config(a.config)
    try:
        if a.path and not a.smoke:
            params = {}
            for kv in a.param:
                k, _, v = kv.partition("=")
                params.setdefault(k, []).append(v)
            flat = {k: (vs[0] if len(vs) == 1 else vs) for k, vs in params.items()}
            data = get(a.path, flat, cfg=cfg)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        return smoke(cfg)
    except KeychainError as e:
        sys.stderr.write(f"[mfk_api] {e}\n")
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
