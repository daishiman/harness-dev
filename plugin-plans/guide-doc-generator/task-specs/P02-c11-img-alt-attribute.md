---
id: "P02-c11-img-alt-attribute"
title: "C11 が alt 値を alt 属性として描くことを契約に書く"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C11.json"
acceptance_criterion: "script-brief-C11.json の画像描画 algorithm に、assets[].alt の値を <img> の alt 属性へ無変換で出すことが明記されていること。data-hb-asset-alt は逆抽出用の marker であり支援技術向けの機構ではない旨を併記し、alt が空文字になる経路が無いこと"
objective: "実測: script-brief-C11.json の 'alt=' は 0 件。C12 が構成データ段で alt を必須にし C21 も image-plan の必須フィールドとして exit2 で守っているのに、最終 DOM で alt 属性になる契約文が無く data-hb-asset-alt (data 属性) へ入る記述しかない。R25 の per-section IMG 必須化で露出面が節数に比例する"
verify: "script-brief-C11.json の画像描画 algorithm に、assets[].alt の値を <img> の alt 属性へ無変換で出すことが明記されていること。data-hb-asset-alt は逆抽出用の marker であり支援技術向けの機構ではない旨を併記し、alt が空文字になる経路が無いこと"
depends_on: ["P02-C17-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c11-img-alt-attribute.md"]
consumes: []
---

# C11 が alt 値を alt 属性として描くことを契約に書く

## 由来

build 実行中に `P02-C17-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: script-brief-C11.json の 'alt=' は 0 件。C12 が構成データ段で alt を必須にし C21 も image-plan の必須フィールドとして exit2 で守っているのに、最終 DOM で alt 属性になる契約文が無く data-hb-asset-alt (data 属性) へ入る記述しかない。R25 の per-section IMG 必須化で露出面が節数に比例する

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C17-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c11-img-alt-attribute.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C11.json の画像描画 algorithm に、assets[].alt の値を <img> の alt 属性へ無変換で出すことが明記されていること。data-hb-asset-alt は逆抽出用の marker であり支援技術向けの機構ではない旨を併記し、alt が空文字になる経路が無いこと
