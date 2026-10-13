---
name: assign-system-dev-plan-evaluator
description: exact-13 staging planを独立評価したいとき、4条件とdigestに束縛したplan-findings.jsonを生成したいときに使う。
kind: assign
effect: local-artifact
prefix: assign
hierarchy: L1
version: 0.1.0
owner: team-platform
source: plugin-plans/system-dev-planner/component-inventory.json#C02
user-invocable: false
disable-model-invocation: true
context: fork
allowed-tools: [Read, Write, Bash(python3 *), Task]
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

## Purpose & Output Contract

`run-system-dev-plan` が staging へ書き出した exact-13 package を、生成側と共有しない fork context で読み取り専用に1回評価する。

- **入力**: caller repository 内の staging への repo 相対 path、C09 が解決した repo context、`validate-system-plan.py` の stdout/exit code。
- **出力**: `plan-findings.json` 1件を staging 外の repo-local state へ書く。`evaluator.context=fork`、validator の `validated_digest` を固定した `evaluated_digest`、C1 矛盾なし / C2 漏れなし / C3 整合性あり / C4 依存関係整合 の各 PASS|FAIL、総合 verdict、findings を持ち、`schemas/plan-findings.schema.json` に従う。
- **禁則**: 評価対象の staging package を修正しない。生成時の推論・期待 verdict を evaluator へ渡さない。1条件でも FAIL、validator 非0、digest 不在、high finding のどれかがあれば総合 verdict を PASS にしない。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Steps

1. C09 repo context を解決し、staging が caller repository 内であることを確認する。
2. `system-dev-plan-evaluator` を fork context で起動する。生成時の推論・期待 verdict は渡さない。
3. `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-system-plan.py" --repo-root <root> --staging <relative>` の stdout/exit code を機械根拠として渡す。
4. C1 矛盾なし / C2 漏れなし / C3 整合性あり / C4 依存関係整合をそれぞれ PASS|FAIL で評価する。C14 `system-build-handoff.json` の source exact-set、manifest digest包含、promotion/registration receipt owner 境界も必須根拠に含める。
5. `evaluated_digest` に validator の `validated_digest` をそのまま固定し、`evaluator.context=fork` の `plan-findings.json` を staging 外の repo-local state へ出力する。
6. 1条件でも FAIL、validator 非0、digest 不在、high finding があれば総合 verdict を FAIL にする。対象成果物は修正しない。

1回の evaluator 起動は read-only の1評価で終える。修正後の package を再評価する外側の goal-seek は、呼び出し側 C01 `run-system-dev-plan` の `goal_seek.max_loops=5` (`component-inventory.json` の C01 entry) に従い、5周で未達なら自動継続せず findings と staging path を返す。

出力 schema は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/schemas/plan-findings.schema.json`、評価対象契約は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/feature-execution-package-contract.md` を正本とする。これらは plugin の道具・契約であり、評価対象と出力状態は caller repository 内に限定する。

## Gotchas

- **validator の exit0 だけで PASS にしない**: 決定論 gate は構造しか見ない。空 section・placeholder・title と1文だけの擬似 task は、gate を通っても C2 漏れとして指摘する。
- **digest を自分で計算し直さない**: `evaluated_digest` は validator の `validated_digest` をそのまま写す。評価側で canonical digest を再導出すると、同じ規則を二か所で持つことになる。別 digest に対する verdict は破棄する。
- **周回はこの skill の中で回さない**: 未達でも FAIL の findings を返して終える。修正と再評価の周回は呼び出し側 `run-system-dev-plan` の `goal_seek.max_loops=5` が数える。
- **findings を staging の中へ書かない**: Write の対象は `plan-findings.json` だけで、置き場所は staging 外の repo-local state。評価対象と評価結果を同じ場所に混ぜない。
- **`${PLUGIN_ROOT}` を評価対象の置き場にしない**: plugin root は script と schema の位置決めにだけ使う。staging と出力は caller repository の中に限る。
