---
id: "P05-C06-rebuild"
title: "handout-readability-reviewer.md を訂正後の brief から再 build する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/agents/handout-readability-reviewer.md"
acceptance_criterion: "出荷物が plugins/guide-doc-generator/references/ を 1 件も参照せず (実在は skills/ref-handout-design-system/references/)、文長・文数の担当が C12 と書かれており C18 と書かれた箇所が 0 件であること"
objective: "出荷物 handout-readability-reviewer.md の :57/:125 が実在しない references/ を指し、:155 が文長系を C18 へ誤帰属している。brief 側は訂正済みだが出荷物が追従していない"
verify: "出荷物が plugins/guide-doc-generator/references/ を 1 件も参照せず (実在は skills/ref-handout-design-system/references/)、文長・文数の担当が C12 と書かれており C18 と書かれた箇所が 0 件であること"
depends_on: ["P02-C06-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-C06-rebuild.md"]
consumes: []
---

# handout-readability-reviewer.md を訂正後の brief から再 build する

## 由来

build 実行中に `P02-C06-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 出荷物 handout-readability-reviewer.md の :57/:125 が実在しない references/ を指し、:155 が文長系を C18 へ誤帰属している。brief 側は訂正済みだが出荷物が追従していない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C06-01.json`

## 作業

`plugins/guide-doc-generator/agents/handout-readability-reviewer.md` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-C06-rebuild.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

出荷物が plugins/guide-doc-generator/references/ を 1 件も参照せず (実在は skills/ref-handout-design-system/references/)、文長・文数の担当が C12 と書かれており C18 と書かれた箇所が 0 件であること
