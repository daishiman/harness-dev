#!/usr/bin/env python3
# /// script
# name: postal_proxy
# purpose: 日本郵便 addresszip を中継する最小プロキシ。鍵と固定送信元IPをこのサーバ1台に集約し、不特定多数・多拠点のクライアントが鍵/IP登録なしで郵便番号を引けるようにする(IP許可リスト10件上限の回避)。
# inputs:
#   - keychain/env(サーバ側): japanpost-da-api.<keychain-prefix> (client_id/secret_key)、proxy_token (通行認証, 任意)
#   - http: POST /addresszip (addresszip と同じ body) / GET /healthz
# outputs:
#   - http: 日本郵便 addresszip レスポンス {addresses, level, ...} をそのまま返す
#   - exit: 0=OK
# contexts: [server]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""日本郵便 addresszip 中継プロキシ (参照実装・標準ライブラリのみ)。

不特定多数・多拠点配布で各クライアントの送信元IPがバラつき、日本郵便のIP許可リスト(1鍵あたり最大10件)で
覆いきれない場合に使う。鍵と「日本郵便に登録した固定送信元IP」を**このサーバ1台に集約**し、クライアントの
プラグインは `proxy_url` (+任意 `proxy_token`) だけ設定すれば、ローカルに日本郵便鍵もIP登録も持たずに
郵便番号を引ける。token 発行/IP認証/addresszip 呼び出しは `postal_api` の実証済み関数を再利用する
(直叩きとプロキシで挙動が一致)。

運用:
  - 本サーバを固定グローバルIPの環境 (Cloud Run + 固定NAT / VPS 等) で動かし、その出口IPを日本郵便 for Biz に登録する。
  - サーバ側 Keychain (または env) に client_id/secret_key を保持する (クライアントには配らない)。
  - クライアントの濫用を緩衝するため `proxy_token` (Bearer) と単一インスタンスのベストエフォートなレート制限を
    備える (確実な制限は前段 WAF/API GW で行うこと)。郵便番号検索は公開データだが、無認証の踏み台化を避けるため
    公開bind時は proxy_token を必須とする (fail-closed)。詳細は references/postal-proxy-deploy.md。

エンドポイント:
  POST /addresszip  body=addresszip と同じ JSON (pref_name/city_name/town_name/freeword 等) → {addresses, level, ...}
  GET  /healthz     → {"ok": true}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # noqa: E402
import postal_api  # noqa: E402

# 固定ウィンドウ・レート制限 (プロセス内・IP単位)。これは単一インスタンスのベストエフォート緩衝にすぎず、
# 確実な制限は前段の WAF/API GW で行うこと (複数インスタンス/再起動では状態が共有されない)。
_RATE_WINDOW_SEC = 60
_RATE_MAX_PER_WINDOW = int(os.environ.get("POSTAL_PROXY_RATE_PER_MIN", "60"))
_RATE_STATE: dict[str, tuple[int, float]] = {}
# ThreadingHTTPServer 配下では _RATE_STATE が複数スレッドから read-modify-write されるため、
# lost update を避けるべく更新をロックで直列化する。
_RATE_LOCK = threading.Lock()


def _client_token() -> str | None:
    """通行認証トークン (Keychain japanpost-da-api.<keychain-prefix>/proxy_token → env)。未設定なら認証なし。"""
    return notion_config.get_postal_proxy_token()


def _rate_ok(client_ip: str, now: float) -> bool:
    # read-modify-write を直列化し、ThreadingHTTPServer 配下での lost update を防ぐ。
    with _RATE_LOCK:
        count, window_start = _RATE_STATE.get(client_ip, (0, now))
        if now - window_start >= _RATE_WINDOW_SEC:
            count, window_start = 0, now
        count += 1
        _RATE_STATE[client_ip] = (count, window_start)
        return count <= _RATE_MAX_PER_WINDOW


def _is_loopback_host(host: str) -> bool:
    """bind host がループバック (ローカル専用) かどうか。無認証許容はこの場合に限る。"""
    return host.strip().lower() in ("127.0.0.1", "localhost", "::1")


class _Handler(BaseHTTPRequestHandler):
    server_version = "postal-proxy/0.1"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # noqa: A003  アクセスログは最小限 (機密を出さない)
        sys.stderr.write("[postal-proxy] " + (fmt % args) + "\n")

    def do_GET(self) -> None:
        if self.path.rstrip("/") in ("/healthz", "/health"):
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") not in ("/addresszip", ""):
            self._json(404, {"error": "not_found"})
            return
        # 通行認証 (proxy_token 設定時のみ)。
        required = _client_token()
        if required:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {required}":
                self._json(401, {"error": "unauthorized"})
                return
        # レート制限 (送信元単位)。
        client_ip = (self.headers.get("x-forwarded-for") or self.client_address[0] or "?").split(",")[0].strip()
        if not _rate_ok(client_ip, time.time()):
            self._json(429, {"error": "rate_limited"})
            return
        # body (addresszip クエリ) を読む。
        try:
            length = int(self.headers.get("Content-Length") or 0)
            query = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(query, dict):
                raise ValueError("body must be a JSON object")
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, {"error": "bad_request", "detail": str(e)[:120]})
            return
        # 日本郵便 addresszip を代行 (postal_api の実証済みロジックを再利用)。
        try:
            token = postal_api.get_token()
            addresses, level = postal_api.search_zip(
                token, query, egress_ip=postal_api.resolve_egress_ip())
            self._json(200, {"addresses": addresses, "level": level})
        except postal_api.JapanPostError as e:
            status = 403 if e.kind == "auth" else 502
            self._json(status, {"error": e.kind, "detail": e.detail[:200]})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": "internal", "detail": f"{type(e).__name__}: {e}"[:200]})


def main() -> int:
    ap = argparse.ArgumentParser(description="日本郵便 addresszip 中継プロキシ (参照実装)")
    ap.add_argument("--host", default=os.environ.get("POSTAL_PROXY_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    args = ap.parse_args()
    # 起動前チェック: 日本郵便鍵がサーバ側にあるか (無いと全リクエストが auth error になる)。
    cid, sec = notion_config.get_japanpost_credentials()
    if not (cid and sec):
        sys.stderr.write(
            "[postal-proxy] FATAL: サーバ側に日本郵便 client_id/secret_key がありません "
            "(Keychain japanpost-da-api.<keychain-prefix>)。references/postal-proxy-deploy.md を参照。\n")
        return 2
    # fail-closed: 非ループバック bind かつ proxy_token 未設定なら、無認証の踏み台化を機械層で拒否する。
    # ループバック bind 時のみ無認証を許容 (ローカル開発用)。proxy_token 設定時は Bearer 認証で防御。
    if not _client_token() and not _is_loopback_host(args.host):
        sys.stderr.write(
            "[postal-proxy] FATAL: 公開bind ({0}) では proxy_token が必須です "
            "(無認証の日本郵便API踏み台化を防ぐため)。Keychain/env で proxy_token を設定するか、"
            "ローカル検証は --host 127.0.0.1 で起動してください。\n".format(args.host))
        return 2
    if not _client_token():
        sys.stderr.write(
            "[postal-proxy] WARN: proxy_token 未設定 = 無認証の中継です "
            "(ループバック bind のためローカル開発用途に限り許容)。\n")
    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    sys.stderr.write(f"[postal-proxy] listening on {args.host}:{args.port} "
                     f"(rate {_RATE_MAX_PER_WINDOW}/min/IP)\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
