#!/usr/bin/env python3
# /// script
# name: setup_send_log_db
# purpose: 送信ログDB の Notion プロパティを仕様書 §9 の期待schemaと照合し、不足プロパティ/select選択肢を冪等に追加する。既定 dry-run (差分表示)、--apply で実適用。--write-config で db_id を .notion-config.json へ焼き込む。
# inputs:
#   - argv: --db-id <id> / --apply / --write-config / --config <path>
#   - keychain: notion-api-key.<keychain-prefix>
# outputs:
#   - stdout: 差分レポート (不足プロパティ・追加結果)
#   - exit: 0=整合 or 適用成功 / 1=差分あり(dry-run) / 2=usage/接続エラー
# contexts: [E, C]
# network: true   # api.notion.com への HTTPS のみ
# write-scope: notion-db-schema   # --apply 時のみ DB プロパティ追加
# dependencies: []
# requires-python: ">=3.9"
# ///
"""送信ログDB セットアップ (仕様書 §9 schema)。

Notion ページURL の id (送信ログDB) を受け、期待プロパティと現状を照合する。不足のみ
冪等に追加し、既存プロパティは変更しない。title 型が「冪等キー」でなければ rename を提案する。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import notion_client, notion_config, secrets, idempotent_log  # noqa: E402

# 期待プロパティ schema (仕様書 §9 送信ログDB schema)
STATUS_OPTIONS = [
    idempotent_log.PLANNED, idempotent_log.RESERVED, idempotent_log.SENDING, idempotent_log.SENT,
    idempotent_log.SKIPPED_IDEMPOTENT, idempotent_log.SKIPPED_VALIDATION,
    idempotent_log.ERROR, idempotent_log.UNKNOWN,
]
REASON_OPTIONS = idempotent_log.REASON_CODES
EXPECTED: dict[str, dict] = {
    "冪等キー": {"title": {}},
    "campaign_id": {"rich_text": {}},
    "plan_hash": {"rich_text": {}},
    "content_hash": {"rich_text": {}},
    "status": {"select": {"options": [{"name": s} for s in STATUS_OPTIONS]}},
    "reason_code": {"select": {"options": [{"name": r} for r in REASON_OPTIONS]}},
    "本文page_id": {"rich_text": {}},
    "宛先page_id": {"rich_text": {}},
    "From": {"rich_text": {}},
    "To": {"rich_text": {}},
    "CC": {"rich_text": {}},
    "件名": {"rich_text": {}},
    "messageId": {"rich_text": {}},
    "reserved_at": {"date": {}},
    "sending_at": {"date": {}},
    "sent_at": {"date": {}},
    "error": {"rich_text": {}},
}


def _type_of(prop: dict) -> str:
    return prop.get("type", "")


def diff_schema(current: dict) -> tuple[dict, list[str], str | None]:
    """現状プロパティと期待を照合。

    Returns (to_add, type_mismatch, title_rename)
        to_add: update_database に渡す追加プロパティ (title 以外)
        type_mismatch: 型が食い違う既存プロパティ名
        title_rename: 既存 title プロパティ名 (≠冪等キー の場合のみ)
    """
    to_add: dict = {}
    mismatch: list[str] = []
    title_rename: str | None = None

    # 既存の title プロパティ名を特定
    cur_title = next((n for n, p in current.items() if _type_of(p) == "title"), None)
    if cur_title and cur_title != "冪等キー":
        title_rename = cur_title

    for name, schema in EXPECTED.items():
        want_type = next(iter(schema))
        if name == "冪等キー":
            continue  # title はリネームで扱う
        cur = current.get(name)
        if cur is None:
            to_add[name] = schema
        elif _type_of(cur) != want_type:
            mismatch.append(f"{name}: 期待={want_type} 現状={_type_of(cur)}")
        elif want_type == "select":
            # select 選択肢の不足を追加
            existing = {o["name"] for o in cur.get("select", {}).get("options", [])}
            missing = [o for o in schema["select"]["options"] if o["name"] not in existing]
            if missing:
                merged = cur.get("select", {}).get("options", []) + missing
                to_add[name] = {"select": {"options": merged}}
    return to_add, mismatch, title_rename


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-id", help="送信ログDB の database id (未指定なら config から解決)")
    ap.add_argument("--apply", action="store_true", help="実際に Notion へプロパティを追加する")
    ap.add_argument("--write-config", action="store_true", help=".notion-config.json に db_id を焼き込む")
    ap.add_argument("--config", help=".notion-config.json パス (NOTION_GMAIL_CONFIG 相当)")
    args = ap.parse_args()

    db_id = args.db_id
    if not db_id:
        try:
            cfg = notion_config.load_config(args.config)
            db_id = notion_config.get_db_id("gmail-send-log", cfg)
        except notion_config.ConfigError as e:
            print(f"[ERROR] --db-id 未指定かつ config 未解決: {e}", file=sys.stderr)
            return 2

    try:
        client = notion_client.NotionClient(secrets.get_notion_api_key())
        db = client.retrieve_database(db_id)
    except (secrets.KeychainError, notion_client.NotionError) as e:
        print(f"[ERROR] Notion 取得失敗: {e}", file=sys.stderr)
        return 2

    current = db.get("properties", {})
    to_add, mismatch, title_rename = diff_schema(current)

    title_txt = "".join(t.get("plain_text", "") for t in db.get("title", []))
    print(f"対象DB: {title_txt or '(無題)'} ({db_id})")
    print(f"現状プロパティ数: {len(current)} / 期待: {len(EXPECTED)}")
    if title_rename:
        print(f"  [title rename 提案] '{title_rename}' → '冪等キー'")
    if mismatch:
        print("  [型不一致 — 手動確認が必要]")
        for m in mismatch:
            print(f"    - {m}")
    if to_add:
        print(f"  [不足/補完プロパティ {len(to_add)} 件]")
        for n in to_add:
            print(f"    + {n}")
    if not to_add and not title_rename and not mismatch:
        print("✅ schema は期待と整合済み。追加不要。")

    if args.write_config:
        print("\n[--write-config] .notion-config.json への db_id 焼き込みは手動で以下を設定してください:")
        print(f'  {{"databases": {{"gmail-send-log": {{"db_id": "{db_id}"}}}}}}')

    if not args.apply:
        if to_add or title_rename:
            print("\n(dry-run) --apply で上記を適用します。型不一致は自動修正しません。")
            return 1
        return 0

    # --apply: title rename と不足追加を実行
    patch: dict = dict(to_add)
    if title_rename:
        patch[title_rename] = {"name": "冪等キー"}
    if patch:
        try:
            client.update_database(db_id, patch)
            print(f"\n✅ {len(patch)} 件のプロパティを追加/更新しました。")
        except notion_client.NotionError as e:
            print(f"[ERROR] プロパティ追加失敗: {e}", file=sys.stderr)
            return 2
    if mismatch:
        print("⚠️ 型不一致は自動修正していません。手動で確認してください。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
