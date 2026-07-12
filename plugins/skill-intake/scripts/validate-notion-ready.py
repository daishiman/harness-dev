#!/usr/bin/env python3
"""Check Notion config, fixed DB target, and token availability without printing secrets."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-key", default="hearing-sheet")
    parser.add_argument("--check-api", action="store_true", help="Also perform a read-only Notion database GET")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args()

    # mmdc preflight (execution-contract.md 終了コード規約: 3 = DEPENDENCY_ERROR)。
    # render 系 (render_to_image.py / render_to_svg.py) が mmdc 必須のため publish 前に fail-fast する。
    if shutil.which("mmdc") is None:
        print(
            "[check_notion_ready] mmdc (Mermaid CLI) が見つかりません。図の描画に必須です。\n"
            "導入手順:\n"
            "  1. Node.js をインストール (https://nodejs.org)\n"
            "  2. ターミナルで: npm install -g @mermaid-js/mermaid-cli\n"
            "  3. mmdc --version が表示されれば導入完了",
            file=sys.stderr,
        )
        return 3

    try:
        cfg = notion_config.load_config()
    except Exception as exc:
        print(f"[check_notion_ready] config error: {exc}", file=sys.stderr)
        return 2
    if not cfg:
        print("[check_notion_ready] config missing (.notion-config.json or notion-config.fixed.json)", file=sys.stderr)
        return 2

    db_id = notion_config.get_db_id(args.database_key)
    if not db_id:
        print(f"[check_notion_ready] databases.{args.database_key}.db_id missing", file=sys.stderr)
        return 2

    token = notion_config.get_token(cfg)
    if not token:
        print(
            "[check_notion_ready] token unavailable "
            "(Keychain, or NOTION_TOKEN with INTAKE_ALLOW_ENV_TOKEN=1)",
            file=sys.stderr,
        )
        return 44

    result = {
        "ok": True,
        "config_path": cfg.get("__path__"),
        "database_key": args.database_key,
        "database_id": db_id,
        "parent_page_id": notion_config.get_parent_page_id(),
        "token": "available",
        "mmdc": "available",
        "api": "not_checked",
    }

    if args.check_api:
        from notion_http import NotionHttpError, get_database

        try:
            db = get_database(db_id)
        except NotionHttpError as exc:
            print(f"[check_notion_ready] Notion database GET failed: {exc}", file=sys.stderr)
            return 44 if getattr(exc, "status", None) == 401 else 1
        result["api"] = "ok"
        result["database_title"] = "".join(t.get("plain_text", "") for t in db.get("title", []))
        result["property_count"] = len(db.get("properties", {}))

    if args.json_out:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            "OK Notion ready "
            f"config={result['config_path']} "
            f"database={result['database_id']} "
            f"token={result['token']} "
            f"api={result['api']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
