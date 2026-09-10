---
id: "P02-demo-first-no-fallback"
title: "demo_first の先頭 main セクションで illustration fallback を禁止する配線を C01/C05 へ入れる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json"
acceptance_criterion: "skill-brief-C01.json の R3-render に、presentation_order=demo_first のとき最初の main セクションの assets[].role を illustration へ書き換えない例外が明記され、素材が無い場合の代替 (live_demo=true の B17 を先頭に置く) と、それも不可能な場合の失敗の出し方が定まっていること"
objective: "R25/REQ-3 で全 main セクションに IMG 必須になった結果、demo_first の資料で最初の main セクションの IMG が素材不足で illustration へ落ちると C22 の NAR-07 (最初の提示物は実画面) が必ず FAIL する。evidence/P07.json:68 と evidence/P13.json:166 に NAR-07 初回 FAIL の実績あり。C01 の R3-render fallback と C05 の設計手順のどちらかに『demo_first のとき最初の main セクションは illustration への降格を許さず、screenshot 素材か live_demo の B17 を確保する』を配線する必要がある"
verify: "skill-brief-C01.json の R3-render に、presentation_order=demo_first のとき最初の main セクションの assets[].role を illustration へ書き換えない例外が明記され、素材が無い場合の代替 (live_demo=true の B17 を先頭に置く) と、それも不可能な場合の失敗の出し方が定まっていること"
depends_on: ["P02-C22-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-demo-first-no-fallback.md"]
consumes: []
---

# demo_first の先頭 main セクションで illustration fallback を禁止する配線を C01/C05 へ入れる

## 由来

build 実行中に `P02-C22-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: R25/REQ-3 で全 main セクションに IMG 必須になった結果、demo_first の資料で最初の main セクションの IMG が素材不足で illustration へ落ちると C22 の NAR-07 (最初の提示物は実画面) が必ず FAIL する。evidence/P07.json:68 と evidence/P13.json:166 に NAR-07 初回 FAIL の実績あり。C01 の R3-render fallback と C05 の設計手順のどちらかに『demo_first のとき最初の main セクションは illustration への降格を許さず、screenshot 素材か live_demo の B17 を確保する』を配線する必要がある

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C22-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C01.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-demo-first-no-fallback.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

skill-brief-C01.json の R3-render に、presentation_order=demo_first のとき最初の main セクションの assets[].role を illustration へ書き換えない例外が明記され、素材が無い場合の代替 (live_demo=true の B17 を先頭に置く) と、それも不可能な場合の失敗の出し方が定まっていること
