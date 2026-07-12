---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *)]
kind: {{kind}}
owner: {{owner}}
since: {{date}}
role_suffix: {{role_suffix}}
hierarchy_level: {{hierarchy_level}}        # L0=単独参照 / L1=連携 / L2=オーケストレーション
rubric_refs: {{rubric_refs | default([])}}  # 評価で参照する rubric Skill 名（複数可）。pair=evaluator がある場合は必須
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal")}}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly")}}
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈次第の危険検査を hook で追加（二段防御）。例: creator-kit/config/claude-settings-hooks.json.example 参照
---

# {{name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
{{key_constraints}}

## 手順
{{generated_steps}}

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
本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。両者は独立に動作するため、片方の漏れをもう片方で補える。例設定は `creator-kit/config/claude-settings-hooks.json.example` を参照。
