---
name: run-governance-config
description: governance config一式の用途と必須keyを確認したいとき、projectへの導入差分をread-onlyで把握したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-config
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: config registry policy exampleの参照を辿りrequired present unresolved ownerを実ファイルから分類している
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: secret値を表示または生成せずdangling参照 parse不能 未解決placeholderをread-only結果として報告している
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

# run-governance-config

## Purpose & Output Contract

`config/`のregistry/policy/exampleを棚卸しし、対象projectに必要な設定と未解決値を報告する。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`として扱う。
- `.example`を実credential入り設定として扱わない。
- secret値を表示・生成しない。
- read-only分析を既定とし、設定反映は別のowner workflowへ渡す。

## ゴールシーク実行

利用目的を確定し、対応するconfigと参照関係を読み、`required / present / unresolved / owner`表を返す。

## 検証

参照先のdangling、JSON parse不能、未解決placeholderを明示する。
