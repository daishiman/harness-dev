---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit, Agent]
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

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール
{{goal}}

### 目的・背景
{{purpose_background}}

### 完了チェックリスト
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
- `templates/`
{{additional_resources}}
