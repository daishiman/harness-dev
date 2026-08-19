---
id: "P05-x-16-cr-owner-registry"
title: "CR-* prefix の owner 登録表を作る"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md"
acceptance_criterion: "CR-* prefix を持つ全 rule (CR-EXT / CR-EMOJI / CR-EXTRACT-ARGS) が 1 つの表に owner component 付きで列挙され、新規追加時に衝突を検出できること"
objective: "RESOLUTION-P03.md:212-213 の表は CR-EXT / CR-EMOJI の 2 件のみだが、C08 が owner の CR-EXTRACT-ARGS が別系統で存在する。3 つ目以降の衝突を検出する機構が無い"
verify: "CR-* prefix を持つ全 rule (CR-EXT / CR-EMOJI / CR-EXTRACT-ARGS) が 1 つの表に owner component 付きで列挙され、新規追加時に衝突を検出できること"
depends_on: ["P02-C16-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-16-cr-owner-registry.md"]
consumes: []
---

# CR-* prefix の owner 登録表を作る

## 由来

build 実行中に `P02-C16-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: RESOLUTION-P03.md:212-213 の表は CR-EXT / CR-EMOJI の 2 件のみだが、C08 が owner の CR-EXTRACT-ARGS が別系統で存在する。3 つ目以降の衝突を検出する機構が無い

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C16-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-16-cr-owner-registry.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

CR-* prefix を持つ全 rule (CR-EXT / CR-EMOJI / CR-EXTRACT-ARGS) が 1 つの表に owner component 付きで列挙され、新規追加時に衝突を検出できること
