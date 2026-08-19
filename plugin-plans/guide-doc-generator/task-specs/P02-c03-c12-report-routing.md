---
id: "P02-c03-c12-report-routing"
title: "C12 の json-report を C06 の委譲入力へ含めるかを裁定する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C03.json"
acceptance_criterion: "C12 の json-report を gate_reports に含めるか否かが 1 箇所で裁定され、C03 の deterministic_checks と C06 の input_contract.receives が同じ結論を持つこと"
objective: "C12 は C09 の 4 ゲートに含まれない構成データ側ゲートのため、R25/REQ-7 で error 化された文長判定の結果が C06 へ届かない経路になっている"
verify: "C12 の json-report を gate_reports に含めるか否かが 1 箇所で裁定され、C03 の deterministic_checks と C06 の input_contract.receives が同じ結論を持つこと"
depends_on: ["P02-C03-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c03-c12-report-routing.md"]
consumes: []
---

# C12 の json-report を C06 の委譲入力へ含めるかを裁定する

## 由来

build 実行中に `P02-C03-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C12 は C09 の 4 ゲートに含まれない構成データ側ゲートのため、R25/REQ-7 で error 化された文長判定の結果が C06 へ届かない経路になっている

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C03-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C03.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c03-c12-report-routing.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C12 の json-report を gate_reports に含めるか否かが 1 箇所で裁定され、C03 の deterministic_checks と C06 の input_contract.receives が同じ結論を持つこと
