---
id: "P02-c12-copy-long-impl"
title: "W-COPY-LONG の判定を C12 へ実装記述する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C12.json"
acceptance_criterion: "script-brief-C12.json に W-COPY-LONG の detection が実在し、閾値を config/handout-visual-policy.json#micro_copy から解決し、対象フィールドの決定規則 (roles の fields 対応・exempt_parts / exempt_fields の除外) が書かれていること"
objective: "出荷 config の _meta.canon_authority は W-COPY-LONG の閾値解決を C12 と宣言しているが、script-brief-C12.json の出現は 0 件。消費側 (C01/C05) だけがコードを参照する W-OPENS-PROSE と同型の欠陥、3 例目"
verify: "script-brief-C12.json に W-COPY-LONG の detection が実在し、閾値を config/handout-visual-policy.json#micro_copy から解決し、対象フィールドの決定規則 (roles の fields 対応・exempt_parts / exempt_fields の除外) が書かれていること"
depends_on: ["P02-C18-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c12-copy-long-impl.md"]
consumes: []
---

# W-COPY-LONG の判定を C12 へ実装記述する

## 由来

build 実行中に `P02-C18-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 出荷 config の _meta.canon_authority は W-COPY-LONG の閾値解決を C12 と宣言しているが、script-brief-C12.json の出現は 0 件。消費側 (C01/C05) だけがコードを参照する W-OPENS-PROSE と同型の欠陥、3 例目

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C18-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C12.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c12-copy-long-impl.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C12.json に W-COPY-LONG の detection が実在し、閾値を config/handout-visual-policy.json#micro_copy から解決し、対象フィールドの決定規則 (roles の fields 対応・exempt_parts / exempt_fields の除外) が書かれていること
