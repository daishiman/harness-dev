#!/usr/bin/env python3
"""Notion REST API の共有 transport 層 (HTTP 送受信 + トークン解決 + プロパティ読取)。

notion_invoice_sink / build_notion_db / verify_db_schema / mf_invoice_enrich など
複数モジュールが叩く Notion HTTP の低レベル要素をここへ集約する単一正本 (SSOT)。
これまで notion_invoice_sink.py に同居していた _req / _notion_token / _notion_service /
_notion_account / _rich_text_plain / _select_name を分離し、sink 側は本モジュールから
再公開 (re-export) して既存の公開名・挙動を不変に保つ。

トークン解決規則は MF キー側 (mfk_keychain) と対称:
  - token  : env(NOTION_API_KEY) > Keychain(service/account)
  - service: env(NOTION_KEYCHAIN_SERVICE) > config(notion.keychain_service) > default
  - account: env(NOTION_KEYCHAIN_ACCOUNT) > config(notion.keychain_account) > default
共通リゾルバ mfk_keychain.resolve_service / fetch_secret を経由する。

リトライ方針 (_req):
  - HTTP 429/502/503/504 : 既存挙動を維持 (最大3リトライ=4試行, Retry-After 尊重, 上限8秒)。
  - TimeoutError/URLError : ネットワーク断・read/connect timeout に指数バックオフで再試行
    (最大6試行, 上限10秒)。urllib の read timeout で素通り例外死していた経路を耐性化する。

書き込み系レート間隔 (_req):
  - Notion API は実測で平均 ~3 req/s 付近からレート制限 (HTTP429/timeout) に当たる。大量書き込みを
    無間隔で一括投入すると HTTP400/timeout で散発失敗する (2026-06-26 実証)。これを避けるため
    **書き込み系 (POST/PATCH/PUT/DELETE) の成功直後にのみ** `time.sleep(gap)` で間隔を空ける。
    読み取り (GET) には間隔を入れない (検索/全件 query を不必要に遅くしない)。
  - gap は env `MFK_NOTION_WRITE_GAP` (既定 0.34 秒 ≒ 1.6 req/s) から取得。`MFK_NOTION_WRITE_GAP=0`
    (負値・解析不能も含む) で無効化でき、テストは実 sleep せず高速に走る。
"""
import json
import os
import time
import urllib.error
import urllib.request

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# --- リトライ/タイムアウト定数 (SSOT) ----------------------------------------------
_TIMEOUT = 30                                  # 1 リクエストの read/connect timeout (秒)
_MAX_ATTEMPTS = 6                              # timeout/URLError は最大 6 試行 (= 5 リトライ)
_HTTP_RETRY_STATUS = {429, 502, 503, 504}      # 一時的とみなす HTTP ステータス
_HTTP_MAX_RETRIES = 3                          # 既存挙動: HTTP は最大 3 リトライ (= 4 試行)
_HTTP_BACKOFF_CAP = 8                          # HTTP バックオフ上限 (秒) — 既存値を不変に維持
_NET_BACKOFF_CAP = 10                          # ネットワーク断バックオフ上限 (秒) — 新規

# --- 書き込み系レート間隔 (SSOT) ---------------------------------------------------
_WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}  # 書き込み系メソッド (成功後に間隔を空ける)
_DEFAULT_WRITE_GAP = "0.34"                          # env 未指定時の既定間隔 (秒) ≒ 1.6 req/s
_WRITE_GAP_ENV = "MFK_NOTION_WRITE_GAP"             # 間隔を上書き/無効化する env 名


def _write_gap():
    """書き込み系リクエスト成功後に空ける間隔 (秒) を返す。

    env(MFK_NOTION_WRITE_GAP) > 既定 0.34。0 / 負値 / 解析不能は 0.0 (= 間隔なし) に倒す。
    テストは `MFK_NOTION_WRITE_GAP=0` で実 sleep を無効化して高速に走らせられる。
    """
    raw = os.environ.get(_WRITE_GAP_ENV, _DEFAULT_WRITE_GAP)
    try:
        gap = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return gap if gap > 0 else 0.0


def _notion_cfg(cfg=None):
    """cfg の notion セクション (dict) を返す。

    cfg を明示渡し (空 dict 含む) ならその notion セクション、cfg=None (未指定) なら
    load_config() を遅延 import で読む。import 失敗時は空 dict (= env+default のみで解決)。
    """
    if cfg is not None:
        return cfg.get("notion") or {}
    try:
        from mfk_api import load_config  # 遅延 import (実行経路により lib が後付け sys.path)
        return (load_config() or {}).get("notion") or {}
    except Exception:
        return {}


