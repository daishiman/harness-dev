---
id: "P02-c01-verdict-vocab-dedup"
title: "C01 R4-verify の verdict 語彙を C09 の評価順へ一本化する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json"
acceptance_criterion: "C01 の R4-verify が verdict 語彙と評価順を自前定義せず command-brief-C09.json の評価順を正本として参照していること"
objective: "C01 R4-verify の verdict 語彙 (pass/fail/incomplete/partial) が C09 の固定評価順を散文で二重に持つ可能性がある"
verify: "C01 の R4-verify が verdict 語彙と評価順を自前定義せず command-brief-C09.json の評価順を正本として参照していること"
depends_on: ["P02-C09-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c01-verdict-vocab-dedup.md"]
consumes: []
---

# C01 R4-verify の verdict 語彙を C09 の評価順へ一本化する

## 由来

build 実行中に `P02-C09-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C01 R4-verify の verdict 語彙 (pass/fail/incomplete/partial) が C09 の固定評価順を散文で二重に持つ可能性がある

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C09-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c01-verdict-vocab-dedup.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C01 の R4-verify が verdict 語彙と評価順を自前定義せず command-brief-C09.json の評価順を正本として参照していること
