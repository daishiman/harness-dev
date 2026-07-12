---
name: ref-skill-glossary
description: 未知の用語に遭遇したとき、用語統一を確認するときに読む。
disable-model-invocation: true
user-invocable: false
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

# ref-skill-glossary

## Purpose & Output Contract

Skill設計に登場する用語の正本辞書。Read専用、評価・生成は行わない。

**入力**: 不明な用語（例: "Goodhart", "deep-merge", "rubric_refs"）
**出力**: `references/terms.md` 内の該当エントリ。各エントリは「定義 / 文脈 / 関連条文」。

**禁則**: 用語の新規追加は PR レビュー経由。本SKILLは検索インデックスのみを提供。

## Key Rules

1. **正本は references/terms.md**: SKILL.md 本文は索引と発動条件に限る。
2. **disable-model-invocation: true**: モデル自動発動は禁止、必要時に明示Readする。
3. **kind=reference**: 評価器でも生成器でもない、純粋資料層（27章）。

## Steps

1. 不明用語を確認。
2. `references/terms.md` を Grep で検索（例: `grep -n "^## Goodhart" references/terms.md`）。
3. ヒットした定義ブロックを Read で抜粋。

## Gotchas

- **辞書の肥大化**: 用語数 > 40 になったら章ごとに `references/terms-*.md` に分割。
- **正本の二重化禁止**: ルール本体（rubric.json）の定義は再掲しない。リンクのみ。
- **言語**: 用語は英語キーで保存、説明文は日本語可。

## Additional Resources

- `references/terms.md` — 用語集本体
- upstream: `ref-skill-design-rubric/rubric.json`（ルール定義の正本）
