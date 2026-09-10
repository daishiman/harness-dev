#!/usr/bin/env python3
# /// script
# name: secret-helper
# purpose: Resolve keychain_helper lazily so credential-free adapter calls stay runnable.
# inputs:
#   - callers: sink adapters under scripts/adapters/
# outputs:
#   - python API: get_secret / sanitize_error / SecretError
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""keychain_helper への遅延 bridge。

`--help` と `--dry-run` は credential を一切参照しない。にもかかわらず module
読込時に keychain_helper を import すると、provider (skill-governance-secrets)
が同居しない配布形態では argparse へ到達する前に ModuleNotFoundError で落ち、
**副作用の無い呼び出しこそが実行不能**になる。secret が実際に要る時点まで解決を
遅らせ、解決できない場合も traceback ではなく Sink Contract v1.0 の failure を
返せるよう `SecretError` へ正規化する。
"""
from __future__ import annotations

import sys
from pathlib import Path

_SECRETS_DIR = Path(__file__).resolve().parent / "secrets"


class SecretError(Exception):
    """secret の解決・取得に失敗した。adapter は exit 2 の failure へ畳む。"""


def _load():
    """keychain_helper module を解決する。失敗は SecretError へ正規化する。"""
    path = str(_SECRETS_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import keychain_helper  # noqa: PLC0415
    except ImportError as exc:
        raise SecretError(
            "keychain_helper unavailable: secret 参照には skill-governance-secrets の "
            f"secrets/keychain_helper.py が {_SECRETS_DIR} へ配備されている必要がある "
            f"({exc})"
        ) from exc
    return keychain_helper


def get_secret(ref: str) -> str:
    """keychain から secret を取得する。provider 未配備も取得失敗もSecretError。"""
    module = _load()
    try:
        return module.get_secret(ref)
    except Exception as exc:  # keychain_helper 側の SecretError を含む
        if isinstance(exc, SecretError):
            raise
        raise SecretError(str(exc)) from exc


def sanitize_error(message: object, secrets: list[str]) -> str:
    """secret 値を伏せた1行へ畳む。

    provider 未配備時はここが最後の防壁になるため、bridge 自身が置換 fallback を
    持つ。provider があればその実装を正本として委譲する。
    """
    try:
        return _load().sanitize_error(message, secrets)
    except SecretError:
        text = str(message)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return text
