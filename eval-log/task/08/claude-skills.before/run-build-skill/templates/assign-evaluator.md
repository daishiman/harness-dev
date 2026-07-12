---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: {{generator}}
kind: {{kind}}
role_suffix: evaluator
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal")}}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly")}}
rubric_refs:
  - {{upstream-rubric}}
  - references/rubric.json
merge_strategy: deep-merge
conflict_policy: most-specific-wins
---

# {{name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
1. Goodhart対策: 被採点物を改変しない。
{{key_constraints}}

## 手順
### Step 1
rubric.json ロード → findings 収集 → score算出 → JSON出力。

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- `references/rubric.json`
- `scripts/render-findings-score.py`
{{additional_resources}}
