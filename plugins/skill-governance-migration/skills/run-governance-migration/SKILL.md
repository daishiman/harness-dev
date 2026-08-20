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
---

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
