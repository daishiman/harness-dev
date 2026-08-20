---
name: run-governance-config
description: governance config一式の用途と必須keyを確認したいとき、projectへの導入差分をread-onlyで把握したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
allowed-tools: Read, Glob
effect: conversation-output
owner: team-platform
since: 2026-08-20
last-audited: 2026-08-20
source: plugins/skill-governance-config
source-tier: internal
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: config registry policy exampleの参照を辿りrequired present unresolved ownerを実ファイルから分類している
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: secret値を表示または生成せずdangling参照 parse不能 未解決placeholderをread-only結果として報告している
      verify_by: evaluator
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
