---
name: run-governance-hooks
description: governance hookのevent、matcher、command、対象file ownershipを監査したいときに使う。
allowed-tools: Bash, Read, Glob
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
