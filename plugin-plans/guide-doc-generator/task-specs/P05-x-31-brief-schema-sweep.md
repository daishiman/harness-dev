---
id: "P05-x-31-brief-schema-sweep"
title: "skill-brief 系 brief 全件へ schema 検証を一括適用する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/"
acceptance_criterion: "skill-brief-*.json の全件が Draft202012Validator で errors 0 になり、違反があった場合の修正箇所が一覧で記録されていること"
objective: "skill-brief.schema.json の boundary に maxLength:200 があり、既存 brief に超過があるか未確認 (C03 は 470 字違反を実際に踏んだ)"
verify: "skill-brief-*.json の全件が Draft202012Validator で errors 0 になり、違反があった場合の修正箇所が一覧で記録されていること"
depends_on: ["P02-C03-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-31-brief-schema-sweep.md"]
consumes: []
---

# skill-brief 系 brief 全件へ schema 検証を一括適用する

## 由来

build 実行中に `P02-C03-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: skill-brief.schema.json の boundary に maxLength:200 があり、既存 brief に超過があるか未確認 (C03 は 470 字違反を実際に踏んだ)

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C03-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-31-brief-schema-sweep.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

skill-brief-*.json の全件が Draft202012Validator で errors 0 になり、違反があった場合の修正箇所が一覧で記録されていること
