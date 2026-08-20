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
---

# run-governance-hooks

## Purpose & Output Contract

`scripts/`のhook実体を棚卸しし、配線候補と安全な単体検証結果を返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- hookを配線済みと推測せず、manifest/settingsの参照を別途確認する。
- stdin payloadをfixtureで与え、実projectを変更しない検証を優先する。
- block/fail-softのexit契約を保持する。

## ゴールシーク実行

対象hookのpurpose/frontmatterを読み、event・matcher・payload・write scopeを確認してからfixtureで実行する。

## 検証

command path confinement、exit code、stdout JSON、未配線理由を報告する。
