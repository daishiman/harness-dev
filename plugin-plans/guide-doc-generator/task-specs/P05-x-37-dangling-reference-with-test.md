---
id: "P05-x-37-dangling-reference-with-test"
title: "実在しない references/ 参照 3 箇所を出荷物とテストで同時に直す"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "3 箇所すべてが skills/ref-handout-design-system/references/ を指し、:155 の担当が C12 と書かれ、当該テストが緑で通る"
objective: "plugins/guide-doc-generator/references/ は実在せず (正は skills/ref-handout-design-system/references/)、参照は agents/handout-readability-reviewer.md:57,125 の 2 箇所に加え tests/handout-readability-reviewer/test_input_contract.py:73 の計 3 箇所。テストが誤ったパスを期待値として固定しているため出荷物だけ直すとテストが落ちる。同 md:155 の文長担当 C18 誤帰属 (正本 owner は C12) も同一ファイル内で同時に直す"
verify: "3 箇所すべてが skills/ref-handout-design-system/references/ を指し、:155 の担当が C12 と書かれ、当該テストが緑で通る"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-37-dangling-reference-with-test.md"]
consumes: []
---

# 実在しない references/ 参照 3 箇所を出荷物とテストで同時に直す

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: plugins/guide-doc-generator/references/ は実在せず (正は skills/ref-handout-design-system/references/)、参照は agents/handout-readability-reviewer.md:57,125 の 2 箇所に加え tests/handout-readability-reviewer/test_input_contract.py:73 の計 3 箇所。テストが誤ったパスを期待値として固定しているため出荷物だけ直すとテストが落ちる。同 md:155 の文長担当 C18 誤帰属 (正本 owner は C12) も同一ファイル内で同時に直す

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-37-dangling-reference-with-test.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

3 箇所すべてが skills/ref-handout-design-system/references/ を指し、:155 の担当が C12 と書かれ、当該テストが緑で通る
