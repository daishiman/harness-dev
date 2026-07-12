#!/usr/bin/env python3
# /// script
# name: mfk_keychain
# purpose: macOS Keychain からマネーフォワード掛け払い API キーを取得する唯一の経路。
# inputs:
#   - argv: --service --account --check
#   - env: MFK_KEYCHAIN_SERVICE / MFK_KEYCHAIN_ACCOUNT / MFK_API_KEY(fallback)
# outputs:
#   - stdout: マスク表示のみ (生値は出力しない)
#   - exit: 0=OK / 44=Keychain lookup 失敗 / 9=非macOS かつ env fallback 無し
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""macOS Keychain からマネーフォワード掛け払い (MF KESSAI) API キーを取得する唯一の経路。

命名規約: service=mfkessai-api-key.<keychain-prefix> / account=<keychain-prefix>。
既存の notion-api-key.<keychain-prefix> (notion_config.py) と同じ命名規約に揃える。
実装パターンは plugins/contract-generator/lib/keychain_get_secret.py に準拠。

優先順位:
  1. macOS Keychain (service/account) ← 通常はこちら
  2. 環境変数 MFK_API_KEY ← CI / 非macOS のフォールバックのみ

取得した生値はログ出力・print してはならない。HTTP ヘッダ `apikey` にのみ載せる。
"""

import argparse
import os
import subprocess
import sys

from tenant_runtime import TenantConfigError, credential_ref

# --- service 命名規約 SSOT ---------------------------------------------------
# Keychain service 名の既定はこの定数群を唯一の正本とする。MF キーと Notion トークンの
# 両方をここで一元管理し、命名規約 (<purpose>-api-key.<keychain-prefix> / account=<keychain-prefix>) の
# 散在を防ぐ。notion_invoice_sink._notion_token はこの DEFAULT_NOTION_SERVICE を参照する。
DEFAULT_SERVICE = ""
DEFAULT_NOTION_SERVICE = ""
DEFAULT_ACCOUNT = ""


def resolve_service(env_var, config_value, default):
    """env > config > default の優先順で Keychain service/account 名を解決する共通リゾルバ。

    MF キー (_service/_account) と Notion トークン (_notion_token) が同一の解決規則を
    共有するための単一実装。env_var が示す環境変数を最優先し、次に config 値、最後に
    既定値へフォールバックする。空文字/None は「未設定」とみなし次の候補へ進む。
    """
    return os.environ.get(env_var) or (config_value or None) or default


def _service(cfg=None):
    """env > config > active tenant の優先順で service 名を解決する。"""
    explicit = resolve_service("MFK_KEYCHAIN_SERVICE", (cfg or {}).get("keychain_service"), "")
    if explicit:
        return explicit
    try:
        return credential_ref("mfkessai-api-key")[0]
    except TenantConfigError as exc:
        raise KeychainError(str(exc), exit_code=9) from exc


def _account(cfg=None):
    """env > config > active tenant の優先順で account 名を解決する。"""
    explicit = resolve_service("MFK_KEYCHAIN_ACCOUNT", (cfg or {}).get("keychain_account"), "")
    if explicit:
        return explicit
    try:
        return credential_ref("mfkessai-api-key")[1]
    except TenantConfigError as exc:
        raise KeychainError(str(exc), exit_code=9) from exc


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def fetch_secret(service, account):
    """macOS Keychain から service/account の生値を取得する共通コア。

    見つからない/非macOS なら None を返す (例外は投げない)。MF キーと Notion トークンの
    両方がこの単一実装を経由することで、`security` 呼出・非macOS フォールバック・改行除去の
    挙動を一元化する。生値はログ・標準出力に出さないこと。
    """
    if sys.platform != "darwin":
        return None
    res = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return None
    token = (res.stdout or "").rstrip("\n")
    return token or None


def _from_keychain(service, account):
    """後方互換エイリアス。共通コア fetch_secret へ委譲する (既存呼出/テストを壊さない)。"""
    return fetch_secret(service, account)


def get_api_key(service=None, account=None, cfg=None):
    """MF 掛け払い API キーを取得して生値を返す。

    service/account は env > config(cfg.keychain_service/account) > DEFAULT の優先順で解決する。
    呼び出し側は戻り値をログ・標準出力に出さないこと。
    """
    service = service or _service(cfg)
    account = account or _account(cfg)

    token = _from_keychain(service, account)
    if token:
        return token

    env_key = os.environ.get("MFK_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if sys.platform != "darwin":
        raise KeychainError(
            f"unsupported platform: {sys.platform} (macOS only). "
            "非macOS では環境変数 MFK_API_KEY を設定してください",
            exit_code=9,
        )
    raise KeychainError(
        f"Keychain lookup failed (service={service}, account={account}). "
        "未登録なら README の Keychain 登録手順を実施してください"
    )


def mask(t):
    if not t:
        return "(empty)"
    if len(t) <= 6:
        return f"(len={len(t)})"
    return f"{t[:4]}...{t[-2:]} (len={len(t)})"


def main():
    p = argparse.ArgumentParser(description="MF掛け払い APIキーの Keychain 取得確認 (本体は表示しない)")
    p.add_argument("--service")
    p.add_argument("--account")
    p.add_argument("--check", action="store_true", help="取得可否のみ確認 (マスク表示)")
    a = p.parse_args()
    service = a.service or _service()
    account = a.account or _account()
    try:
        t = get_api_key(service=service, account=account)
    except KeychainError as e:
        sys.stderr.write(f"[mfk_keychain] {e}\n")
        return e.exit_code
    print(f"OK service={service} account={account} {mask(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
