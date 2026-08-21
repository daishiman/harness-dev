---
name: run-governance-hooks
description: governance hookのevent・matcher・commandを監査したいとき、対象file ownershipと配線漏れを確認したいときに使う。
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
source: plugins/skill-governance-hooks
source-tier: internal
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: hook実体ごとにevent matcher command path stdin payloadとexit契約をfixtureで検証し配線済みと推測していない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: plugin root外commandを許さず実projectを変更しない検証結果と未配線理由を報告している
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

# run-governance-hooks

## Purpose & Output Contract

`scripts/`のhook実体を棚卸しし、hook実体ごとに **event / matcher / command path / 配線状態 (配線済みか未配線か + 参照元) / fixture実行のexit codeとstdout JSON** を列挙して返す。未配線のものは理由を添える。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- hookを配線済みと推測せず、manifest/settingsの参照を別途確認する。
- stdin payloadをfixtureで与え、**実projectを変更しない**。書込を持つhookは既定の書込先がproject-localのため、必ず退避先を明示してから起動する — `hook-handoff.py` と `hook-post-compact.py` は `CLAUDE_HANDOFF_DIR` (既定 `.claude/handoff`)、`hook-check-file-ownership.py` は `CLAUDE_TASK_OWNERSHIP_STATE` (既定 `.claude/logs/task-ownership.json`) を一時ディレクトリへ向ける。env上書きが使えない場合は隔離cwdで実行する。どちらも取れないhookは実行せず未検証理由として報告する。
- block/fail-softのexit契約を保持する。

## ゴールシーク実行

対象hookのpurpose/frontmatterを読み、event・matcher・payload・write scopeを確認する。write scopeがnone以外なら上記envで書込先を退避してからfixtureで実行する。

## 検証

IN1の機械根拠は「hook実体をfixture stdinで起動したときのexit code」であり、hook script自身が検証scriptを兼ねる (別途の検証scriptは持たない)。command path confinement、exit code、stdout JSON、退避先へ書かれた成果物、未配線理由を報告する。
