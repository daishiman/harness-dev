---
id: "P05-x-63-c58-owner-declaration-missing"
title: "C58 の checklist_covered 宣言を C12 へ追加する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C12.json"
acceptance_criterion: "C46-C59 の 14 件すべてが いずれかの brief の checklist_covered に現れる。宣言 0 件の checklist id が存在しないことを機械検査するゲートを持つ"
objective: "C58 (受講者の具体業務への紐づけ) だけが どの brief の checklist_covered にも入っていない。実体は揃っており validate-handout-config.py:168 TIE_TASK_PREFIX と :1233 の target_tasks 走査が検査している。C12 の acceptance_checks は C58 を名指ししているため宣言だけが落ちた形。宣言の穴は『検査していない』ではなく『誰が持つか不明』を作り、owner 不在のまま仕様変更が来ると誰も追随しない"
verify: "C46-C59 の 14 件すべてが いずれかの brief の checklist_covered に現れる。宣言 0 件の checklist id が存在しないことを機械検査するゲートを持つ"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-63-c58-owner-declaration-missing.md"]
consumes: []
---

# C58 の checklist_covered 宣言を C12 へ追加する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C58 (受講者の具体業務への紐づけ) だけが どの brief の checklist_covered にも入っていない。実体は揃っており validate-handout-config.py:168 TIE_TASK_PREFIX と :1233 の target_tasks 走査が検査している。C12 の acceptance_checks は C58 を名指ししているため宣言だけが落ちた形。宣言の穴は『検査していない』ではなく『誰が持つか不明』を作り、owner 不在のまま仕様変更が来ると誰も追随しない

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/script-brief-C12.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C12.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-63-c58-owner-declaration-missing.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C46-C59 の 14 件すべてが いずれかの brief の checklist_covered に現れる。宣言 0 件の checklist id が存在しないことを機械検査するゲートを持つ
