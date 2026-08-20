---
name: run-governance-secrets
description: governance secret helperの利用可否を確認したいとき、key名とbackendを値を露出せず監査したいときに使う。
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
source: plugins/skill-governance-secrets
source-tier: internal
feedback_contract:
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
---

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
