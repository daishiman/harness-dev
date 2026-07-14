---
name: ref-claude-code-skill-spec
description: frontmatterを記述するとき、subagent/hooksを配線するときに読む。
disable-model-invocation: false
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

# ref-claude-code-skill-spec

## Purpose & Output Contract

Claude Code Skills の仕様サマリ。
公式仕様と {{PROJECT_ROOT}} ローカル規約を区別し、frontmatter・ライフサイクル・Subagent/hook 連携の判断材料を圧縮する。

## Key Rules

1. **公式とローカル規約を区別**: 公式上は `description` 推奨中心。{{PROJECT_ROOT}} 出荷基準では `name`, `description` を必須として lint する。
2. **`disable-model-invocation: true`** で自動発動を抑止（ref系）。
3. **`user-invocable: false`** でユーザー直接呼出抑止（assign系）。
4. **`allowed-tools`** は最小権限。`Bash(python3 *)` のように glob 制限可能。
5. **`context: fork`** で 新規 context（evaluator用、09章）。
6. **`pair`** で対になるSkill宣言（generator↔evaluator）。
7. **frontmatter は YAML 1.2**: タブ禁止、true/false小文字。

## frontmatter フィールド表（要約）

| field | 区分 | 用途 |
|---|---|---|
| name | local required | ディレクトリ名と一致 |
| description | official recommended / local required | 発動条件 exactly 2 trigger |
| disable-model-invocation | official | 自動発動抑止 |
| user-invocable | official | ユーザー直接呼出抑止 |
| allowed-tools | official | tool 承認省略 |
| argument-hint / arguments | official | run系の引数 |
| context | official | fork / inline |
| agent | official | subagent種別 |
| pair | local | 対Skill |
| kind | local | run/ref/assign/wrap/delegate |
| rubric_refs / reference_refs / script_refs | local | 多重継承（29章） |
| merge_strategy / conflict_policy | local | deep-merge / most-specific-wins |
| aliases | local | 改名時の旧名 |

詳細は `references/frontmatter-fields.md`。

## ライフサイクル

1. trigger一致 → 2. frontmatter読込 → 3. SKILL.md本文展開 → 4. references/scripts 必要時ロード → 5. tool実行 → 6. compaction時に保持/捨象判定。

詳細は `references/lifecycle.md`。

## Steps

参照用。frontmatter 書く時は本文の表を見て、不足時に `references/frontmatter-fields.md` へ。

## Gotchas

- **`disable-model-invocation: true` + `user-invocable: true` は意味的に矛盾しないが直感に反する**: ref系を CLI から直接読ませる構成。
- **`context: fork` を付け忘れると evaluator が本体contextを汚染**（Goodhart）。
- **`allowed-tools` で `Bash(*)` は危険**: 必ず glob 制限。
- **trigger は exactly 2**: 03章 hard rule。1個は鍵不足、3個以上は description 肥大化。

## Additional Resources

- `references/frontmatter-fields.md` — 全フィールド詳細表
- `references/lifecycle.md` — 発動・compaction・hook
- `references/subagent-and-hook.md` — Subagent / Agent Teams / hooks（17章）
