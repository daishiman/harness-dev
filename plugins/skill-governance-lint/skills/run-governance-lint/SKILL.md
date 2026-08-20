---
name: run-governance-lint
description: skill・agent・pluginのgovernance lintを選択したいとき、rubricを含む検査をfail-closedで実行したいときに使う。
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
source: plugins/skill-governance-lint
source-tier: internal
feedback_contract:
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: artifact kindに適用可能なlintとvalidatorを実在entrypointから選び各helpとexit codeを独立に確認している
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 必要lintの未実行を理由付きで残し非0findingを自動修正または成功へ畳まず表形式で報告している
      verify_by: evaluator
---

# run-governance-lint

## Purpose & Output Contract

対象artifactに適用可能な`scripts/lint-*.py` / `validate-*.py`を選び、全exit codeとfindingを返す。

## Key Rules

- plugin rootは`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`で解決する。
- lint名を実在一覧から選び、対象pathを明示する。
- 非0を自動修正や成功へ畳まない。
- 複数lintは独立結果として保持する。

## ゴールシーク実行

artifact kindから候補lintを列挙し、各`--help`で引数を確認して実行する。必要lintの未実行が0になるまで続ける。

## 検証

`lint | target | exit | finding`表と未実施理由を返す。
