---
name: run-governance-automation
description: governanceの登録・rubric合成を実行したいとき、再評価・rollback automationを安全に選択したいときに使う。
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
source: plugins/skill-governance-automation
source-tier: internal
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 選択したautomation entrypointのhelpとread-only preflightを実行し非0またはreceipt欠落を成功へ畳んでいない
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: apply rollback 通知の外部作用はユーザー承認後だけ実行されcommand exit changed pathsと残リスクが報告されている
      verify_by: evaluator
---

# run-governance-automation

## Purpose & Output Contract

`scripts/`のautomation entrypointを利用目的に対応付け、help/preflight後に実行結果を返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- 最初に対象scriptの`--help`を実行する。
- apply/rollback/通知は明示承認なしに実行しない。
- exit非0やreceipt欠落を成功へ畳まない。

## ゴールシーク実行

目的に合う実在scriptを選び、入力・write scope・rollbackを確認する。read-only checkがあれば先に実行し、許可された操作だけを続行する。

## 検証

実行command、exit code、changed paths、残リスクを報告する。