def _notion_service(cfg=None):
    """env(NOTION_KEYCHAIN_SERVICE) > config(notion.keychain_service) > default の順で解決。

    MF キー側 (mfk_keychain._service) と同じ共通リゾルバ resolve_service を共有し、解決規則を
    対称化する。cfg 未指定なら load_config() を遅延 import で読み、config から Notion service を
    設定可能にする (MF 側 keychain_service と対称)。
    """
    from mfk_keychain import resolve_service
    from tenant_runtime import credential_ref
    explicit = resolve_service(
        "NOTION_KEYCHAIN_SERVICE", _notion_cfg(cfg).get("keychain_service"), "")
    return explicit or credential_ref("notion-api-key")[0]


def _notion_account(cfg=None):
    """env(NOTION_KEYCHAIN_ACCOUNT) > config(notion.keychain_account) > default の順で解決。"""
    from mfk_keychain import resolve_service
    from tenant_runtime import credential_ref
    explicit = resolve_service(
        "NOTION_KEYCHAIN_ACCOUNT", _notion_cfg(cfg).get("keychain_account"), "")
    return explicit or credential_ref("notion-api-key")[1]


def _notion_token(cfg=None):
    """Notion API トークンを取得して生値 (文字列) を返す。

    解決順: env(NOTION_API_KEY) > Keychain(service/account)。service/account は
    env > config(notion.keychain_service/account) > default の順で `_notion_service`/
    `_notion_account` が解決する (MF 側と対称)。シグネチャは引数省略可で従来の引数なし呼出と
    互換。Keychain 取得は mfk_keychain.fetch_secret (MF 側と同一の共通コア) を経由する。
    """
    env = os.environ.get("NOTION_API_KEY")
    if env and env.strip():
        return env.strip()
    service = _notion_service(cfg)
    account = _notion_account(cfg)
    from mfk_keychain import fetch_secret
    token = fetch_secret(service, account)
    if not token:
        raise RuntimeError(f"Notion token lookup failed (service={service}, account={account})")
    return token


def _req(method, path, token, body=None):
    """Notion REST を 1 回叩いて JSON を返す。一時的エラーは指数バックオフで再試行する。

    リトライ対象:
      - HTTP 429/502/503/504 : 最大 3 リトライ (= 4 試行)。Retry-After を尊重し上限 8 秒。
        既存挙動を byte 一致で維持する。
      - TimeoutError/URLError : read/connect timeout・一時的なネットワーク断。最大 6 試行
        (= 5 リトライ)・指数バックオフ上限 10 秒。urllib の read timeout で例外死していた
        経路を耐性化する。
    上記以外の HTTP エラーや再試行枯渇時は RuntimeError を送出する。

    書き込み系 (POST/PATCH/PUT/DELETE) は **成功直後にのみ** `_write_gap()` 秒だけ sleep して
    Notion のレート制限を回避する (GET には間隔を入れない)。間隔は env(MFK_NOTION_WRITE_GAP) で
    調整・無効化できる (既定 0.34 秒)。
    """
    url = NOTION_API + path
    data = json.dumps(body).encode() if body is not None else None
    is_write = method.upper() in _WRITE_METHODS
    last_err = None
    for attempt in range(_MAX_ATTEMPTS):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                result = json.loads(r.read().decode())
            # 書き込み成功後のみレート間隔を空ける (読み取りは間隔なし・gap<=0 は sleep 省略)。
            if is_write:
                gap = _write_gap()
                if gap > 0:
                    time.sleep(gap)
            return result
        except urllib.error.HTTPError as e:
            # HTTPError は URLError のサブクラスなので URLError より先に捕捉する。
            body_text = e.read().decode("utf-8", "replace")
            if e.code in _HTTP_RETRY_STATUS and attempt < _HTTP_MAX_RETRIES:
                retry_after = e.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 2 ** attempt
                time.sleep(min(delay, _HTTP_BACKOFF_CAP))
                continue
            raise RuntimeError(f"Notion {method} {path}: HTTP {e.code} {body_text}")
        except (urllib.error.URLError, TimeoutError) as e:
            # read/connect timeout や一時的なネットワーク断。指数バックオフで再試行する。
            last_err = e
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(min(2 ** attempt, _NET_BACKOFF_CAP))
                continue
            raise RuntimeError(
                f"Notion {method} {path}: {type(e).__name__} {e} "
                f"({_MAX_ATTEMPTS} 回試行しても接続できませんでした)")
    # ループは必ず return / raise で抜けるが、保険として枯渇を明示する。
    raise RuntimeError(f"Notion {method} {path}: 再試行を使い果たしました ({last_err})")


def _rich_text_plain(prop):
    """Notion rich_text プロパティを plain text へ連結する (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    return "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("rich_text") or [])
    )


def _select_name(prop):
    """Notion select プロパティの name を返す (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    sel = prop.get("select") or {}
    return sel.get("name") or ""
