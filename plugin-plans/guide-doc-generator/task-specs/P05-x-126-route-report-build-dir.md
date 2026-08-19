---
id: "P05-x-126-route-report-build-dir"
title: "route-build-report の書込先を cycle build_dir へ統一し TG-C05/TG-C08 から可視化する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/harness-creator/scripts/"
acceptance_criterion: "route executor 群の書込先と TG-C05/TG-C08 の読込先が同一 build_dir を指すことを、route-build-report を 1 件生成したうえで TG-C05 の route_report_count が 0 でなく実数を返すことで実証する。既存 report の inputs_consumed 相互参照が dangling にならないことも同時に確認する。"
objective: "TG-C05 (summarize-task-progress.py) を cycle build_dir に対して実行すると route_report_count=2 (route-build-contract.json / route-build-plan.json のみ) を返す。本 cycle で実際に生成された route-build-report 72 件は eval-log/guide-doc-generator/build/ 直下に flat 配置され、cycle dir r25-improvement-2026-08-18/ には 1 件も無い。よって TG-C05 の進捗サマリと TG-C08 の完了ゲートは route 証跡をゼロ件として扱い、route の成否 (success 71 / failure 1) が集計から丸ごと落ちる。しかも route 証跡が 0 件という状態自体はエラーにならないため、測っていないことに気づけない。単純な移動では解決しない: 各 report の inputs_consumed が eval-log/guide-doc-generator/build/route-C16.json 形式の flat パスで相互参照しており、移動すると依存宣言が全て dangling になる。書込側 (resolve_build_dir を使う route executor 群) が --cycle-id を受け取っていないか無視しているのが根因と推定され、書込側 flat と読込側 cycle-dir のどちらを正本にするかの裁定を要する。本 cycle が繰り返し検出してきた検査が空振りする族の、集計層での実例。"
verify: "route executor 群の書込先と TG-C05/TG-C08 の読込先が同一 build_dir を指すことを、route-build-report を 1 件生成したうえで TG-C05 の route_report_count が 0 でなく実数を返すことで実証する。既存 report の inputs_consumed 相互参照が dangling にならないことも同時に確認する。"
depends_on: ["P05-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-126-route-report-build-dir.md"]
consumes: []
---

# route-build-report の書込先を cycle build_dir へ統一し TG-C05/TG-C08 から可視化する

## 由来

build 実行中に `P05-C10-01` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: TG-C05 (summarize-task-progress.py) を cycle build_dir に対して実行すると route_report_count=2 (route-build-contract.json / route-build-plan.json のみ) を返す。本 cycle で実際に生成された route-build-report 72 件は eval-log/guide-doc-generator/build/ 直下に flat 配置され、cycle dir r25-improvement-2026-08-18/ には 1 件も無い。よって TG-C05 の進捗サマリと TG-C08 の完了ゲートは route 証跡をゼロ件として扱い、route の成否 (success 71 / failure 1) が集計から丸ごと落ちる。しかも route 証跡が 0 件という状態自体はエラーにならないため、測っていないことに気づけない。単純な移動では解決しない: 各 report の inputs_consumed が eval-log/guide-doc-generator/build/route-C16.json 形式の flat パスで相互参照しており、移動すると依存宣言が全て dangling になる。書込側 (resolve_build_dir を使う route executor 群) が --cycle-id を受け取っていないか無視しているのが根因と推定され、書込側 flat と読込側 cycle-dir のどちらを正本にするかの裁定を要する。本 cycle が繰り返し検出してきた検査が空振りする族の、集計層での実例。

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/build-summary.json`

## 作業

`plugins/harness-creator/scripts/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-126-route-report-build-dir.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

route executor 群の書込先と TG-C05/TG-C08 の読込先が同一 build_dir を指すことを、route-build-report を 1 件生成したうえで TG-C05 の route_report_count が 0 でなく実数を返すことで実証する。既存 report の inputs_consumed 相互参照が dangling にならないことも同時に確認する。
