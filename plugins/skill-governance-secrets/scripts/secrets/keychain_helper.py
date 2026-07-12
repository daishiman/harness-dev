#!/usr/bin/env python3
# /// script
# name: keychain-helper
# purpose: Read macOS Keychain secrets for sink adapters without printing secret values.
# inputs:
#   - import: get_secret(ref)
# outputs:
#   - return: secret string to caller only
#   - exception: sanitized SecretError
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""macOS Keychainからsecretを取得する共通ヘルパー。

CRITICAL: この関数は adapter内部のsubprocessから呼ぶこと。
取得したsecretは絶対にstdoutに出さない、エラーメッセージにも含めない。
"""
from __future__ import annotations
import subprocess
import sys
import re


class SecretError(Exception):
    pass


def get_secret(ref: str) -> str:
    """`keychain:service/account` 形式の参照からKeychain値を取得。

    取得失敗時はSecretErrorを送出。値自体はexceptionメッセージに含めない。
    """
    if not ref.startswith("keychain:"):
        raise SecretError(f"unsupported ref scheme: {ref.split(':')[0]}")

    rest = ref[len("keychain:"):]
    if "/" not in rest:
        raise SecretError("invalid keychain ref format, expected keychain:service/account")
    service, account = rest.split("/", 1)

    # 安全のため service/account は英数字-_のみ許可
    if not re.match(r"^[A-Za-z0-9_.-]+$", service) or not re.match(r"^[A-Za-z0-9_.-]+$", account):
        raise SecretError("invalid characters in service/account")

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, check=True, timeout=10
        )
    except subprocess.CalledProcessError:
        raise SecretError(f"secret not found in keychain: service={service} account={account}")
    except subprocess.TimeoutExpired:
        raise SecretError("keychain access timed out")

    secret = result.stdout.strip()
    if not secret:
        raise SecretError("keychain returned empty value")
    return secret


def sanitize_error(message: str, secrets: list[str]) -> str:
    """エラーメッセージから secret 値を除去。"""
    sanitized = message
    for s in secrets:
        if s and len(s) >= 4:
            sanitized = sanitized.replace(s, "[REDACTED]")
    return sanitized


if __name__ == "__main__":
    # この経路は使用禁止: 直接実行するとstdoutにsecretが出る
    print("ERROR: keychain_helper.py is a library module. Do not run directly.", file=sys.stderr)
    sys.exit(1)
