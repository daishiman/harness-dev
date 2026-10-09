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

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
<!-- /runtime-root-contract:v1 -->

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 守ること
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
