---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Task]
kind: run
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal") }}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly") }}
role_suffix: orchestrator
pair: {{pair_evaluator}}
rubric_refs:
  - ref-skill-design-rubric
  - {{domain_rubric_ref}}
# permissions: 設計書10章§7.4 二段防御。orchestrator は subagent 起動を伴うため
#   settings.json で permissions.deny に破壊的 command を列挙すること。
# TaskCreated hook: file ownership 衝突検出のため scripts/hook-check-file-ownership.py を有効化。
# SubagentStop hook: evaluator JSON 契約検証のため scripts/hook-verify-evaluator-json.py を有効化。
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Boundary
- 入口: {{entry_condition}}
- 出口: 全 Gate PASS + 成果物が `{{artifact_path}}` に書き出される
- 非責務: 個別 generator/evaluator の実装ロジック（各 sub-skill に委譲）

## Orchestration Model

本スキルは設計書09章「評価駆動オーケストレーション」に準拠する multi-phase gate orchestrator である。

### フェーズ一覧

| フェーズ | 役割 | 担当 | Gate |
|---|---|---|---|
| 1 | 要求収集 | {{phase1_skill}} | brief.json 完成 |
| 2 | 生成 | {{phase2_generator}} | P0 lint 全 PASS |
| 3 | 評価 | {{phase3_evaluator}} (context: fork) | score >= threshold |
| 4 | 統合・反映 | self | git diff 確認 + 4条件PASS |

### 最大反復回数
- 改善ループ: **最大3周**（evaluator → generator 戻し）
- 上限到達時: governance フロー (`run-skill-rubric-governance`) にエスカレーション

## Key Rules
- 各 Gate 通過を機械的に判定する（自然言語の「完了しました」を信用しない）
- Phase 3 evaluator は **必ず `context: fork`** で起動する（Sycophancy防止、設計書09章）
- Phase 間 handoff は JSON ファイル経由（`.claude/handoff/{{name}}-<session>.json`）
- PreCompact が走ったら PostCompact で handoff を再読込し goal/next を復元

## ゴールシーク実行
> 固定手順は書かない。Gate を完了チェックリストとし、どの局面をいつ実行するかは AI が都度判断する。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
全 Gate が PASS し、成果物が `{{artifact_path}}` に書き出された状態。

### 完了チェックリスト (Checklist) — これが Gate 群
- [ ] **Gate 1**: brief.json が schema validation を通過した
- [ ] **Gate 2**: 全 P0 lint が exit 0 + git diff --shortstat が >0 行
- [ ] **Gate 3**: evaluator JSON が SubagentStop hook 検証を通過 + `passed: true`
- [ ] **Gate 4**: 4条件（矛盾なし / 漏れなし / 整合性 / 依存関係整合）+ ユーザー最終承認

### ゴールシークループ
1. 未達 Gate を特定 → 2. その Gate を満たす局面（下のカタログ参照）を AI が選んで手順を都度生成 → 3. 実行 → 4. Gate 再判定し `[x]` 更新 → 全 `[x]` まで反復。**最大3周**、超過時は `run-skill-rubric-governance` にエスカレーション。Gate は自然言語の「完了しました」ではなく機械判定する。

### 局面カタログ（順序は都度判断・固定シーケンスではない）

- **要求収集**: `{{phase1_skill}}` を起動し `{{brief_path}}` に brief.json を出力（Gate 1）。
- **生成**: `{{phase2_generator}}` を Task tool 経由で起動。完了時に P0 lint を実行（Gate 2）:
  ```bash
  python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py --skills-dir {{output_dir}}
  python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py {{output_dir}}/SKILL.md
  python3 plugins/skill-governance-lint/scripts/lint-skill-description.py --skills-dir {{output_dir}}
  ```
- **評価（fork）**: `{{phase3_evaluator}}` を `context: fork` で起動（Gate 3）:
  ```yaml
  subagent_type: {{phase3_evaluator}}
  context: fork
  input: { artifact_path: "{{artifact_path}}", rubric_refs: [...] }
  ```
- **統合**: git diff をユーザーに提示し 4条件を機械検証 → 承認 → commit（Gate 4）。

## Gotchas
- **Phase間でcontext共有しない**: forked evaluator に generator の思考過程を渡すと sycophancy が出る
- **Gate を skip しない**: 「明らかに通る」と思っても自然言語判断ではなく機械判定を走らせる
- **handoff file は session 単位**: 別 session で resume するときは PostCompact が拾う

## Additional Resources
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `references/gate-templates.md` — Gate 判定 snippet 集
- 設計書 09章 — 評価ピラミッド P0-P3
- 設計書 10章 §7 — Hook 競合解決

## Security & Permissions
本 orchestrator は subagent 起動と Python entrypoint 実行を伴う。設計書10章§7.4 二段防御:
1. **一段目（静的）**: `settings.json` の `permissions.deny` に破壊的 command と rubric ファイル Write/Edit を列挙
2. **二段目（動的）**: `PreToolUse` hook で context-dependent な危険検査
3. **TaskCreated hook**: file ownership 衝突を block
4. **SubagentStop hook**: evaluator JSON 契約違反を block
