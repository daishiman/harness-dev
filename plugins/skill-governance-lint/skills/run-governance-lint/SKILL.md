---
name: run-governance-lint
description: skill・agent・pluginのgovernance lintを選択したいとき、rubricを含む検査をfail-closedで実行したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-lint
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: artifact kindに適用可能なlintとvalidatorを実在entrypointから選び各helpとexit codeを独立に確認している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 必要lintの未実行を理由付きで残し非0findingを自動修正または成功へ畳まず表形式で報告している
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

# run-governance-lint

## Purpose & Output Contract

対象artifactに適用可能な`scripts/lint-*.py` / `validate-*.py`を選び、全exit codeとfindingを返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- lint名を実在一覧から選び、対象pathを明示する。
- 非0を自動修正や成功へ畳まない。
- 複数lintは独立結果として保持する。

## ゴールシーク実行

artifact kindから候補lintを列挙し、各`--help`で引数を確認して実行する。必要lintの未実行が0になるまで続ける。

## 検証

`lint | target | exit | finding`表と未実施理由を返す。
