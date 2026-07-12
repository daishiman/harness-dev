#!/usr/bin/env python3
# /// script
# name: keychain_get_secret
# purpose: macOS Keychain から Service Account 鍵 JSON 等の機密を取得する唯一の経路。
# inputs:
#   - argv: --service --account --check
# outputs:
#   - stdout: マスク表示のみ(生値出力は廃止)
#   - exit: 0=OK / 2=hook 未経由 / 44=Keychain lookup 失敗
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""macOS Keychain から機密(Service Account 鍵 JSON 等)を取得する唯一の経路。

命名規約: service=gdrive-service-account.<keychain-prefix> 固定 / account=<用途>/<資格情報種別>。
本スキル既定 account=contract-generate/service-account-json。
plugins/skill-intake/scripts/keychain_get_secret.py のパターンに準拠。
"""

import argparse
import os
import subprocess
import sys

from tenant_runtime import credential_ref

DEFAULT_SERVICE = ""
DEFAULT_ACCOUNT = "contract-generate/service-account-json"


def _service():
    return os.environ.get("GDRIVE_KEYCHAIN_SERVICE") or credential_ref("gdrive-service-account")[0]


def _account():
    return os.environ.get("GDRIVE_KEYCHAIN_ACCOUNT") or credential_ref("gdrive-service-account")[1]


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def get_secret(service=None, account=None):
    service = service or _service()
    account = account or _account()
    if sys.platform != "darwin":
        raise KeychainError(f"unsupported platform: {sys.platform} (macOS only)")
    res = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise KeychainError(
            f"Keychain lookup failed (service={service}, account={account}): "
            + (res.stderr or "").strip()
        )
    token = (res.stdout or "").rstrip("\n")
    if not token:
        raise KeychainError("Keychain returned empty secret")
    return token


def mask(t):
    if not t:
        return "(empty)"
    return f"{t[:4]}... (len={len(t)})"


def main():
    if os.environ.get("CLAUDE_HOOK_INVOKED") != "1":
        sys.stderr.write("[keychain_get_secret] hook 経由で実行してください\n")
        return 2
    p = argparse.ArgumentParser()
    p.add_argument("--service")
    p.add_argument("--account")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    service = a.service or _service()
    account = a.account or _account()
    try:
        t = get_secret(service=service, account=account)
    except KeychainError as e:
        sys.stderr.write(f"[keychain_get_secret] {e}\n")
        return e.exit_code
    if a.check:
        print(f"OK {mask(t)}")
    else:
        print(f"OK service={service} account={account} {mask(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
