---
name: intake
description: ヒアリングインタビューを起動 (run-skill-intake, 11 phase) — 5 軸ヒアリング・図解マスト・指定 Notion ページ公開まで一気通貫
argument-hint: "[topic] [--page-url <notion-page-url>|--page-id <notion-page-id>] [--database-id <notion-db-id>]"
---

# /intake

ユーザー要望 `$ARGUMENTS` を受け取り、`run-skill-intake` スキルを起動する。引数省略時は kickoff フェーズで対話的に topic を確定する。`--page-url` / `--page-id` が含まれる場合は、Phase 10 publish まで `notion_target` として必ず伝搬し、指定ページを PATCH 更新する。指定ページが解決できない場合は新規ページを作らず停止する。

## 振る舞い

1. `Skill(run-skill-intake, args="$ARGUMENTS")` を呼ぶ。`$ARGUMENTS` 内の `--page-url` / `--page-id` / `--database-id` は Notion publish の明示指定として扱う。
2. スキル側の 11 phase (kickoff → … → finalize → Notion publish → next-action) が `workflow-manifest.json` 順に起動する。
3. Gate A (summarizer) でユーザー承認を得てから Notion 公開に進む。
4. 完了後、Markdown 正本 / JSON 副本 / Notion URL のパスを返す。
5. **スキル生成は実行しない**: ワークフローは Phase 11 (next-action) の `mode` 推奨提示で**完結・停止**する。`/intake` は `run-skill-create` / `run-build-skill` / `capability-build` 等を自動起動しない。スキルを実際に作成したい場合は、ユーザーが別途明示的に `run-skill-create` を起動する (intake はヒアリング〜Notion 公開〜推奨までを担う独立フロー)。

## 事前条件

- `plugins/skill-intake/scripts/validate-notion-ready.py --check-api` が PASS すること。PASS 済みなら API キー / Notion トークンは再質問しない。
- 対象 Notion DB (`--database-id` / `INTAKE_NOTION_DATABASE_ID` / `.notion-config.json#databases.hearing-sheet.db_id` / `notion-config.fixed.json#databases.hearing-sheet.db_id` のいずれかで指定) に PAT / Integration が Connections 追加されていること。
- 既存 Notion ページへ出力する場合は `--page-url` または `--page-id` を指定すること。指定された場合、publish は update 専用になり create へフォールバックしない。

## 失敗時

- exit 44 (Keychain 未登録): `keychain-setup.md` を案内
- HTTP 401/403 (Notion 認証/権限): PAT/Integration の Connections 設定を確認
- verify_notion_assets FAIL: 図解 PNG 不足。再生成案内
- exit 51 (page_id 未解決): `--page-url` / `--page-id` を指定し直す。初回作成は明示的な create 用導線以外では行わない
