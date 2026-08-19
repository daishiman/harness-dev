---
id: "P05-x-73-presentation-order-derivation-enum-index-coupling"
title: "C49 の presentation_order 導出が enum の並び順に依存している件を外す"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/scripts/validate-handout-config.py"
acceptance_criterion: "導出が値の名前による写像で表現され、prior_knowledge_level か presentation_order の enum を並べ替えても写像が変わらないこと。並べ替えを入れた回帰テストが落ちること"
objective: "validate-handout-config.py:1729-1731 の index = 1 if prior == ctx.prior_levels[-1] else 0 / ctx.presentation_orders[index] は両 enum の並び順に依存する。正本 presentation_order_derivation.rule は値の名前による写像表を持つため、どちらかの enum を並べ替えると写像が黙って反転し検査で落ちない。cyan が検出"
verify: "導出が値の名前による写像で表現され、prior_knowledge_level か presentation_order の enum を並べ替えても写像が変わらないこと。並べ替えを入れた回帰テストが落ちること"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-73-presentation-order-derivation-enum-index-coupling.md"]
consumes: []
---

# C49 の presentation_order 導出が enum の並び順に依存している件を外す

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: validate-handout-config.py:1729-1731 の index = 1 if prior == ctx.prior_levels[-1] else 0 / ctx.presentation_orders[index] は両 enum の並び順に依存する。正本 presentation_order_derivation.rule は値の名前による写像表を持つため、どちらかの enum を並べ替えると写像が黙って反転し検査で落ちない。cyan が検出

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P03-x-04.json`

## 作業

`plugins/guide-doc-generator/scripts/validate-handout-config.py` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-73-presentation-order-derivation-enum-index-coupling.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

導出が値の名前による写像で表現され、prior_knowledge_level か presentation_order の enum を並べ替えても写像が変わらないこと。並べ替えを入れた回帰テストが落ちること
