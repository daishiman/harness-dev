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
runtime_root_policy: host-skill-path
---

# {{name}}

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

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
