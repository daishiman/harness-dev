#!/usr/bin/env python3
"""MFクラウド請求書 OAuth2 初回ブートストラップ (取得担当が1回だけ実行)。

集中取得型: 会社のMFアカウントで登録したアプリの client_id/secret と、1回のブラウザ同意で
得た authorization code から access_token / refresh_token を取得し、取得担当マシンの
Keychain に保存する。以後は mf_invoice_api.py が refresh_token で自動更新するため、
ここを再実行する必要はない (トークン失効/スコープ変更時のみ)。

OAuth は標準ライブラリ(urllib)のみで実装 (第三者依存なし=ポータビリティ維持)。

前提 (会社で1回): MFクラウド「アプリポータル → API連携(開発者向け)」でアプリ作成し、
  client_id / client_secret / redirect_uri / 参照scope を取得しておく。

使い方:
  # 認証情報を env で渡す (Keychain に保存するので毎回は不要)
  export MF_INVOICE_CLIENT_ID=...        MF_INVOICE_CLIENT_SECRET=...
  export MF_INVOICE_REDIRECT_URI=...     # アプリ登録時のものと完全一致
  export MF_INVOICE_SCOPE='...'          # アプリで選んだ参照scope (空白区切り)

  # 1) 認可URLを出す → ブラウザで開いて同意 → リダイレクト先URLの ?code=XXXX を控える
  python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py" --authorize-url

  # 2) code を渡してトークン取得 + Keychain 保存
  python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py" --exchange '<CODE>'

  # 3) 動作確認 (refresh して /partners を1件叩く)
  python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py" --smoke
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://api.biz.moneyforward.com/authorize"
TOKEN_URL = "https://api.biz.moneyforward.com/token"
INVOICE_BASE = "https://invoice.moneyforward.com/api/v3"

# Keychain 保存先 (取得担当マシン1か所)。token 一式を JSON で1エントリに保存。
KC_SERVICE = os.environ.get("MF_INVOICE_KEYCHAIN_SERVICE", "")
KC_ACCOUNT = os.environ.get("MF_INVOICE_KEYCHAIN_ACCOUNT", "")


def _kc_ref():
    prefix = os.environ.get("HARNESS_KEYCHAIN_PREFIX", "").strip()
    service = KC_SERVICE or (f"mf-invoice-oauth.{prefix}" if prefix else "")
    account = KC_ACCOUNT or prefix
    if not service or not account:
        raise RuntimeError(
            "MF_INVOICE_KEYCHAIN_SERVICE/account or HARNESS_KEYCHAIN_PREFIX is required"
        )
    return service, account


def _cfg():
    cid = os.environ.get("MF_INVOICE_CLIENT_ID")
    sec = os.environ.get("MF_INVOICE_CLIENT_SECRET")
    redir = os.environ.get("MF_INVOICE_REDIRECT_URI")
    scope = os.environ.get("MF_INVOICE_SCOPE", "")
    missing = [k for k, v in [("MF_INVOICE_CLIENT_ID", cid),
                              ("MF_INVOICE_CLIENT_SECRET", sec),
                              ("MF_INVOICE_REDIRECT_URI", redir)] if not v]
    if missing:
        sys.stderr.write(f"環境変数が不足しています: {missing}\n"
                         "アプリ登録で得た値を export してください。\n")
        sys.exit(2)
    return cid, sec, redir, scope


def _kc_save(obj):
    service, account = _kc_ref()
    payload = json.dumps(obj)
    # 既存を消してから入れる (-U は環境差があるため delete→add で確実に上書き)。
    subprocess.run(["/usr/bin/security", "delete-generic-password",
                    "-s", service, "-a", account],
                   capture_output=True, text=True)
    # secret を argv に載せず stdin 渡し (README Step1 の安全原則と対称化)。
    # man security: `-w` を末尾・値なしで置くと非tty時は stdin から password を読む (Apple 推奨)。
    # 改行を付けない=JSON を壊さない。
    r = subprocess.run(["/usr/bin/security", "add-generic-password",
                        "-s", service, "-a", account, "-w"],
                       input=payload, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"Keychain 保存に失敗: {r.stderr}\n")
        sys.exit(2)


def _kc_load():
    service, account = _kc_ref()
    r = subprocess.run(["/usr/bin/security", "find-generic-password",
                        "-s", service, "-a", account, "-w"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout.strip())
    except json.JSONDecodeError:
        return None


def _post_token(data, client_id, client_secret):
    """トークンエンドポイントへ POST。client_id/secret は HTTP Basic 認証で渡す
    (MFクラウドの公式仕様 `-u ClientID:ClientSecret`)。grant_type/code/refresh_token/
    redirect_uri のみ body に入れる。"""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {basic}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"token endpoint HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}\n")
        sys.exit(2)


def authorize_url():
    cid, _, redir, scope = _cfg()
    params = {"response_type": "code", "client_id": cid, "redirect_uri": redir}
    if scope:
        params["scope"] = scope
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    print("以下のURLをブラウザで開き、同意後にリダイレクトされたURLの code= の値を控えてください:\n")
    print(url)
    print("\n(リダイレクト先がエラー表示でも、アドレスバーの ?code=XXXX をコピーすれば問題ありません)")
    return 0


def exchange(code):
    cid, sec, redir, _ = _cfg()
    tok = _post_token({
        "grant_type": "authorization_code", "code": code, "redirect_uri": redir,
    }, cid, sec)
    if "refresh_token" not in tok:
        sys.stderr.write(f"refresh_token が返りませんでした: {json.dumps(tok)[:300]}\n")
        return 2
    # client_id/secret も一緒に保存し、以後 env 無しでも refresh できるようにする。
    _kc_save({"client_id": cid, "client_secret": sec,
              "refresh_token": tok["refresh_token"],
              "access_token": tok.get("access_token", ""),
              "redirect_uri": redir})
    service, _ = _kc_ref()
    print(f"OK: token を Keychain ({service}) に保存しました。")
    print("→ 以後 mf_invoice_api.py が refresh_token で自動更新します。--smoke で確認できます。")
    return 0


def refresh_access_token():
    """保存済み refresh_token から access_token を取得する (ローテーション対応で再保存)。"""
    saved = _kc_load()
    if not saved:
        sys.stderr.write("保存済みトークンがありません。先に --exchange を実行してください。\n")
        sys.exit(2)
    tok = _post_token({
        "grant_type": "refresh_token", "refresh_token": saved["refresh_token"],
    }, saved["client_id"], saved["client_secret"])
    if "access_token" not in tok:
        sys.stderr.write(f"refresh 失敗: {json.dumps(tok)[:300]}\n")
        sys.exit(2)
    # refresh_token がローテーションされる実装なら新しい方を保存 (集中取得=単一利用なので安全)。
    new_refresh = tok.get("refresh_token", saved["refresh_token"])
    _kc_save({**saved, "refresh_token": new_refresh, "access_token": tok["access_token"]})
    return tok["access_token"]


def smoke():
    at = refresh_access_token()
    req = urllib.request.Request(INVOICE_BASE + "/partners?page=1&per_page=1", method="GET")
    req.add_header("Authorization", f"Bearer {at}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        n = len((data.get("data") or data.get("partners") or []))
        pg = data.get("pagination", {})
        print(f"OK: /partners 到達 (HTTP 200)。取引先 total={pg.get('total_count', pg.get('total','?'))} "
              f"(1ページ {n}件)。refresh_token による自動更新が機能しています。")
        return 0
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"/partners HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}\n")
        return 2


def main():
    p = argparse.ArgumentParser(description="MFクラウド請求書 OAuth2 初回ブートストラップ")
    p.add_argument("--authorize-url", action="store_true", help="認可URLを表示")
    p.add_argument("--exchange", metavar="CODE", help="authorization code をトークンに交換し保存")
    p.add_argument("--smoke", action="store_true", help="refresh して /partners 疎通確認")
    a = p.parse_args()
    if a.authorize_url:
        return authorize_url()
    if a.exchange:
        return exchange(a.exchange)
    if a.smoke:
        return smoke()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
