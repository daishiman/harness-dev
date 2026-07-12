---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
disable-model-invocation: false
user-invocable: true
context: fork
agent: {{subagent}}
delegate_agent: {{delegate_agent}}
allowed-tools: [Read, Write]
kind: delegate
owner: {{owner}}
since: {{date}}
hierarchy_level: {{hierarchy_level | default("L2") }}  # delegate は通常 L2（外部実行委譲）
rubric_refs: {{rubric_refs | default([]) }}            # 委譲先の受け入れ判定 rubric
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
1. 入出力契約のみ定義、ロジックは subagent 側。
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
- TODO
{{additional_resources}}

## セキュリティと権限
本Skillは subagent へ委譲するが、委譲先の権限も親の `permissions` で制御される。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査を動的に行うこと。委譲先が信頼境界外なら deny を厳しく、hook で入出力を検証する。例設定は `creator-kit/config/claude-settings-hooks.json.example` を参照。
