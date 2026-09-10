---
id: "P05-x-70-required-slot-described-but-unimplemented"
title: "required_slot の schema 記述と slug 直書き実装の不一致を解消する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/validate-handout-config.py"
acceptance_criterion: "slot 検査の適用対象が section_kind 属性から決まるか、あるいは schema 記述が実装どおりへ改まっているかのいずれかで、記述と実装が一致していること"
objective: "schemas/handout-config.schema.json:400 は required_slot を持つ section_kind では全 part に必須 と属性駆動を宣言するが、required_slot は repo 全体でこの記述文字列 1 件のみで属性としては出荷・plan いずれの handout-sections.json にも 0 件。実装は validate-handout-config.py:1160 の if kind == KIND_CAPABILITY_EXPLAINER で slug 直書き。C46 で属性駆動へ直したのと同じ欠陥が C51 側に残っている。dispatcher が grep と該当行の直読みで確認。cyan が検出"
verify: "slot 検査の適用対象が section_kind 属性から決まるか、あるいは schema 記述が実装どおりへ改まっているかのいずれかで、記述と実装が一致していること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-70-required-slot-described-but-unimplemented.md"]
consumes: []
---

# required_slot の schema 記述と slug 直書き実装の不一致を解消する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: schemas/handout-config.schema.json:400 は required_slot を持つ section_kind では全 part に必須 と属性駆動を宣言するが、required_slot は repo 全体でこの記述文字列 1 件のみで属性としては出荷・plan いずれの handout-sections.json にも 0 件。実装は validate-handout-config.py:1160 の if kind == KIND_CAPABILITY_EXPLAINER で slug 直書き。C46 で属性駆動へ直したのと同じ欠陥が C51 側に残っている。dispatcher が grep と該当行の直読みで確認。cyan が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/validate-handout-config.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-70-required-slot-described-but-unimplemented.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

slot 検査の適用対象が section_kind 属性から決まるか、あるいは schema 記述が実装どおりへ改まっているかのいずれかで、記述と実装が一致していること
