---
name: run-governance-config
description: governance config一式の用途、必須key、projectへの導入差分をread-onlyで確認したいときに使う。
allowed-tools: Read, Glob
---

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
