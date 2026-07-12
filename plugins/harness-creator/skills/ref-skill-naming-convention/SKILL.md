---
name: ref-skill-naming-convention
description: Skillを命名するとき、改名するときに読む。
disable-model-invocation: true
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-17
version: 0.1.0
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs: [prompts/R1-search-summarize.md]
---

# ref-skill-naming-convention

## Purpose & Output Contract

Skill 命名規約の正本サマリ（第1〜16条）。
本SKILL.md は要約のみ。条文全文は `references/articles-full.md`。

## Key Rules（条文サマリ）

1. **第1条 形式**: kebab-case、英小文字+数字+ハイフン。
2. **第2条 prefix必須**: `run-` / `ref-` / `assign-` / `wrap-` / `delegate-` のいずれか。
3. **第3条 role-suffix推奨**: `-evaluator` / `-generator` / `-runbook` 等。
4. **第4条 動詞 or 名詞**: run/assign系は動詞、ref/wrap/delegate系は名詞。
5. **第5条 60文字以下**: prefix含む合計。
6. **第6条 予約語回避**: `skill`, `claude`, `anthropic` 単独使用禁止。
7. **第7条 ディレクトリ名 == frontmatter.name**.
8. **第8〜13条 構造**: `templates/`, `references/`, `scripts/`, `examples/` 配下のファイル命名。
9. **第14条 多言語**: description は日本語推奨。動詞ベースの2〜3個のトリガー条件を含むこと（本文も日本語可）。
10. **第15条 改名は alias 経由**: `aliases: [old-name]` で猶予期間。
11. **第16条 forbidden**: `test-` / `tmp-` / `wip-` prefix は本番投入禁止。
12. **第17条 role-suffix 語彙**: `-evaluator` / `-generator` / `-linter` / `-auditor` / `-aggregator` / `-runbook` / `-watcher` / `-dispatcher` を正式語彙とする。新設は governance board 承認が必要。詳細: `references/role-suffix-vocabulary.md`。

## 5 prefix × 4軸 対応

`references/prefix-axis-matrix.md` を参照。
4軸 = (発動主体, context, write権限, 評価対象)。

## Steps

参照用。命名時のフロー:

1. 用途 → prefix選定（matrix 参照）
2. role-suffix を付与（第3条）
3. `python3 scripts/lint-skill-name.py SKILL.md` で第1〜5,7条検証

## Gotchas

- **assign- は user-invocable: false が原則**: 第2条 + 04章。
- **ref- は disable-model-invocation: true 必須**: 自動発動を防ぐ。
- **改名は破壊的変更**: 第15条 alias を必ず付ける（後方互換）。

## Additional Resources

- `references/articles-full.md` — 第1〜16条全文
- `references/decision-table.md` — 主要8ケース裁定表
- `references/prefix-axis-matrix.md` — 5 prefix × 4軸
- `../run-skill-elicit/SKILL.md#onboarding-mode初学者向け3問` — 初学者向け Onboarding mode（Q1/Q2/Q3 から prefix を自動推定）
- lint: `scripts/lint-skill-name.py`
