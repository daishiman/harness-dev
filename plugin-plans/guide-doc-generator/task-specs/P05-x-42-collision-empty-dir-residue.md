---
id: "P05-x-42-collision-empty-dir-residue"
title: "衝突回避で描画未到達の空ディレクトリが残る問題を直す"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "描画未到達のディレクトリが残らない、または残骸が識別可能に印付けされる"
objective: "handout-output/2026-08-18-report-kpi-flow-and-processing-app-2 は .handout-route.json と空の assets/ だけを持ち handout.html が無い。その config_path は隣の app ディレクトリの config を指す。route-handout-output.py:329 resolve_collision が連番ディレクトリを先に作り、描画到達前に失敗しても後始末しないため残骸が蓄積する。利用者から見ると成果物が 5 件あるように見えて実体は 4 件"
verify: "描画未到達のディレクトリが残らない、または残骸が識別可能に印付けされる"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-42-collision-empty-dir-residue.md"]
consumes: []
---

# 衝突回避で描画未到達の空ディレクトリが残る問題を直す

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: handout-output/2026-08-18-report-kpi-flow-and-processing-app-2 は .handout-route.json と空の assets/ だけを持ち handout.html が無い。その config_path は隣の app ディレクトリの config を指す。route-handout-output.py:329 resolve_collision が連番ディレクトリを先に作り、描画到達前に失敗しても後始末しないため残骸が蓄積する。利用者から見ると成果物が 5 件あるように見えて実体は 4 件

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-42-collision-empty-dir-residue.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

描画未到達のディレクトリが残らない、または残骸が識別可能に印付けされる
