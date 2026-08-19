---
id: "P02-inventory-c01-c21-align"
title: "component-inventory.json の C01 deterministic_checks と C21 purpose を brief 正本へ整合させる"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/component-inventory.json"
acceptance_criterion: "inventory C21 の purpose が『生成対象は role=illustration の節に限る』と読める文言であること、および inventory C01 の deterministic_checks が skill-brief-C01.json の R3-render 呼出し列 (validate / resolve / embed-assets / render-diagram-svg / build-icon-sprite / srg-image-bridge / render-handout / C09 4 ゲート / route) を欠落なく列挙すること"
objective: "component-inventory.json の C21 purpose 文言が visual-per-section-decision.json#cost_and_risk.mitigation と矛盾して読める。mitigation は『生成対象は illustration 役の節に限られる』と定めるが、inventory の記述は全節生成と解釈できる。加えて inventory C01 の deterministic_checks 7 件に embed-assets / render-diagram-svg / build-icon-sprite / srg-image-bridge / render-handout が含まれず、brief 側の呼出し列と一致しない"
verify: "inventory C21 の purpose が『生成対象は role=illustration の節に限る』と読める文言であること、および inventory C01 の deterministic_checks が skill-brief-C01.json の R3-render 呼出し列 (validate / resolve / embed-assets / render-diagram-svg / build-icon-sprite / srg-image-bridge / render-handout / C09 4 ゲート / route) を欠落なく列挙すること"
depends_on: ["P02-C01-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-inventory-c01-c21-align.md"]
consumes: []
---

# component-inventory.json の C01 deterministic_checks と C21 purpose を brief 正本へ整合させる

## 由来

build 実行中に `P02-C01-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: component-inventory.json の C21 purpose 文言が visual-per-section-decision.json#cost_and_risk.mitigation と矛盾して読める。mitigation は『生成対象は illustration 役の節に限られる』と定めるが、inventory の記述は全節生成と解釈できる。加えて inventory C01 の deterministic_checks 7 件に embed-assets / render-diagram-svg / build-icon-sprite / srg-image-bridge / render-handout が含まれず、brief 側の呼出し列と一致しない

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C01-01.json`

## 作業

`plugin-plans/guide-doc-generator/component-inventory.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-inventory-c01-c21-align.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

inventory C21 の purpose が『生成対象は role=illustration の節に限る』と読める文言であること、および inventory C01 の deterministic_checks が skill-brief-C01.json の R3-render 呼出し列 (validate / resolve / embed-assets / render-diagram-svg / build-icon-sprite / srg-image-bridge / render-handout / C09 4 ゲート / route) を欠落なく列挙すること
