---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Bash(bash *), Task]
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
# TaskCompleted hook: evaluator JSON 契約検証のため scripts/hook-verify-evaluator-json.py を有効化。
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

## Steps

### Step 1: Phase 1 - 要求収集
```bash
# {{phase1_skill}} を起動。brief.json が `{{brief_path}}` に出力されるまで blocking。
```
**Gate 1**: brief.json が schema validation を通過すること。

### Step 2: Phase 2 - 生成
```bash
# {{phase2_generator}} を Task tool 経由で起動。
# 完了時に P0 lint 全件を実行:
python3 creator-kit/scripts/lint-skill-tree.py --skills-dir {{output_dir}}
python3 creator-kit/scripts/validate-frontmatter.py {{output_dir}}/SKILL.md
python3 creator-kit/scripts/lint-skill-description.py --skills-dir {{output_dir}}
```
**Gate 2**: 全 lint exit 0 + git diff --shortstat が >0 行。

### Step 3: Phase 3 - 評価（fork）
```yaml
# Task tool で fork 評価を起動
subagent_type: {{phase3_evaluator}}
context: fork
input: { artifact_path: "{{artifact_path}}", rubric_refs: [...] }
```
**Gate 3**: evaluator JSON が SubagentStop hook 検証を通過 + `passed: true`。

### Step 4: Phase 4 - 統合
- git diff 確認をユーザーに提示
- 4条件（矛盾なし / 漏れなし / 整合性 / 依存関係整合）を機械的に検証
**Gate 4**: ユーザー最終承認 → commit。

### Step 5: 改善ループ判定
- Gate 3 fail かつ反復回数 < 3 → Phase 2 へ戻す（findings を context に注入）
- 反復回数 == 3 → governance へエスカレーション

## Gotchas
- **Phase間でcontext共有しない**: forked evaluator に generator の思考過程を渡すと sycophancy が出る
- **Gate を skip しない**: 「明らかに通る」と思っても自然言語判断ではなく機械判定を走らせる
- **handoff file は session 単位**: 別 session で resume するときは PostCompact が拾う

## Additional Resources
- `references/handoff-schema.json` — Phase間 handoff 構造
- `references/gate-templates.md` — Gate 判定 snippet 集
- 設計書 09章 — 評価ピラミッド P0-P3
- 設計書 10章 §7 — Hook 競合解決

## Security & Permissions
本 orchestrator は subagent 起動と外部 command 実行を伴う。設計書10章§7.4 二段防御:
1. **一段目（静的）**: `settings.json` の `permissions.deny` に `Bash(rm -rf*)`, `Bash(git push --force*)`, rubric ファイル Write/Edit を列挙
2. **二段目（動的）**: `PreToolUse` hook で context-dependent な危険検査
3. **TaskCreated hook**: file ownership 衝突を block
4. **TaskCompleted hook**: evaluator JSON 契約違反を block
