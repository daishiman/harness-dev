---
name: ref-yaml-spec-fetcher
description: YAML仕様が変わったか確認するとき、公式仕様との差分を確認するときに使う。
disable-model-invocation: false
allowed-tools:
  - Read
kind: ref
effect: none
owner: team-platform
since: 2026-05-18
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# ref-yaml-spec-fetcher

## Purpose & Output Contract

Claude Code 公式 YAML frontmatter 仕様のローカルキャッシュを提供する（PF-G1-001）。

**入力**: なし（Read-only辞書型）
**出力**: `references/yaml-spec-cache.md` の内容（最終取得日時付き）

**更新方式**: 手動取得を正式手順とする（自動化は意図的に見送り、2026-05-18 判断）。
公式が機械可読配布（llms.txt / 公開 API）を提供していないため、目視取得＋差分記録の人手プロセスを公式運用とする。
週次レビュー担当者（`owner: team-skills`）が下記「手動取得手順」に従って `references/yaml-spec-cache.md` を更新する。

## Key Rules

1. **Read-only**: このスキルはファイルを書き込まない。書き込みは GitHub Actions が行う。
2. **キャッシュ参照**: 直接ネットワーク取得しない。`references/yaml-spec-cache.md` を Read する。
3. **鮮度確認**: `last_fetched:` メタデータで取得日時を確認し、30日超過なら更新を推奨する。
4. **差分報告**: 現行 `03-yaml-frontmatter-reference.md` との差分を指摘する。

## 参照ファイル

- `references/yaml-spec-cache.md` — 公式仕様の週次キャッシュ
- `references/spec-diff-history.md` — 過去の差分履歴

## 公式ソース

- Claude Code Skills: https://docs.claude.com/en/docs/claude-code/skills
- Claude Code Settings: https://docs.claude.com/en/docs/claude-code/settings

## 手動取得手順（週次・正式運用）

1. 上記公式ソースをブラウザで開き、frontmatter 仕様セクションを目視確認する。
2. 変更がある場合は `references/yaml-spec-cache.md` の本文を更新し、frontmatter の `last_fetched:` を当日 ISO 日付に書き換える。
3. 旧版との差分（追加/削除/変更フィールド）を `references/spec-diff-history.md` に追記する（日付・変更要約・出典 URL）。
4. 30日経過しても更新が無い場合は `last_fetched:` のみ更新し「変更なし確認」と記録する。
5. 自動化方針の見直しは公式が機械可読配布（llms.txt / API）を提供した時点で再評価する。`run-skill-rubric-governance` の Proposal として提起する。
