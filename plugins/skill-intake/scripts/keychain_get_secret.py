#!/usr/bin/env python3
"""macOS Keychain から Notion トークンを取得する唯一の経路。"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from tenant_runtime import credential_ref

DEFAULT_SERVICE = ''
DEFAULT_ACCOUNT = ''


def _load_config_if_available():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import notion_config
    return notion_config.load_config()


def _default_service():
    """毎呼出 env を再評価 (module-level 定数だと同一プロセスでの repo 切替に追随できない)。
    .notion-config.json がある場合は keychain_service を尊重する。
    """
    if os.environ.get('INTAKE_KEYCHAIN_SERVICE'):
        return os.environ['INTAKE_KEYCHAIN_SERVICE']
    cfg = _load_config_if_available()
    if cfg and cfg.get('keychain_service'):
        return cfg['keychain_service']
    return credential_ref('notion-api-key')[0]


def _default_account():
    if os.environ.get('INTAKE_KEYCHAIN_ACCOUNT'):
        return os.environ['INTAKE_KEYCHAIN_ACCOUNT']
    cfg = _load_config_if_available()
    if cfg and cfg.get('keychain_account'):
        return cfg['keychain_account']
    return credential_ref('notion-api-key')[1]


# 後方互換 alias。実行時解決は _default_* を使う。
SERVICE = DEFAULT_SERVICE
ACCOUNT = DEFAULT_ACCOUNT


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def get_secret(service=None, account=None):
    service = service or _default_service()
    account = account or _default_account()
    if sys.platform != 'darwin':
        raise KeychainError(f'unsupported platform: {sys.platform} (macOS only)')
    res = subprocess.run(
        ['/usr/bin/security', 'find-generic-password', '-s', service, '-a', account, '-w'],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise KeychainError(
            f'Keychain lookup failed (service={service}, account={account}): '
            + (res.stderr or '').strip()
        )
    token = (res.stdout or '').rstrip('\n')
    if not token:
        raise KeychainError('Keychain returned empty token')
    return token


def mask_token(t):
    if not t:
        return '(empty)'
    return f'{t[:4]}... (len={len(t)})'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--service')
    parser.add_argument('--account')
    parser.add_argument('--env-prefix')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--print-unsafe', action='store_true')
    args = parser.parse_args()

    try:
        service = args.service or _default_service()
        account = args.account or _default_account()
    except Exception as e:
        sys.stderr.write(f'[keychain_get_secret] config error: {e}\n')
        return 2
    try:
        t = get_secret(service=service, account=account)
    except KeychainError as e:
        sys.stderr.write(f'[keychain_get_secret] {e}\n')
        return e.exit_code

    if args.check:
        print(f'OK {mask_token(t)}')
    elif args.print_unsafe:
        sys.stdout.write(t)
    else:
        print(f'OK service={service} account={account} {mask_token(t)}')
        print('hint: use --print-unsafe to emit raw token (avoid in shared terminals)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
