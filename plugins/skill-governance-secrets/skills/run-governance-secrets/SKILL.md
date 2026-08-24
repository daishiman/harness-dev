---
name: run-governance-secrets
description: governance secret helperの利用可否を確認したいとき、key名とbackendを値を露出せず監査したいときに使う。
kind: run
prefix: run
goal_seek:
  engine: inline
  fork: inline
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-secrets
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 実在helperのhelpを確認してsecretの存在確認を値取得から分離しstdout stderr logへ値を出していない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: key backend present value_exposed falseだけを報告し登録 更新 削除はユーザー承認後に限定している
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

# run-governance-secrets

## Purpose & Output Contract

`scripts/secrets/`のhelperを使い、secretの存在・backend・remediationだけを返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- secret値をstdout/stderr、log、成果物へ出さない。
- key名とbackendを明示し、存在確認を値取得から分離する。
- 登録・更新・削除はユーザー承認後のみ行う。

## ゴールシーク実行

対象key/backend/helperを確定し、helpと存在確認を行う。不在なら値を尋ねず安全な登録手順を提示する。

## 検証

`key | backend | present | value_exposed=false`だけを報告する。
