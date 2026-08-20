---
name: run-governance-automation
description: governanceの登録・rubric合成・再評価・rollback automationを選択して安全に実行したいときに使う。
allowed-tools: Bash, Read, Glob
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
