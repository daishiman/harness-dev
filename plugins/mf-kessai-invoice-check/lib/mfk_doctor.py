#!/usr/bin/env python3
# /// script
# name: mfk_doctor
# purpose: mf-kessai-invoice-check のセットアップ状態を横断自己診断する (MF掛け払いAPIキー / MF API 疎通 / Notion トークン / 既定 DB 到達)。本送信・書き込みはしない。
# inputs:
#   - argv: [--json]
#   - env: 各 lib の解決規則に従う (MFK_KEYCHAIN_* / NOTION_KEYCHAIN_* / MFK_BASE_URL 等)。CLAUDE_PLUGIN_ROOT には依存しない。
# outputs:
#   - stdout: 各チェックの OK/WARN/SKIP 一覧 (鍵・トークン本体はマスク表示のみ)
#   - exit: 0 (WARN-not-FAIL: 個別失敗は WARN として集約し全体は穏当に 0 で終える)
# contexts: [C, E]
# network: true   # MF API /customers GET・Notion DB GET の疎通確認 (読み取りのみ)
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""mf-kessai-invoice-check セットアップ自己診断 (doctor)。

MF掛け払い請求書チェックを回すのに必要な前提を 1 コマンドで横断点検する薄い入口:
  (1) MF掛け払い APIキー   … Keychain から取得できるか (mfk_keychain.get_api_key を再利用)
  (2) MF掛け払い API 疎通  … GET /customers?limit=1 で HTTP200・顧客総数 (mfk_api を再利用)
  (3) Notion トークン      … Keychain から取得できるか (notion_transport._notion_token を再利用)
  (4) Notion 既定 DB 到達  … GET /databases/{id} でアクセス可否 (notion_transport._req を再利用)

設計原則 (厳守):
  - install 位置は __file__ 相対で自己解決し `$CLAUDE_PLUGIN_ROOT` に一切依存しない。
    (生ターミナルで変数が空展開して `/lib/...` になる事故を構造的に排除する。)
  - 鍵・トークン本体は絶対に表示しない (mfk_keychain.mask のマスク表示のみ)。
  - WARN-not-FAIL: 個別チェック失敗は WARN として集約し、doctor 全体は常に exit 0 で穏当に終える。
    誤検出で FAIL を濫発しない (brew doctor の教訓)。診断ツールでありゲートではない。
  - MF API は GET のみ (参照専用ガードと整合。書き込みは一切しない)。
  - 既存 lib を import 再利用し、ロジックを複製しない。
