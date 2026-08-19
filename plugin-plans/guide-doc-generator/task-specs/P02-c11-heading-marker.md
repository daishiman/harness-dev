---
id: "P02-c11-heading-marker"
title: "C11 の data-hb-field enum へ heading を追加し裁定表へ /assets/*/role を記録する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C11.json"
acceptance_criterion: "script-brief-C11.json の data-hb-field enum に heading が含まれ、見出しテキストのみを持つ要素へ付与する手順が algorithm に現れること。あわせて plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md へ /assets/*/role のエントリ (decision=marker / marker=data-hb-asset-role) が追加され、13 pointer の包含関係が brief 側と一致すること"
objective: "C11 の data-hb-field enum に heading が無い (dispatcher 実測)。C20 の enum は heading を受理準備済みで、ROUNDTRIP-CONTRACT.md も /sections/*/heading を marker_status=absent とし residual_work を『C11 が見出しテキストのみを持つ要素へ data-hb-field=heading を付ける』と C11 へ割り当てているが未了。render-handout.py:1511 が出す <h2 class=\"section-label\"> は属性を持たず、見出しテキストの復元路が塞がったまま。加えて ROUNDTRIP-CONTRACT.md の 13 pointer に /assets/*/role のエントリが無く (出現 0 件)、裁定の正本側に記録が無い"
verify: "script-brief-C11.json の data-hb-field enum に heading が含まれ、見出しテキストのみを持つ要素へ付与する手順が algorithm に現れること。あわせて plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md へ /assets/*/role のエントリ (decision=marker / marker=data-hb-asset-role) が追加され、13 pointer の包含関係が brief 側と一致すること"
depends_on: ["P02-C20-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c11-heading-marker.md"]
consumes: []
---

# C11 の data-hb-field enum へ heading を追加し裁定表へ /assets/*/role を記録する

## 由来

build 実行中に `P02-C20-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C11 の data-hb-field enum に heading が無い (dispatcher 実測)。C20 の enum は heading を受理準備済みで、ROUNDTRIP-CONTRACT.md も /sections/*/heading を marker_status=absent とし residual_work を『C11 が見出しテキストのみを持つ要素へ data-hb-field=heading を付ける』と C11 へ割り当てているが未了。render-handout.py:1511 が出す <h2 class="section-label"> は属性を持たず、見出しテキストの復元路が塞がったまま。加えて ROUNDTRIP-CONTRACT.md の 13 pointer に /assets/*/role のエントリが無く (出現 0 件)、裁定の正本側に記録が無い

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C20-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C11.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c11-heading-marker.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C11.json の data-hb-field enum に heading が含まれ、見出しテキストのみを持つ要素へ付与する手順が algorithm に現れること。あわせて plugins/guide-doc-generator/schemas/ROUNDTRIP-CONTRACT.md へ /assets/*/role のエントリ (decision=marker / marker=data-hb-asset-role) が追加され、13 pointer の包含関係が brief 側と一致すること
