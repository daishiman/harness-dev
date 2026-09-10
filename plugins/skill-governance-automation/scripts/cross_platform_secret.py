#!/usr/bin/env python3
# /// script
# name: cross-platform-secret
# purpose: Get, set, or probe secrets through the platform-specific fallback chain.
# inputs:
#   - argv: --get, --set, --value, --probe
# outputs:
#   - stdout: JSON status without secret leakage
#   - stderr: sanitized errors
# contexts: [E]
# network: false
# write-scope: output-dir
# dependencies: []
# requires-python: ">=3.9"
# ///
"""クロスプラットフォーム secret 取得の薄ラッパー。

doc/22 cross-platform-runtime に準拠した OS 分岐エントリポイント。
no-deps 原則 (stdlib のみ) を維持しつつ、Mac/Linux/Windows/unknown に
フォールバックする。既存の scripts/secrets/keychain_helper.py を変更せず、
mac 経路ではそれを subprocess 経由で呼び出すアーキテクチャに統一する。

優先順位:
  1. environment variable HARNESS_SECRET_<SLUG>_<KEY>  (全OS共通フォールバック)
  2. OS native backend:
       mac     -> scripts/secrets/keychain_helper.py (security CLI)
       linux   -> $XDG_CONFIG_HOME/harness/secrets.json (chmod 600)
       windows -> base64 file fallback (not encrypted)
       unknown -> stderr で停止
  3. いずれも失敗時: status=failure を JSON で返却

usage:
  python3 cross_platform_secret.py --get <KEY>
  python3 cross_platform_secret.py --set <KEY> --value <VALUE>
  python3 cross_platform_secret.py --probe        # OS/backend 情報のみ出力
"""
from __future__ import annotations

import argparse
import base64
import hmac
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from tenant_runtime import TenantConfigError, active_tenant_slug, credential_ref, scoped_secret_env


def detect_os() -> str:
    s = platform.system().lower()
    if s == "darwin":
        return "mac"
    if s == "linux":
        return "linux"
    if s == "windows":
        return "windows"
    return "unknown"


def _env_lookup(key: str) -> str | None:
    """Resolve only the active tenant's namespaced environment variable."""
    return os.environ.get(scoped_secret_env(key))


def _xdg_path(key: str) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "harness" / active_tenant_slug() / "secrets.json"


def _linux_get(key: str) -> str | None:
    p = _xdg_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get(key)
    except (OSError, json.JSONDecodeError):
        return None


def _linux_set(key: str, value: str) -> bool:
    p = _xdg_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[key] = value
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.chmod(p, 0o600)
    return True


def _windows_get(key: str) -> str | None:
    """Windows 用の base64 ファイルフォールバック。

    DPAPI ではないため暗号化として扱わない。利用者には環境変数フォールバックか
    OS ネイティブ secret backend の追加実装を推奨する。
    """
    storage = Path(os.environ.get("APPDATA", str(Path.home()))) / "harness" / active_tenant_slug() / "secrets.bin"
    if not storage.exists():
        return None
    try:
        encrypted_b64 = storage.read_text(encoding="utf-8")
        data = json.loads(base64.b64decode(encrypted_b64).decode("utf-8"))
        return data.get(key)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _windows_set(key: str, value: str) -> bool:
    """Windows 用の base64 ファイルフォールバック。DPAPI ではない。"""
    storage = Path(os.environ.get("APPDATA", str(Path.home()))) / "harness" / active_tenant_slug() / "secrets.bin"
    storage.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if storage.exists():
        try:
            data = json.loads(base64.b64decode(storage.read_text(encoding="utf-8")).decode("utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            data = {}
    data[key] = value
    payload = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    storage.write_text(payload, encoding="utf-8")
    return True


def _mac_get(key: str) -> str | None:
    service, account = credential_ref(key)
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def get_secret(key: str) -> dict:
    """secret を取得して dict で返す。

    返却 contract:
      { status: "ok"|"failure", os: str, backend: str, value: str|None, errors: [str] }
    """
    os_kind = detect_os()
    errors: list[str] = []

    # 1. env 優先
    try:
        v = _env_lookup(key)
    except TenantConfigError as exc:
        return {"status": "failure", "os": os_kind, "backend": "none", "value": None, "errors": [str(exc)]}
    if v is not None:
        return {"status": "ok", "os": os_kind, "backend": "env", "value": v, "errors": []}

    # 2. OS native backend
    if os_kind == "mac":
        v = _mac_get(key)
        if v is not None:
            return {"status": "ok", "os": "mac", "backend": "keychain", "value": v, "errors": []}
        errors.append("mac keychain lookup failed")
    elif os_kind == "linux":
        v = _linux_get(key)
        if v is not None:
            return {"status": "ok", "os": "linux", "backend": "xdg", "value": v, "errors": []}
        errors.append("linux xdg lookup failed")
    elif os_kind == "windows":
        v = _windows_get(key)
        if v is not None:
            return {"status": "ok", "os": "windows", "backend": "base64-file", "value": v, "errors": []}
        errors.append("windows base64-file lookup failed")
    else:
        errors.append("OS判定失敗。tenant-scoped HARNESS_SECRET_<SLUG>_<PURPOSE> を設定してください")

    return {"status": "failure", "os": os_kind, "backend": "none", "value": None, "errors": errors}


def set_secret(key: str, value: str) -> dict:
    os_kind = detect_os()
    if os_kind == "mac":
        try:
            service, account = credential_ref(key)
        except TenantConfigError as exc:
            return {"status": "failure", "os": "mac", "backend": "none", "errors": [str(exc)]}
        try:
            r = subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-U",
                    "-a",
                    account,
                    "-s",
                    service,
                    "-w",
                    value,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0:
                return {"status": "ok", "os": "mac", "backend": "keychain"}
            return {"status": "failure", "os": "mac", "backend": "keychain",
                    "errors": ["security add-generic-password failed"]}
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"status": "failure", "os": "mac", "backend": "keychain", "errors": [str(e)]}
    if os_kind == "linux":
        ok = _linux_set(key, value)
        return {"status": "ok" if ok else "failure", "os": "linux", "backend": "xdg"}
    if os_kind == "windows":
        ok = _windows_set(key, value)
        return {"status": "ok" if ok else "failure", "os": "windows", "backend": "base64-file"}
    return {"status": "failure", "os": os_kind, "backend": "none",
            "errors": ["OS判定失敗。tenant-scoped HARNESS_SECRET_<SLUG>_<PURPOSE> で渡してください"]}


def probe() -> dict:
    return {
        "os": detect_os(),
        "python": sys.version.split()[0],
        "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
        "supported_backends": {
            "mac": "keychain (security CLI)",
            "linux": "$XDG_CONFIG_HOME/harness/<slug>/secrets.json (chmod 600)",
            "windows": "base64 file fallback (not encrypted)",
            "unknown": "tenant-scoped env only",
        },
        "fallback_priority": ["env", "os-native", "failure"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--get", metavar="KEY")
    ap.add_argument("--set", metavar="KEY")
    ap.add_argument("--value", default=None)
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    if args.probe:
        print(json.dumps(probe(), ensure_ascii=False, indent=2))
        return 0

    if args.get:
        r = get_secret(args.get)
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["status"] == "ok" else 1

    if args.set:
        if args.value is None:
            print(json.dumps({"status": "failure", "errors": ["--value required with --set"]}))
            return 2
        r = set_secret(args.set, args.value)
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["status"] == "ok" else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