"""
import argparse
import json as _json
import os
import sys

# install 位置は __file__ 相対で自己解決する。doctor は lib/ に同居するため、自分の
# ディレクトリを import path へ足すだけで兄弟 lib を解決できる。$CLAUDE_PLUGIN_ROOT を
# 参照しないので、Claude Code の外 (素のターミナル) で実行しても壊れない。
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import mfk_api  # noqa: E402  (GET 疎通・config ロード)
import mfk_keychain  # noqa: E402  (MF キー取得 + mask)
import notion_transport  # noqa: E402  (Notion トークン取得 + _req)

_ICON = {"OK": "OK  ", "WARN": "WARN", "SKIP": "SKIP"}


def _item(status, label, detail="", action=""):
    return {"status": status, "label": label, "detail": detail, "action": action}


def check_mf_keychain(cfg):
    """(1) MF掛け払い APIキーの Keychain 取得可否。本体は出さずマスク表示のみ。"""
    try:
        key = mfk_keychain.get_api_key(cfg=cfg)
    except mfk_keychain.KeychainError as e:
        return _item(
            "WARN", "MF掛け払い APIキー (Keychain)", str(e),
            "README『Step 1』で Keychain へ登録 (security add-generic-password -s mfkessai-api-key.<keychain-prefix> ...)")
    # key は生値。print せず mask() を通した安全表示だけを detail に載せる。
    return _item("OK", "MF掛け払い APIキー (Keychain)", mfk_keychain.mask(key))


def check_mf_api(cfg, key_ok):
    """(2) MF掛け払い API 疎通 (GET /customers?limit=1)。GET のみ・書き込みしない。"""
    if not key_ok:
        return _item(
            "SKIP", "MF掛け払い API 疎通", "APIキー未取得のため未実施",
            "上の『MF掛け払い APIキー』WARN を先に解消する")
    try:
        data = mfk_api.get("/customers", {"limit": 1}, cfg=cfg)
    except mfk_keychain.KeychainError as e:
        return _item("WARN", "MF掛け払い API 疎通", str(e), "README『Step 1』で Keychain へ登録")
    except SystemExit as e:
        # mfk_api.get は HTTP/接続エラーを SystemExit へ変換する。doctor は落とさず WARN 集約。
        return _item(
            "WARN", "MF掛け払い API 疎通", str(e),
            "environment / base_url を確認 (README『Step 4』)。401=キー不正 / 404=base_url 誤り")
    except Exception as e:  # noqa: BLE001  予期せぬ失敗も WARN へ倒す (doctor を落とさない)
        return _item("WARN", "MF掛け払い API 疎通", f"{type(e).__name__}: {e}", "README『Step 4』を参照")
    total = (data.get("pagination") or {}).get("total")
    return _item(
        "OK", "MF掛け払い API 疎通 (GET /customers)",
        f"HTTP 200 到達 base_url={mfk_api.base_url(cfg)} 顧客総数 total={total}")


def check_notion_token(cfg):
    """(3) Notion トークンの取得可否。マスク表示のみ。返り値 (item, token) で reach へ渡す。"""
    try:
        token = notion_transport._notion_token(cfg)
    except Exception as e:  # noqa: BLE001  RuntimeError (lookup 失敗) 等
        return _item(
            "WARN", "Notion トークン (Keychain)", f"{type(e).__name__}: {e}",
            "README『Notion セットアップ』で notion-api-key.<keychain-prefix> を Keychain へ登録"), None
    return _item("OK", "Notion トークン (Keychain)", mfk_keychain.mask(token)), token


def check_notion_reach(cfg, token):
    """(4) Notion 既定 DB への到達確認 (GET /databases/{id})。読み取りのみ。"""
    db_id = (cfg.get("notion") or {}).get("database_id")
    if not token:
        return _item(
            "SKIP", "Notion 既定 DB 到達", "Notion トークン未取得のため未実施",
            "上の『Notion トークン』WARN を先に解消する")
    if not db_id:
        return _item(
            "SKIP", "Notion 既定 DB 到達", "notion.database_id 未設定",
            "/run-mf-invoice-db-setup で DB を用意する")
    try:
        res = notion_transport._req("GET", f"/databases/{db_id}", token)
    except Exception as e:  # noqa: BLE001  404/接続失敗等
        return _item(
            "WARN", "Notion 既定 DB 到達", f"{type(e).__name__}: {e}",
            "DB に integration を接続する (README『Notion セットアップ』2)。未接続だと 404 object_not_found")
    title = "".join((t.get("plain_text") or "") for t in (res.get("title") or []))
    detail = f"database_id={db_id[:8]}... アクセス可"
    if title:
        detail += f" 『{title}』"
    return _item("OK", "Notion 既定 DB 到達", detail)


def doctor_checks():
    """全診断項目を実行し結果 list を返す (表示と分離してテスト可能にする)。"""
    try:
        cfg = mfk_api.load_config()
    except Exception:  # noqa: BLE001  config 読み込み失敗でも診断自体は続行する
        cfg = {}
    items = []
    mf_key = check_mf_keychain(cfg)
    items.append(mf_key)
    items.append(check_mf_api(cfg, key_ok=(mf_key["status"] == "OK")))
    notion_item, token = check_notion_token(cfg)
    items.append(notion_item)
    items.append(check_notion_reach(cfg, token))
    return items


def _print_text(items):
    print("mf-kessai-invoice-check doctor — セットアップ自己診断")
    print("=" * 56)
    for it in items:
        line = f"[{_ICON.get(it['status'], it['status'])}] {it['label']}"
        if it["detail"]:
            line += f": {it['detail']}"
        print(line)
        if it["action"]:
            print(f"       → 次アクション: {it['action']}")
    print("=" * 56)
    warns = [it for it in items if it["status"] == "WARN"]
    if warns:
        print(f"WARN {len(warns)} 件。上記の次アクションを実施して再度 doctor を実行してください "
              "(WARN は診断のみで処理を止めません)。")
    else:
        print("WARN なし。セットアップは整っています (SKIP は前提未達で未実施の項目)。")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="mf-kessai-invoice-check セットアップ自己診断 (鍵・トークン本体は表示しない)")
    ap.add_argument("--json", action="store_true", help="結果を JSON で出力する")
    args = ap.parse_args(argv)
    items = doctor_checks()
    if args.json:
        print(_json.dumps({"items": items}, ensure_ascii=False, indent=2))
    else:
        _print_text(items)
    # WARN-not-FAIL: 個別失敗は WARN に集約し、doctor 全体は常に 0 で穏当に終える
    # (診断ツールでありゲートではない。誤検出で FAIL を濫発しない = brew doctor の教訓)。
    return 0


if __name__ == "__main__":
    sys.exit(main())
