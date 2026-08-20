---
name: run-governance-secrets
description: governance secret helperの利用可否、key名、backendを値を露出せず確認したいときに使う。
allowed-tools: Bash, Read, Glob
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
