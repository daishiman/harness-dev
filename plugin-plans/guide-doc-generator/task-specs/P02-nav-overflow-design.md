---
id: "P02-nav-overflow-design"
title: "ナビ項目の字数超過と項目過多に対する描画時の破綻回避を定める"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C11.json"
acceptance_criterion: "script-brief-C11.json のナビ描画契約が (1) ラベルが 14 字上限を超えた場合の扱い (2) 項目数が多い場合の折返しまたは横スクロール、の 2 点を決定論的に定め、いずれも外部依存なしに実現できる形で記述されていること"
objective: "上部ナビの視覚設計が字数上限のみで閉じていない。micro_copy.roles の role=label が nav_item に max_chars 14 を課しているが、超過時の扱い (折返し / 省略記号 / ツールチップ) と項目数が多いときの段組・横スクロールが script-brief-C11.json にも handout-visual-policy.json にも定義されていない (SubAgent が 折返し/省略/ellipsis/overflow/段組 を grep しナビ対象のヒット 0 件)。利用者の R11 指摘 (スクリーンショット付きの『上部を見やすくしてください』) は字数だけでは閉じない"
verify: "script-brief-C11.json のナビ描画契約が (1) ラベルが 14 字上限を超えた場合の扱い (2) 項目数が多い場合の折返しまたは横スクロール、の 2 点を決定論的に定め、いずれも外部依存なしに実現できる形で記述されていること"
depends_on: ["P02-C04-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-nav-overflow-design.md"]
consumes: []
---

# ナビ項目の字数超過と項目過多に対する描画時の破綻回避を定める

## 由来

build 実行中に `P02-C04-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 上部ナビの視覚設計が字数上限のみで閉じていない。micro_copy.roles の role=label が nav_item に max_chars 14 を課しているが、超過時の扱い (折返し / 省略記号 / ツールチップ) と項目数が多いときの段組・横スクロールが script-brief-C11.json にも handout-visual-policy.json にも定義されていない (SubAgent が 折返し/省略/ellipsis/overflow/段組 を grep しナビ対象のヒット 0 件)。利用者の R11 指摘 (スクリーンショット付きの『上部を見やすくしてください』) は字数だけでは閉じない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C04-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-nav-overflow-design.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C11.json のナビ描画契約が (1) ラベルが 14 字上限を超えた場合の扱い (2) 項目数が多い場合の折返しまたは横スクロール、の 2 点を決定論的に定め、いずれも外部依存なしに実現できる形で記述されていること
