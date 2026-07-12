---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit]
pair: {{evaluator}}
kind: {{kind}}
role_suffix: generator
owner: {{owner}}
since: {{date}}
rubric_refs:
  - ref-skill-design-rubric              # L0 (固定)
  # L1: ドメイン rubric は --rubric-refs / DOMAIN_RUBRIC_REFS で append (rubric-registry.json 経由)
  - {{rubric_ref_l2 | default("references/rubric.json")}}  # L2: 本 generator 固有
merge_strategy: {{merge_strategy | default("deep-merge")}}
conflict_policy: {{conflict_policy | default("most-specific-wins")}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal")}}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly")}}
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
- `templates/`
{{additional_resources}}
