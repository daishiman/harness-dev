---
id: "P02-c11-heading-field-marker"
title: "C11 が見出し要素へ data-hb-field=heading を付ける契約を brief へ入れる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C11.json"
acceptance_criterion: "script-brief-C11.json が見出しテキストのみを持つ要素へ data-hb-field=\"heading\" を付けると明記し、C20 の data-hb-field 値の列挙にも heading が含まれること"
objective: "ROUNDTRIP-CONTRACT.md:271 の residual_work (見出し要素へ data-hb-field=heading を付ける) が未着手で、自 plugin 生成 HTML でも round-trip 等価 (C02 OUT1) が成立しない"
verify: "script-brief-C11.json が見出しテキストのみを持つ要素へ data-hb-field=\"heading\" を付けると明記し、C20 の data-hb-field 値の列挙にも heading が含まれること"
depends_on: ["P02-C02-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c11-heading-field-marker.md"]
consumes: []
---

# C11 が見出し要素へ data-hb-field=heading を付ける契約を brief へ入れる

## 由来

build 実行中に `P02-C02-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: ROUNDTRIP-CONTRACT.md:271 の residual_work (見出し要素へ data-hb-field=heading を付ける) が未着手で、自 plugin 生成 HTML でも round-trip 等価 (C02 OUT1) が成立しない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C02-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c11-heading-field-marker.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C11.json が見出しテキストのみを持つ要素へ data-hb-field="heading" を付けると明記し、C20 の data-hb-field 値の列挙にも heading が含まれること
