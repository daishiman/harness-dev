#!/usr/bin/env python3
"""`.notion-config.json` が repo-slug namespacing 規約を満たすか機械検査。

検査項目 (全て独立 exit code 1 失敗扱い):
  L1. keychain_service が `notion-api-key.<slug>` 形式 (legacy 裸 `notion-api-key` を拒否)
  L2. keychain_account が空でなく、placeholder `<REPLACE_WITH_REPO_SLUG>` を含まない
  L3. databases.*.db_id が placeholder `<your-*-db-id>` のままになっていない
  L4. keychain_service の slug 部分が git remote basename と一致 (mismatch は warn)
  L5. Keychain に該当 entry が登録済 (macOS only, --skip-keychain で抑止可)

Usage:
  python3 scripts/lint-notion-config.py
  python3 scripts/lint-notion-config.py --skip-keychain   # CI 用
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".notion-config.json"

LEGACY_SERVICE = "notion-api-key"  # 裸 (slug 無し) は collision risk
SERVICE_PATTERN = re.compile(r"^notion-api-key\.[a-zA-Z0-9._-]+$")
SLUG_PLACEHOLDER = "<REPLACE_WITH_REPO_SLUG>"
DB_ID_PLACEHOLDER_PATTERN = re.compile(r"^<your-[a-z-]+-db-id>$")


def derive_slug() -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return url.rstrip("/").split("/")[-1].removesuffix(".git") or None
    except subprocess.CalledProcessError:
        return None


def check_keychain(service: str, account: str) -> bool:
    if sys.platform != "darwin":
        return True
    res = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account],
        capture_output=True, text=True,
    )
    return res.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-keychain", action="store_true", help="L5 をスキップ (CI 用)")
    args = ap.parse_args()

    if not CONFIG.exists():
        print(f"[lint-notion-config] WARN: {CONFIG} not found. "
              f"Run `python3 scripts/build-notion-config.py` to create it.", file=sys.stderr)
        return 0  # warn-and-skip (config 未配置 repo は対象外)

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    service = cfg.get("keychain_service", "")
    account = cfg.get("keychain_account", "")

    # L1
    if service == LEGACY_SERVICE:
        errors.append(
            f"L1: keychain_service='{service}' は legacy 裸名 (global collision risk)。"
            f" `notion-api-key.<slug>` 形式に変更し Keychain も移行すること。"
        )
    elif not SERVICE_PATTERN.match(service):
        errors.append(f"L1: keychain_service='{service}' が `notion-api-key.<slug>` 形式でない")

    # L2
    if not account or SLUG_PLACEHOLDER in account:
        errors.append(f"L2: keychain_account='{account}' が未設定 or placeholder")

    # L3
    for key, ent in (cfg.get("databases") or {}).items():
        db_id = (ent or {}).get("db_id", "")
        if not db_id or DB_ID_PLACEHOLDER_PATTERN.match(db_id):
            errors.append(f"L3: databases.{key}.db_id='{db_id}' が placeholder のまま")

    # L4
    slug = derive_slug()
    if slug and service.startswith("notion-api-key."):
        cfg_slug = service.split(".", 1)[1]
        if cfg_slug != slug:
            warnings.append(
                f"L4: keychain_service slug='{cfg_slug}' が git remote basename='{slug}' と不一致"
            )
        if account and account != slug:
            warnings.append(f"L4: keychain_account='{account}' が git remote basename='{slug}' と不一致")

    # L5
    if not args.skip_keychain and not errors:
        if not check_keychain(service, account):
            errors.append(
                f"L5: Keychain entry 未登録 (service={service}, account={account})。"
                f" `python3 scripts/build-notion-config.py --print-keychain-cmd` で登録コマンドを表示"
            )

    for w in warnings:
        print(f"[lint-notion-config] WARN {w}", file=sys.stderr)
    for e in errors:
        print(f"[lint-notion-config] ERR  {e}", file=sys.stderr)

    if errors:
        return 1
    print(f"[lint-notion-config] OK service={service} account={account} "
          f"dbs={len(cfg.get('databases') or {})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
