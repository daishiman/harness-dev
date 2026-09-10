---
id: "P05-x-36-per-section-visual-gate"
title: "図解・画像の充足判定を文書全体比率から per-section 判定へ変える"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "全 main section が図解 1 点以上と画像 1 点以上を持つことを per-section で検査し、欠けたセクションを pointer 付きで error として報告する"
objective: "W-DIAGRAM-FEW の pointer が :937 で /diagrams = 文書全体比率になっており、REQ-2/REQ-3 が要求する per-section 判定になっていない。加えて E-IMAGE-ABSENT / role_split / min_images_per_main_section は出荷ツリー全体で 0 件。利用者要件『毎回セクションごとに図解と画像を追加する』が判定不能"
verify: "全 main section が図解 1 点以上と画像 1 点以上を持つことを per-section で検査し、欠けたセクションを pointer 付きで error として報告する"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-36-per-section-visual-gate.md"]
consumes: []
---

# 図解・画像の充足判定を文書全体比率から per-section 判定へ変える

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: W-DIAGRAM-FEW の pointer が :937 で /diagrams = 文書全体比率になっており、REQ-2/REQ-3 が要求する per-section 判定になっていない。加えて E-IMAGE-ABSENT / role_split / min_images_per_main_section は出荷ツリー全体で 0 件。利用者要件『毎回セクションごとに図解と画像を追加する』が判定不能

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-36-per-section-visual-gate.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

全 main section が図解 1 点以上と画像 1 点以上を持つことを per-section で検査し、欠けたセクションを pointer 付きで error として報告する
