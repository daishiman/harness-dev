---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Agent]
kind: {{kind}}
owner: {{owner}}
since: {{date}}
role_suffix: {{role_suffix}}
hierarchy_level: {{hierarchy_level}}        # L0=単独参照 / L1=連携 / L2=オーケストレーション
rubric_refs: {{rubric_refs | default([])}}  # 評価で参照する rubric Skill 名（複数可）。pair=evaluator がある場合は必須
feedback_contract:
  max_iterations: {{feedback_contract_max_iterations | default(3)}}
  criteria:
    - id: IN1
      loop_scope: inner
      text: {{feedback_contract_inner_criteria_text}}
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: {{feedback_contract_outer_criteria_text}}
      verify_by: elegant-review
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal")}}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly")}}
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈次第の危険検査を hook で追加（二段防御）。例: plugins/skill-governance-config/config/claude-settings-hooks.json.example 参照
---

# {{name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
{{key_constraints}}

## 評価・改善ループ契約
`feedback_contract.criteria` は本 Skill 固有の完了チェックリストから導出した評価基準である。inner は現在ゴールを満たす小さな検証、outer はユーザー目的と 4 条件を満たす全体検証を担う。content-review / evaluator / hook は同じ criteria id を参照し、`criteria_evaluated` が全 id を覆うまで PASS にしない。未達時は最大 `feedback_contract.max_iterations` 周まで改善→再評価し、超過時は `INCOMPLETE` として human_review に差し戻す。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。
> ループを多周回す／重い試行錯誤を伴う場合は、親セッションを汚さないよう SubAgent（`Agent`）または Agent Team に fork して実行し、親へは最終成果物と要約のみ返す（同 references「コンテキスト分離」）。

### ゴール (Goal)
{{goal}}

### 目的・背景 (Why)
{{purpose_background}}

### 完了チェックリスト (Checklist)
{{generated_checklist}}

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。

## 検証
{{generated_checks}}

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- `references/`
{{additional_resources}}

## セキュリティと権限
本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。両者は独立に動作するため、片方の漏れをもう片方で補える。例設定は `plugins/skill-governance-config/config/claude-settings-hooks.json.example` を参照。
