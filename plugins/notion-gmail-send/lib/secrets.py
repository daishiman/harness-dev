#!/usr/bin/env python3
# /// script
# name: secrets
# purpose: macOS Keychain から Notion API キーと Google サービスアカウント鍵を取得する。秘密値は返却のみ・ログ出力禁止。鍵の存在確認 (列挙) と値取得を分離する。
# inputs:
#   - keychain: notion-api-key.<keychain-prefix> / Google SA鍵 (svce/acct は config or 引数)
# outputs:
#   - get_notion_api_key(): str / get_google_sa_key(): dict / probe_*(): bool
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Keychain 秘密値アクセス (仕様書 §12)。

鍵の平文化・ログ出力を禁止する。値を返す関数 (get_*) と存在だけ確認する関数 (probe_*) を
分離し、preflight G1 は probe_* で存在を確かめ、実取得は送信直前に限定する。秘密値を含む
例外メッセージは出さない (KeychainError は service 名のみ)。
"""
from __future__ import annotations

import json
import subprocess

try:
    from .tenant_runtime import credential_ref
except ImportError:  # standalone script-style import
    from tenant_runtime import credential_ref

NOTION_SERVICE = ""
NOTION_ACCOUNT = ""


def _notion_ref() -> tuple[str, str]:
    return credential_ref("notion-api-key")


class KeychainError(Exception):
    """Keychain 取得失敗 (G1 で fail-closed)。メッセージに秘密値を含めない。"""


def _find_password(service: str, account: str | None, *, with_value: bool = True) -> str:
    """Keychain 項目を引く。`with_value=False` は存在確認のみ (`-w` を付けず秘密値を出力させない)。

    probe_* は with_value=False を使い、平文を subprocess バッファへ一切引き出さない (§12 PII)。
    返り値は with_value=True のとき平文、False のとき空文字 (存在のみ確認)。
    """
    cmd = ["security", "find-generic-password", "-s", service]
    if account:
        cmd += ["-a", account]
    if with_value:
        cmd.append("-w")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as e:
        raise KeychainError(f"security コマンド実行不可: {e}") from e
    if out.returncode != 0:
        raise KeychainError(f"Keychain に項目が無い: service={service}")
    return out.stdout.rstrip("\n") if with_value else ""


def probe_notion_api_key() -> bool:
    """Notion API キーが Keychain に存在するか (秘密値は取得しない)。"""
    try:
        service, account = _notion_ref()
        _find_password(service, account, with_value=False)
        return True
    except KeychainError:
        return False


def get_notion_api_key() -> str:
    """Notion API キーを取得する。不在なら KeychainError。"""
    service, account = _notion_ref()
    return _find_password(service, account)


def probe_google_sa_key(service: str, account: str | None = None) -> bool:
    """Google SA 鍵が Keychain に存在するか (秘密値は取得しない)。"""
    try:
        _find_password(service, account, with_value=False)
        return True
    except KeychainError:
        return False


def get_google_sa_key(service: str, account: str | None = None) -> dict:
    """Google サービスアカウント鍵 (JSON) を dict で取得する。

    値が JSON としてロードできなければ KeychainError (秘密値はメッセージに含めない)。
    """
    raw = _find_password(service, account)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise KeychainError(f"SA鍵が JSON ではない: service={service} (位置 {e.pos})") from None
    if not isinstance(data, dict) or data.get("type") != "service_account":
        raise KeychainError(f"SA鍵の形式が service_account ではない: service={service}")
    return data
