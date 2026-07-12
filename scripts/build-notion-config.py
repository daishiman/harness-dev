#!/usr/bin/env python3
"""新規 repo (symlink先含む) で .notion-config.json を repo-slug namespacing 付きで生成する。

Usage:
  python3 scripts/build-notion-config.py            # 対話モード (デフォルト)
  python3 scripts/build-notion-config.py --slug harness --non-interactive --force
  python3 scripts/build-notion-config.py --print-keychain-cmd   # Keychain 登録コマンドのみ表示

ゴール: setup を「手で書く 3 ファイル」から「1 コマンド」に圧縮し、
Keychain service/account 名に repo slug を必ず含めることで `notion-api-key` グローバル衝突を物理的に防ぐ。

冪等性: 既存 .notion-config.json があれば --force 無しでは abort。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".notion-config.json"
EXAMPLE = ROOT / ".notion-config.example.json"


def derive_slug() -> str:
    """git remote origin url から basename を取得 → なければ repo-root ディレクトリ名。"""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        slug = url.rstrip("/").split("/")[-1].removesuffix(".git")
        if slug:
            return slug
    except subprocess.CalledProcessError:
        pass
    return ROOT.name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="repo slug (default: git remote basename or dir name)")
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--force", action="store_true", help="既存 .notion-config.json を上書き")
    ap.add_argument("--print-keychain-cmd", action="store_true",
                    help="Keychain 登録コマンドのみ stdout に出す (config は書かない)")
    ap.add_argument("--parent-page-id", default="")
    ap.add_argument("--parent-page-url", default="")
    ap.add_argument("--skill-list-db", default="")
    ap.add_argument("--hearing-sheet-db", default="")
    ap.add_argument("--improvement-request-db", default="")
    args = ap.parse_args()

    slug = args.slug or derive_slug()
    service = f"notion-api-key.{slug}"
    account = slug

    keychain_cmd = (
        f"security add-generic-password -s {service} -a {account} "
        f"-w 'secret_xxxxxxxxxxxxxxxxxxxx' -U"
    )

    if args.print_keychain_cmd:
        print(keychain_cmd)
        return 0

    if CONFIG.exists() and not args.force:
        print(f"[ERR] {CONFIG} already exists. Use --force to overwrite.", file=sys.stderr)
        return 2

    if not args.non_interactive:
        print(f"[build-notion-config] repo slug: {slug}")
        print(f"[build-notion-config] keychain_service: {service}")
        print(f"[build-notion-config] keychain_account: {account}")
        ans = input("Continue? [Y/n]: ").strip().lower()
        if ans and ans != "y":
            print("aborted.")
            return 1

    template = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    template.pop("_comment", None)
    template["keychain_service"] = service
    template["keychain_account"] = account
    template.setdefault("parent_page", {})
    template["parent_page"]["page_id"] = args.parent_page_id or "<your-parent-page-id>"
    template["parent_page"]["page_url"] = args.parent_page_url or "<your-parent-page-url>"
    template["databases"]["skill-list"]["db_id"] = args.skill_list_db or "<your-skill-list-db-id>"
    template["databases"]["hearing-sheet"]["db_id"] = args.hearing_sheet_db or "<your-hearing-sheet-db-id>"
    template["databases"]["improvement-request"]["db_id"] = args.improvement_request_db or "<your-improvement-request-db-id>"

    CONFIG.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[build-notion-config] wrote {CONFIG}")
    print()
    print("Next steps:")
    print(f"  1. Edit {CONFIG.name} and fill in parent page + 3 Notion DB IDs (replace <your-*> placeholders).")
    print(f"  2. Register your Notion API token to Keychain:")
    print(f"       {keychain_cmd}")
    print(f"     (replace secret_xxxx with your actual integration token)")
    print(f"  3. Verify:")
    print(f"       python3 plugins/harness-creator/scripts/notion_config.py")
    print(f"       python3 plugins/skill-intake/scripts/keychain_get_secret.py "
          f"--service {service} --account {account} --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
