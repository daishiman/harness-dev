---
id: "P02-c02-report-shape-binding"
title: "C02 の output_contract を C20 の report_shape へ束縛する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json"
acceptance_criterion: "C02 の output_contract が逆抽出レポートの構造を C20#report_shape の参照として持ち、フィールドを自前で再定義していないこと"
objective: "C02 の output_contract が 1 文のみで、C20 の --report が出す JSON 形状 (report_shape) との対応が書かれていない"
verify: "C02 の output_contract が逆抽出レポートの構造を C20#report_shape の参照として持ち、フィールドを自前で再定義していないこと"
depends_on: ["P02-C08-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c02-report-shape-binding.md"]
consumes: []
---

# C02 の output_contract を C20 の report_shape へ束縛する

## 由来

build 実行中に `P02-C08-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C02 の output_contract が 1 文のみで、C20 の --report が出す JSON 形状 (report_shape) との対応が書かれていない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C08-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c02-report-shape-binding.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C02 の output_contract が逆抽出レポートの構造を C20#report_shape の参照として持ち、フィールドを自前で再定義していないこと
