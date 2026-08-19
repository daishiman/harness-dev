---
id: "P02-c08-checklist-coverage"
title: "C08 の checklist_covered を C20/C02 の checklist と突合して補完する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/command-brief-C08.json"
acceptance_criterion: "C08 の checklist_covered が C20 と C02 の checklist 項目のうち C08 が実際に担う分を漏れなく列挙し、担わない項目は担当 component が明示されていること"
objective: "C08 の checklist_covered が ['C20'] の 1 件のみで、C20 の checklist_covered と C02 の checklist を突合しておらず被覆宣言が過少の可能性がある (C09 は 12 件を宣言)"
verify: "C08 の checklist_covered が C20 と C02 の checklist 項目のうち C08 が実際に担う分を漏れなく列挙し、担わない項目は担当 component が明示されていること"
depends_on: ["P02-C08-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c08-checklist-coverage.md"]
consumes: []
---

# C08 の checklist_covered を C20/C02 の checklist と突合して補完する

## 由来

build 実行中に `P02-C08-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C08 の checklist_covered が ['C20'] の 1 件のみで、C20 の checklist_covered と C02 の checklist を突合しておらず被覆宣言が過少の可能性がある (C09 は 12 件を宣言)

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C08-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/command-brief-C08.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c08-checklist-coverage.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C08 の checklist_covered が C20 と C02 の checklist 項目のうち C08 が実際に担う分を漏れなく列挙し、担わない項目は担当 component が明示されていること
