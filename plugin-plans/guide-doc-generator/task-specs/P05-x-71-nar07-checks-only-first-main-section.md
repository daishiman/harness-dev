---
id: "P05-x-71-nar07-checks-only-first-main-section"
title: "NAR-07 が最初の本編セクション 1 つしか見ていない件を塞ぐ"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/verify-handout-narrative.py"
acceptance_criterion: "C56 criterion 後半 機能説明が必ず実画面より後に置かれる が全本編セクションに対して検査されること。実画面を 1 枚置いて以降を概念説明で埋めた入力が exit 1 になる回帰テストが tests/verify-handout-narrative.py/test_nar07_demo_first.py に存在すること"
objective: "verify-handout-narrative.py:1012 の start = mains[0] により、NAR-07 は最初の本編セクションの先頭要素だけを見る。実画面を 1 枚置けば以降を概念説明で埋めても通る。orange が本 cycle で塞いだのは presentation_order 欠落の fail-open であり、criterion 後半の穴は別。dispatcher が該当行を直読みして確認。cyan が検出"
verify: "C56 criterion 後半 機能説明が必ず実画面より後に置かれる が全本編セクションに対して検査されること。実画面を 1 枚置いて以降を概念説明で埋めた入力が exit 1 になる回帰テストが tests/verify-handout-narrative.py/test_nar07_demo_first.py に存在すること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-71-nar07-checks-only-first-main-section.md"]
consumes: []
---

# NAR-07 が最初の本編セクション 1 つしか見ていない件を塞ぐ

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: verify-handout-narrative.py:1012 の start = mains[0] により、NAR-07 は最初の本編セクションの先頭要素だけを見る。実画面を 1 枚置けば以降を概念説明で埋めても通る。orange が本 cycle で塞いだのは presentation_order 欠落の fail-open であり、criterion 後半の穴は別。dispatcher が該当行を直読みして確認。cyan が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/verify-handout-narrative.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-71-nar07-checks-only-first-main-section.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

C56 criterion 後半 機能説明が必ず実画面より後に置かれる が全本編セクションに対して検査されること。実画面を 1 枚置いて以降を概念説明で埋めた入力が exit 1 になる回帰テストが tests/verify-handout-narrative.py/test_nar07_demo_first.py に存在すること
