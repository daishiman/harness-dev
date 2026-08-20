---
name: assign-system-dev-plan-evaluator
description: exact-13 staging planを独立評価したいとき、4条件とdigestに束縛したplan-findings.jsonを生成したいときに使う。
kind: assign
prefix: assign
hierarchy: L1
version: 0.1.0
owner: team-platform
source: plugin-plans/system-dev-planner/component-inventory.json#C02
user-invocable: false
disable-model-invocation: true
context: fork
allowed-tools: [Read, Write, Bash, Task]
manifest: workflow-manifest.json
role_suffix: evaluator
responsibility_refs:
  - prompts/R4-evaluate.md
  - ../../agents/system-dev-plan-evaluator.md
rubric_refs:
  - ../../EVALS.json
schema_refs:
  - ../../schemas/plan-findings.schema.json
  - ../../schemas/system-build-handoff.schema.json
reference_refs:
  - ../../references/feature-execution-package-contract.md
script_refs:
  - ../../scripts/resolve-project-context.py
  - ../../scripts/validate-system-plan.py
runtime_root_policy: host-skill-path
---

# Independent system plan evaluation

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

1. C09 repo context を解決し、staging が caller repository 内であることを確認する。
2. `system-dev-plan-evaluator` を fork context で起動する。生成時の推論・期待 verdict は渡さない。
3. `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-system-plan.py" --repo-root <root> --staging <relative>` の stdout/exit code を機械根拠として渡す。
4. C1 矛盾なし / C2 漏れなし / C3 整合性あり / C4 依存関係整合をそれぞれ PASS|FAIL で評価する。C14 `system-build-handoff.json` の source exact-set、manifest digest包含、promotion/registration receipt owner 境界も必須根拠に含める。
5. `evaluated_digest` に validator の `validated_digest` をそのまま固定し、`evaluator.context=fork` の `plan-findings.json` を staging 外の repo-local state へ出力する。
6. 1条件でも FAIL、validator 非0、digest 不在、high finding があれば総合 verdict を FAIL にする。対象成果物は修正しない。

1回の evaluator 起動は read-only の1評価で終える。修正後の package を再評価する外側の goal-seek は `component-inventory.json` の `goal_seek.max_loops=5` に従い、5周で未達なら自動継続せず findings と staging path を返す。

出力 schema は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/schemas/plan-findings.schema.json`、評価対象契約は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/feature-execution-package-contract.md` を正本とする。これらは plugin の道具・契約であり、評価対象と出力状態は caller repository 内に限定する。
