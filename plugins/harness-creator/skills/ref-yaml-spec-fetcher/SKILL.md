---
name: ref-yaml-spec-fetcher
description: YAML仕様が変わったか確認するとき、公式仕様との差分を確認するときに使う。
disable-model-invocation: false
allowed-tools:
  - Read
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-18
version: 0.1.0
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs: [prompts/R1-search-summarize.md]
---

# ref-yaml-spec-fetcher

## Purpose & Output Contract

Claude Code 公式 YAML frontmatter 仕様のローカルキャッシュを提供する（PF-G1-001）。

**入力**: なし（Read-only辞書型）
**出力**: `references/yaml-spec-cache.md` の内容（最終取得日時付き）

**更新方式**: GitHub Actions（`update-yaml-spec.yml`）による週次自動取得を正式運用とする。
実仕様ページ群（skills / settings / sub-agents / hooks / permissions / agent-teams / commands / plugins / plugins-reference / output-styles / tools-reference）と製品 CHANGELOG を取得して `references/yaml-spec-cache.md` を更新し、
変更時は `references/spec-diff-history.md` へ差分を記録して dedup 付きの spec-drift issue を起票する。
手動取得は Actions 障害時の fallback とし、担当者（`owner: team-platform`）が下記手順に従う。

## Key Rules

1. **Read-only**: この ref スキル自身はファイルを書き込まない。キャッシュと差分履歴への書き込みは `update-yaml-spec.yml`（GitHub Actions）が担う。
2. **キャッシュ参照**: 直接ネットワーク取得しない。`references/yaml-spec-cache.md` を Read する。
3. **鮮度確認**: `last_fetched:` メタデータで取得日時を確認し、30日超過なら更新を推奨する。
4. **差分報告**: 現行 `03-yaml-frontmatter-reference.md` との差分を指摘する。

## 参照ファイル

- `references/yaml-spec-cache.md` — 公式仕様の週次キャッシュ
- `references/spec-diff-history.md` — 過去の差分履歴

## 公式ソース

- Claude Code Skills: https://docs.claude.com/en/docs/claude-code/skills
- Claude Code Settings: https://docs.claude.com/en/docs/claude-code/settings

## 手動取得手順（fallback・Actions障害時）

1. 上記公式ソースをブラウザで開き、frontmatter 仕様セクションを目視確認する。
2. 変更がある場合は `references/yaml-spec-cache.md` の本文を更新し、frontmatter の `last_fetched:` を当日 ISO 日付に書き換える。
3. 旧版との差分（追加/削除/変更フィールド）を `references/spec-diff-history.md` に追記する（日付・変更要約・出典 URL）。
4. 30日経過しても更新が無い場合は `last_fetched:` のみ更新し「変更なし確認」と記録する。
5. 自動化は完了済（`update-yaml-spec.yml`）。今後の見直しは公式が機械可読スキーマ（JSON Schema 等）を提供した時点で `run-skill-rubric-governance` の Proposal として再評価する。
