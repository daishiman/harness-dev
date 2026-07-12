---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに読む。
disable-model-invocation: true
user-invocable: false
kind: {{kind}}
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability 必須フィールド (ref-* は必須)
source: {{source_url_or_path}}
source-tier: {{source_tier}}            # article-text|image-derived|code-unavailable|code-verified|internal|external-spec
last-audited: {{last_audited_date}}     # YYYY-MM-DD
audit-trigger: {{audit_trigger}}         # rubric-bump|source-update|quarterly
---

# {{name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
{{key_constraints}}

## 手順
参照用。手順なし。

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- `references/`
{{additional_resources}}
