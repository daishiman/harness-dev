---
id: "P05-x-03-nav-item-threshold"
title: "nav ラベルの文字数上限を出荷 config へ載せ検査範囲を届かせる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/config/handout-visual-policy.json"
acceptance_criterion: "出荷 config に nav ラベルの文字数上限が実在し (plan 側 briefs/config/handout-visual-policy.json の nav_item と同値)、micro_copy.note の適用範囲または専用の検査点により C11 algorithm 14 が描く nav ラベルが検査対象に入ること"
objective: "実測: 出荷 config の micro_copy.roles は label/title/caption の 3 種のみで nav_item が存在せず、note の適用範囲も sections[].parts[].data と diagrams[].data に限定。nav ラベルは C11 が section 見出しから描く値のため二重に範囲外。利用者要求 R11 (上部ナビを見やすく) の決定論的担保がこの 1 点に懸かる"
verify: "出荷 config に nav ラベルの文字数上限が実在し (plan 側 briefs/config/handout-visual-policy.json の nav_item と同値)、micro_copy.note の適用範囲または専用の検査点により C11 algorithm 14 が描く nav ラベルが検査対象に入ること"
depends_on: ["P02-C18-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-03-nav-item-threshold.md"]
consumes: []
---

# nav ラベルの文字数上限を出荷 config へ載せ検査範囲を届かせる

## 由来

build 実行中に `P02-C18-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: 出荷 config の micro_copy.roles は label/title/caption の 3 種のみで nav_item が存在せず、note の適用範囲も sections[].parts[].data と diagrams[].data に限定。nav ラベルは C11 が section 見出しから描く値のため二重に範囲外。利用者要求 R11 (上部ナビを見やすく) の決定論的担保がこの 1 点に懸かる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C18-01.json`

## 作業

`plugins/guide-doc-generator/config/handout-visual-policy.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-03-nav-item-threshold.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

出荷 config に nav ラベルの文字数上限が実在し (plan 側 briefs/config/handout-visual-policy.json の nav_item と同値)、micro_copy.note の適用範囲または専用の検査点により C11 algorithm 14 が描く nav ラベルが検査対象に入ること
