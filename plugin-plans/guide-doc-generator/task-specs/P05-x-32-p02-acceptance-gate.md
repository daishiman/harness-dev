---
id: "P05-x-32-p02-acceptance-gate"
title: "P02 の acceptance 3 点を機械検査する gate を用意する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/evidence/P02.json"
acceptance_criterion: "brief 実在の id 集合一致・依存 DAG の非循環・実体解決 4 段の宣言の 3 点を検査する決定論スクリプトが存在し exit0 になること"
objective: "acceptance_criterion の 3 点 (brief 実在 / DAG 非循環 / 4 段解決の宣言) を機械検査する gate が存在せず、既存 2 本は別の面しか見ていない"
verify: "brief 実在の id 集合一致・依存 DAG の非循環・実体解決 4 段の宣言の 3 点を検査する決定論スクリプトが存在し exit0 になること"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-32-p02-acceptance-gate.md"]
consumes: []
---

# P02 の acceptance 3 点を機械検査する gate を用意する

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: acceptance_criterion の 3 点 (brief 実在 / DAG 非循環 / 4 段解決の宣言) を機械検査する gate が存在せず、既存 2 本は別の面しか見ていない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-x-01.json`

## 作業

`plugin-plans/guide-doc-generator/evidence/P02.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-32-p02-acceptance-gate.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

brief 実在の id 集合一致・依存 DAG の非循環・実体解決 4 段の宣言の 3 点を検査する決定論スクリプトが存在し exit0 になること
