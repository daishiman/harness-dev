---
id: "P02-c11-consumers-single"
title: "C11 の consumers 行へ data-hb-single を追加する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C11.json"
acceptance_criterion: "script-brief-C11.json:341 の consumers 行で C17 の読む属性に data-hb-single が含まれること"
objective: "C17:73 が単一選択チップの aria-pressed 判定で data-hb-single を実際に読んでいるが consumers 行に無い。同行は『本節を変えるときは 5 本を同時に更新する』と自認している"
verify: "script-brief-C11.json:341 の consumers 行で C17 の読む属性に data-hb-single が含まれること"
depends_on: ["P02-C17-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c11-consumers-single.md"]
consumes: []
---

# C11 の consumers 行へ data-hb-single を追加する

## 由来

build 実行中に `P02-C17-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C17:73 が単一選択チップの aria-pressed 判定で data-hb-single を実際に読んでいるが consumers 行に無い。同行は『本節を変えるときは 5 本を同時に更新する』と自認している

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C17-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c11-consumers-single.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C11.json:341 の consumers 行で C17 の読む属性に data-hb-single が含まれること
