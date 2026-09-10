---
id: "P05-x-03-image-threshold-key"
title: "出荷 config の per-section 閾値キーを正本へ追従させる"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/config/handout-visual-policy.json"
acceptance_criterion: "config/handout-visual-policy.json#thresholds に min_diagrams_per_main_section (単数形) と min_images_per_main_section が実在し、旧 min_diagrams_per_main_sections (複数形・総量比) が 0 件であること。値は improvement/visual-per-section-decision.json#decision の value=1 と一致すること"
objective: "実測: 出荷 config の閾値キーは min_diagrams_per_main_sections (旧複数形) の 1 件のみで、C12 の E-IMAGE-ABSENT が参照する min_images_per_main_section が実データ側に存在しない。閾値の producer が無いまま error 級ゲートが live になっている"
verify: "config/handout-visual-policy.json#thresholds に min_diagrams_per_main_section (単数形) と min_images_per_main_section が実在し、旧 min_diagrams_per_main_sections (複数形・総量比) が 0 件であること。値は improvement/visual-per-section-decision.json#decision の value=1 と一致すること"
depends_on: ["P02-C16-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-03-image-threshold-key.md"]
consumes: []
---

# 出荷 config の per-section 閾値キーを正本へ追従させる

## 由来

build 実行中に `P02-C16-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 実測: 出荷 config の閾値キーは min_diagrams_per_main_sections (旧複数形) の 1 件のみで、C12 の E-IMAGE-ABSENT が参照する min_images_per_main_section が実データ側に存在しない。閾値の producer が無いまま error 級ゲートが live になっている

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C16-01.json`

## 作業

`plugins/guide-doc-generator/config/handout-visual-policy.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-03-image-threshold-key.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

config/handout-visual-policy.json#thresholds に min_diagrams_per_main_section (単数形) と min_images_per_main_section が実在し、旧 min_diagrams_per_main_sections (複数形・総量比) が 0 件であること。値は improvement/visual-per-section-decision.json#decision の value=1 と一致すること
