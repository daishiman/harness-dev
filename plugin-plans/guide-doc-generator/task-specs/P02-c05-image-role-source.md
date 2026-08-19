---
id: "P02-c05-image-role-source"
title: "C05 の role 読取り先を C23 の section_order[].image_role へ明示する"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/agent-brief-C05.json"
acceptance_criterion: "agent-brief-C05.json の役採用手順が参照先として config/handout-purposes.json の presets[].section_order[].image_role を名指しし、値域 screenshot|illustration を C23 と一致させていること"
objective: "agent-brief-C05.json の役読取り先が曖昧。C23 が section_order[].image_role を必須キーとして持つことが確定したので、C05 は『preset が節に対して宣言した role』の参照先をこのキーへ明示すべき。参照先が書かれていないと preset のどのフィールドを見るかが実装依存になる"
verify: "agent-brief-C05.json の役採用手順が参照先として config/handout-purposes.json の presets[].section_order[].image_role を名指しし、値域 screenshot|illustration を C23 と一致させていること"
depends_on: ["P02-C05-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c05-image-role-source.md"]
consumes: []
---

# C05 の role 読取り先を C23 の section_order[].image_role へ明示する

## 由来

build 実行中に `P02-C05-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: agent-brief-C05.json の役読取り先が曖昧。C23 が section_order[].image_role を必須キーとして持つことが確定したので、C05 は『preset が節に対して宣言した role』の参照先をこのキーへ明示すべき。参照先が書かれていないと preset のどのフィールドを見るかが実装依存になる

**発見時の証跡**: `eval-log/guide-doc-generator/build/r25-improvement-2026-08-18/checklist/P02-C05-01.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/agent-brief-C05.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c05-image-role-source.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

agent-brief-C05.json の役採用手順が参照先として config/handout-purposes.json の presets[].section_order[].image_role を名指しし、値域 screenshot|illustration を C23 と一致させていること
