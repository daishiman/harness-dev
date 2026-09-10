---
id: "P05-x-69-c50-four-steps-vs-three-slots"
title: "C50 の 4 段と slot enum の 3 区画の不一致を裁定する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/goal-spec.json"
acceptance_criterion: "C50 の criterion が要求する段数と schemas/handout-config.schema.json の part.slot enum の区画数が一致していること。操作を 4 つ目の区画として足すか C50 を 3 段へ改めるかの裁定根拠が記録されていること"
objective: "C50 criterion は できること -> 分解 -> 使う機能の組み合わせ -> 操作 の 4 段を要求するが、schema の part.slot enum は outcome / breakdown / feature + null の 3 区画しかなく 4 段目に対応する区画が無い。dispatcher が schema を直読みして確認。C51 の 3 段とも食い違う。cyan が検出"
verify: "C50 の criterion が要求する段数と schemas/handout-config.schema.json の part.slot enum の区画数が一致していること。操作を 4 つ目の区画として足すか C50 を 3 段へ改めるかの裁定根拠が記録されていること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-69-c50-four-steps-vs-three-slots.md"]
consumes: []
---

# C50 の 4 段と slot enum の 3 区画の不一致を裁定する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C50 criterion は できること -> 分解 -> 使う機能の組み合わせ -> 操作 の 4 段を要求するが、schema の part.slot enum は outcome / breakdown / feature + null の 3 区画しかなく 4 段目に対応する区画が無い。dispatcher が schema を直読みして確認。C51 の 3 段とも食い違う。cyan が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugin-plans/guide-doc-generator/goal-spec.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-69-c50-four-steps-vs-three-slots.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C50 の criterion が要求する段数と schemas/handout-config.schema.json の part.slot enum の区画数が一致していること。操作を 4 つ目の区画として足すか C50 を 3 段へ改めるかの裁定根拠が記録されていること
