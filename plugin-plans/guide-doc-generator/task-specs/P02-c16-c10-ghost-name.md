---
id: "P02-c16-c10-ghost-name"
title: "C16 が参照する C10 の名前を実在名へ訂正する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C16.json"
acceptance_criterion: "script-brief-C16.json に handout-emoji-and-external-ref-guard が 0 件、guard-handout-external-ref が 1 件以上あること"
objective: "実測: 誤名 1 件・正名 0 件。実在しない component 名を参照する ghost-name 型で、P02-C16-01 での見落とし"
verify: "script-brief-C16.json に handout-emoji-and-external-ref-guard が 0 件、guard-handout-external-ref が 1 件以上あること"
depends_on: ["P02-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c16-c10-ghost-name.md"]
consumes: []
---

# C16 が参照する C10 の名前を実在名へ訂正する

## 由来

build 実行中に `P02-C10-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: 誤名 1 件・正名 0 件。実在しない component 名を参照する ghost-name 型で、P02-C16-01 での見落とし

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C10-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C16.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c16-c10-ghost-name.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C16.json に handout-emoji-and-external-ref-guard が 0 件、guard-handout-external-ref が 1 件以上あること
