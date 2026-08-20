---
name: run-governance-migration
description: governance artifactのmigration候補、dry-run差分、rollback条件を確認したいときに使う。
allowed-tools: Bash, Read, Glob
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
