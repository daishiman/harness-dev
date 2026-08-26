---
name: run-slide-report-status
description: 生成中のslide deckまたはreportの現在phaseを確認したいとき、中断後の次アクションをread-onlyで特定したいときに使う。
kind: run
prefix: run
version: 0.1.0
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: false
argument-hint: "[output-dir?]"
effect: conversation-output
owner: harness maintainers
since: 2026-08-20
last-audited: 2026-08-20
output_language: ja
runtime_root_policy: host-skill-path
combinators:
  - with-feedback-contract
responsibility_refs:
  - ../../vendor/scripts/workflow-manager.js
  - ../../scripts/validate-output-mode.py
schema_refs:
  - ../../schemas/structure.schema.json
  - ../../schemas/report-structure.schema.json
completeness_exempt:
  - "manifest: 単一の read-only 照会で phase を進めず、本文の定型 2 コマンド以外の workflow 遷移がないため workflow manifest は作らない。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 明示されたproject directoryへworkflow managerのcheck nextとoutput mode preflightをread-onlyで実行し全exit codeを保持している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: deck report両modeの現在phase 欠落artifact 次actionを推測せず報告しplugin runtime欠落を自動復元していない
      verify_by: evaluator
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実回答をmain contextで作成する。secret・欠測・矛盾のminimal guardだけを実行し、根拠refつきの現物をそのまま提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-slide-report-status

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

対象project directoryをplugin同梱workflow managerで検査し、現在phase、検証結果、次アクションを返す。

## Key Rules

- 対象path未指定時は推測せず確認する。
- plugin資産は`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`から解決する。
- 対象projectへ書き込まず、`--check --next`だけを実行する。
- validator非0を成功へ畳まない。

## ゴールシーク実行

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/vendor/scripts/workflow-manager.js" "<project-dir>" --check --next
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-output-mode.py" --preflight
```

stdout/stderrとexit codeから現在phase、欠落artifact、次アクションを要約する。

## 検証

- deck/report両modeを同じworkflow managerで判定する。
- plugin-local runtime欠落は復元せずremediationとして報告する。
