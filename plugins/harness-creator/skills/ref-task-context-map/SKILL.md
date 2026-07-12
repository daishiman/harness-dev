---
name: ref-task-context-map
description: タスク文脈に応じた設計書章番号を調べるとき、動的ロードするべき章を特定するときに読む。
disable-model-invocation: true
user-invocable: false
allowed-tools: [Read]
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

# ref-task-context-map

## Purpose & Output Contract

設計書章番号の静的索引。タスクのキーワードから読むべき章番号を引く。
`run-build-skill` Step 1 での context 予算管理 (CD-005) に使用する。

**入力**: タスクキーワード (例: "Progressive Disclosure", "subagent")
**出力**: `references/task-context-map.yaml` の該当エントリ (章番号リスト)

**禁則**: モデル自動発動なし。Read で静的参照のみ。

## Key Rules

1. **静的索引**: LLM が動的に判断せず、yaml テーブルを Read して返す。
2. **context 予算準拠 (CD-005)**: 全章一括ロード禁止。本スキルで必要章だけを特定してから Read。
3. **正本**: `references/task-context-map.yaml`。追記は PR レビュー経由。

## Steps

1. キーワードを確認。
2. `references/task-context-map.yaml` を Read して該当行を抽出。
3. 章番号リストを返す。

## Gotchas

- **全章一括ロード禁止**: このスキルを使わずに設計書を全部読むのは CD-005 違反。
- **索引の網羅性**: キーワードが見つからない場合は近傍 trigger 候補を `suggestions[]` に返す (exit 0)。sink は schema (`schemas/query-result.schema.json`) が定義する `suggestions` のみ。

## Additional Resources

- `references/task-context-map.yaml` — キーワード→章番号の静的マップ
