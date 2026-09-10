---
id: "P05-x-40-opening-goal-first-cards"
title: "冒頭を goal 先頭のカード群へ再構成する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "冒頭が goal → 全体像 → 各カードの順に並び、hero が個別カードとして描画され、冒頭ブロックの 1 文が閾値内に収まる"
objective: "既存生成物 4 件すべてで冒頭の DOM 順序と data-hb-field 順序が purpose→background→goal であり、goal が最後に置かれている。冒頭は span.hero-purpose 等の散文でカードではなく、冒頭ブロックは最大 738 字。さらに最長文 101 字と次点 88 字がどちらも冒頭 hero にあり、読み手が最初に見る 1 文が文書中で最も長いという最悪の分布。利用者要件はゴールが最初でカード化"
verify: "冒頭が goal → 全体像 → 各カードの順に並び、hero が個別カードとして描画され、冒頭ブロックの 1 文が閾値内に収まる"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-40-opening-goal-first-cards.md"]
consumes: []
---

# 冒頭を goal 先頭のカード群へ再構成する

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 既存生成物 4 件すべてで冒頭の DOM 順序と data-hb-field 順序が purpose→background→goal であり、goal が最後に置かれている。冒頭は span.hero-purpose 等の散文でカードではなく、冒頭ブロックは最大 738 字。さらに最長文 101 字と次点 88 字がどちらも冒頭 hero にあり、読み手が最初に見る 1 文が文書中で最も長いという最悪の分布。利用者要件はゴールが最初でカード化

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-40-opening-goal-first-cards.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

冒頭が goal → 全体像 → 各カードの順に並び、hero が個別カードとして描画され、冒頭ブロックの 1 文が閾値内に収まる
