---
name: run-mf-invoice-db-setup
description: 発行漏れチェック用のNotion DBを初回構築したいとき、DBのプロパティ設計を作り直したいときに使う。
argument-hint: "[--parent-page-id <id>]"
allowed-tools: Read, Bash, Skill
entrypoint: run-mf-invoice-db-setup
---

# /run-mf-invoice-db-setup

`$ARGUMENTS` を `run-mf-invoice-db-setup` スキルに渡し、簡易差集合フロー (`/run-mf-invoice-check`) 用の Notion DB『請求書チェック_DB』へ冪等にスキーマを適用 (不足プロパティ追加・タイトル列リネーム) する。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-db-setup`。

> 請求確認シート基準の DB1/DB2 (`/run-mf-invoice-reconcile` 用) は `scripts/build_reconcile_dbs.py` で用意する (本コマンドの対象外)。

## 振る舞い

1. `Skill(run-mf-invoice-db-setup, args="$ARGUMENTS")` を呼ぶ。
2. `database_id` 既定 DB にスキーマ適用 → verify。`--parent-page-id` 指定時は親ページ配下へ新規 DB を作成し id を `.mf-kessai-config.json` に記録する。

## 実行コード

```bash
SK="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills"
python3 "$SK/run-mf-invoice-db-setup/scripts/build_notion_db.py"
python3 "$SK/run-mf-invoice-db-setup/scripts/verify_db_schema.py"
```
