---
id: "P05-x-02-geometry-acceptance"
title: "P05-x-02 の受入基準を属性様式から幾何規約へ言い換える"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/task-specs/P05-x-02.md"
acceptance_criterion: "task-specs/P05-x-02.md の acceptance_criterion (2) が icon-set.json の属性文字列 (viewBox/stroke/fill/stroke-linecap) の存在を要求せず、幾何規約 (path 座標が 0-24 座標系内・stroke_width 2.2-2.6・線表現) で判定されること。task-graph 上の P05-x-02 ノードの acceptance も同時に追従すること"
objective: "C15 の裁定で様式値の正本は C15 手順 9 のリテラル 1 箇所となり icon-set.json は属性を持たない。現行の受入基準は icon-set.json を grep すると必ず 0 件になり、正しく作っても受入が落ちる"
verify: "task-specs/P05-x-02.md の acceptance_criterion (2) が icon-set.json の属性文字列 (viewBox/stroke/fill/stroke-linecap) の存在を要求せず、幾何規約 (path 座標が 0-24 座標系内・stroke_width 2.2-2.6・線表現) で判定されること。task-graph 上の P05-x-02 ノードの acceptance も同時に追従すること"
depends_on: ["P02-C15-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-02-geometry-acceptance.md"]
consumes: []
---

# P05-x-02 の受入基準を属性様式から幾何規約へ言い換える

## 由来

build 実行中に `P02-C15-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C15 の裁定で様式値の正本は C15 手順 9 のリテラル 1 箇所となり icon-set.json は属性を持たない。現行の受入基準は icon-set.json を grep すると必ず 0 件になり、正しく作っても受入が落ちる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C15-01.json`

## 作業

`plugin-plans/guide-doc-generator/task-specs/P05-x-02.md` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-02-geometry-acceptance.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

task-specs/P05-x-02.md の acceptance_criterion (2) が icon-set.json の属性文字列 (viewBox/stroke/fill/stroke-linecap) の存在を要求せず、幾何規約 (path 座標が 0-24 座標系内・stroke_width 2.2-2.6・線表現) で判定されること。task-graph 上の P05-x-02 ノードの acceptance も同時に追従すること
