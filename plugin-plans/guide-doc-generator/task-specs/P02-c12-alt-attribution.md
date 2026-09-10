---
id: "P02-c12-alt-attribution"
title: "C12 の alt 必須理由の帰属先を C17 へ訂正する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C12.json"
acceptance_criterion: "script-brief-C12.json:482 の『a11y ゲート (C22)』が C17 へ訂正され、C22 は筋道ゲートである分界が保たれること"
objective: "a11y ゲートは C17、C22 は筋道ゲート。誤帰属のまま P06 のテスト設計へ入ると alt の回帰を C22 側へ書く誤りを誘発する"
verify: "script-brief-C12.json:482 の『a11y ゲート (C22)』が C17 へ訂正され、C22 は筋道ゲートである分界が保たれること"
depends_on: ["P02-C17-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c12-alt-attribution.md"]
consumes: []
---

# C12 の alt 必須理由の帰属先を C17 へ訂正する

## 由来

build 実行中に `P02-C17-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: a11y ゲートは C17、C22 は筋道ゲート。誤帰属のまま P06 のテスト設計へ入ると alt の回帰を C22 側へ書く誤りを誘発する

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C17-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C12.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c12-alt-attribution.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C12.json:482 の『a11y ゲート (C22)』が C17 へ訂正され、C22 は筋道ゲートである分界が保たれること
