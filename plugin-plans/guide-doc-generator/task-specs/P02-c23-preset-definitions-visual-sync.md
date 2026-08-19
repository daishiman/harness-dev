---
id: "P02-c23-preset-definitions-visual-sync"
title: "script-brief-C23.json#preset_definitions を DIAGRAM/IMG/image_role 込みの出荷形へ揃える"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/script-brief-C23.json"
acceptance_criterion: "script-brief-C23.json#preset_definitions の各 section_order 要素が id/heading/section_kind/recommended_parts/required/image_role の 6 キーを持ち、全 main 節の recommended_parts が DIAGRAM と IMG を含み、image_role が {screenshot, illustration} に閉じる。かつ出荷 config/handout-purposes.json との差分が 0 であることを実測した証跡がある"
objective: "P05-x-03 で出荷 preset の全 43 節へ DIAGRAM / IMG / image_role を付与した。出荷 config の _meta.source_of_truth は script-brief-C23.json#preset_definitions を正本に指名しているため、brief 側の preset_definitions が旧形 (DIAGRAM/IMG/image_role 無し) のままだと指名だけが残って実体が 2 つに割れる。brief は本 node の write_scope 外"
verify: "script-brief-C23.json#preset_definitions の各 section_order 要素が id/heading/section_kind/recommended_parts/required/image_role の 6 キーを持ち、全 main 節の recommended_parts が DIAGRAM と IMG を含み、image_role が {screenshot, illustration} に閉じる。かつ出荷 config/handout-purposes.json との差分が 0 であることを実測した証跡がある"
depends_on: ["P05-x-03"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c23-preset-definitions-visual-sync.md"]
consumes: []
---

# script-brief-C23.json#preset_definitions を DIAGRAM/IMG/image_role 込みの出荷形へ揃える

## 由来

build 実行中に `P05-x-03` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P05-x-03 で出荷 preset の全 43 節へ DIAGRAM / IMG / image_role を付与した。出荷 config の _meta.source_of_truth は script-brief-C23.json#preset_definitions を正本に指名しているため、brief 側の preset_definitions が旧形 (DIAGRAM/IMG/image_role 無し) のままだと指名だけが残って実体が 2 つに割れる。brief は本 node の write_scope 外

**発見時の証跡**: `plugins/guide-doc-generator/config/handout-purposes.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/script-brief-C23.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c23-preset-definitions-visual-sync.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

script-brief-C23.json#preset_definitions の各 section_order 要素が id/heading/section_kind/recommended_parts/required/image_role の 6 キーを持ち、全 main 節の recommended_parts が DIAGRAM と IMG を含み、image_role が {screenshot, illustration} に閉じる。かつ出荷 config/handout-purposes.json との差分が 0 であることを実測した証跡がある
