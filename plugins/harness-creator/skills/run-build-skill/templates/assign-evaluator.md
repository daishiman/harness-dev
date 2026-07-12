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

## ゴールシーク実行（評価系: 採点網羅をチェックリストで担保）
> evaluator は一度の採点で完結する read-only 工程。ループは回さないが、採点の網羅性をチェックリストで保証する。詳細は run-build-skill `references/goal-seek-paradigm.md` § 評価系。

### ゴール (Goal)
被採点物を rubric に照らし、漏れなく findings + score を算出した状態。

### 完了チェックリスト (Checklist)
- [ ] rubric.json の全項目を評価した
- [ ] 各 finding に観測可能なエビデンス（パス・行・引用）を付与した
- [ ] score を算出し JSON 出力契約を満たした
- [ ] 被採点物を一切改変していない（Goodhart 対策）

### 手順（採点の素描。文脈に応じ AI が調整）
rubric.json ロード → findings 収集 → score算出 → JSON出力。

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- `references/rubric.json`
- `scripts/render-findings-score.py`
{{additional_resources}}
