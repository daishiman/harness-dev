---
name: run-governance-migration
description: governance artifactのmigration候補とdry-run差分を確認したいとき、rollback条件を保った移行を実行したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Glob
effect: local-artifact
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-migration
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: source target versionに対応する実在migrationを順序どおり選びhelp dry-run checkとbefore after digestを検証している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: backupとrollbackが確定しユーザー承認された場合だけapplyし部分適用を成功へ畳まずchanged pathsと残件を報告している
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

Purpose & Output Contractの最小の実成果物をmain contextで作成する。parse/open・secret・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはそのままhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。

# run-governance-migration

## Purpose & Output Contract

`scripts/migrate/`の実在migrationから対象versionに合うものを選び、dry-runと検証結果を返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- source/target versionとbackup/rollbackを確定するまでapplyしない。
- migrationの順序を飛ばさない。
- 非0や部分適用を成功へ畳まない。

## ゴールシーク実行

現在version、目標version、該当migrationを確定し、help/dry-run/checkの順で検証する。applyはユーザー承認後のみ行う。

## 検証

before/after digest、changed paths、rollback command、残件を返す。
