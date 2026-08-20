---
name: run-governance-lint
description: skill、agent、plugin、rubricのgovernance lintを選択しfail-closedで実行したいときに使う。
allowed-tools: Bash, Read, Glob
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
