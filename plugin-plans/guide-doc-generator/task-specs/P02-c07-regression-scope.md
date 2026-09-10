---
id: "P02-c07-regression-scope"
title: "inventory C07 へ harness_coverage.regression_scope を追加する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/component-inventory.json"
acceptance_criterion: "component C07 の harness_coverage に regression_scope が存在し、他 command component と同一の粒度で記述されていること"
objective: "inventory C07 に harness_coverage.regression_scope が無く command 面の回帰対象が未宣言"
verify: "component C07 の harness_coverage に regression_scope が存在し、他 command component と同一の粒度で記述されていること"
depends_on: ["P02-C07-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c07-regression-scope.md"]
consumes: []
---

# inventory C07 へ harness_coverage.regression_scope を追加する

## 由来

build 実行中に `P02-C07-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: inventory C07 に harness_coverage.regression_scope が無く command 面の回帰対象が未宣言

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C07-01.json`

## 作業

`plugin-plans/guide-doc-generator/component-inventory.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c07-regression-scope.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

component C07 の harness_coverage に regression_scope が存在し、他 command component と同一の粒度で記述されていること
