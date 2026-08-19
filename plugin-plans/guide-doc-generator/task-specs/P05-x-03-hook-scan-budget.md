---
id: "P05-x-03-hook-scan-budget"
title: "hook 走査予算の受け皿キーを config へ新設する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/config/handout-output.json"
acceptance_criterion: "config/handout-output.json#size_limits.hook_scan_budget に max_bytes と max_seconds が実在し、R25 の per-section IMG 必須化後の規模 (上限素材 2 点で 8 MiB 超・1 MiB 挿絵 6 節で約 8 MiB) を踏まえた値であること。asset_max_bytes とは別キーとして分離されていること"
objective: "実測: size_limits のキーは note / asset_max_bytes / asset_max_bytes_semantics / asset_max_bytes_source の 4 つのみで受け皿が無い。予算はソース焼き込みのままで、R25 後は打ち切りが常態化し hook が実質無音になる"
verify: "config/handout-output.json#size_limits.hook_scan_budget に max_bytes と max_seconds が実在し、R25 の per-section IMG 必須化後の規模 (上限素材 2 点で 8 MiB 超・1 MiB 挿絵 6 節で約 8 MiB) を踏まえた値であること。asset_max_bytes とは別キーとして分離されていること"
depends_on: ["P02-C10-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-03-hook-scan-budget.md"]
consumes: []
---

# hook 走査予算の受け皿キーを config へ新設する

## 由来

build 実行中に `P02-C10-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: size_limits のキーは note / asset_max_bytes / asset_max_bytes_semantics / asset_max_bytes_source の 4 つのみで受け皿が無い。予算はソース焼き込みのままで、R25 後は打ち切りが常態化し hook が実質無音になる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C10-01.json`

## 作業

`plugins/guide-doc-generator/config/handout-output.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-03-hook-scan-budget.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

config/handout-output.json#size_limits.hook_scan_budget に max_bytes と max_seconds が実在し、R25 の per-section IMG 必須化後の規模 (上限素材 2 点で 8 MiB 超・1 MiB 挿絵 6 節で約 8 MiB) を踏まえた値であること。asset_max_bytes とは別キーとして分離されていること
