---
id: "P02-c02-checklist-covered-declare"
title: "C02 の checklist_covered を宣言する (現状 null)"
phase_ref: "P02"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json"
acceptance_criterion: "skill-brief-C02.json の checklist_covered が null でなく、goal-spec.checklist のうち C02 が担う項目を列挙し、隣接する C20 (script 実装側) との重複分は副として理由つきで宣言していること。担わない隣接項目は担当 component が明示されていること"
objective: "P02-c08-checklist-coverage の AC は『C20 と C02 の checklist 項目のうち C08 が実際に担う分を漏れなく列挙』を求めるが、skill-brief-C02.json の checklist_covered は null で、C02 は goal-spec の checklist 項目を 1 件も宣言していない。分割対象が存在しないため C08 側では閉じられない。C02 は逆抽出 (HTML→構成データ) の唯一の担い手であり、被覆が null のままだと goal-spec の該当項目が誰の担当でもない状態になる"
verify: "skill-brief-C02.json の checklist_covered が null でなく、goal-spec.checklist のうち C02 が担う項目を列挙し、隣接する C20 (script 実装側) との重複分は副として理由つきで宣言していること。担わない隣接項目は担当 component が明示されていること"
depends_on: ["P02-c08-checklist-coverage"]
produces: ["plugin-plans/guide-doc-generator/discovered/P02-c02-checklist-covered-declare.md"]
consumes: []
---

# C02 の checklist_covered を宣言する (現状 null)

## 由来

build 実行中に `P02-c08-checklist-coverage` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P02-c08-checklist-coverage の AC は『C20 と C02 の checklist 項目のうち C08 が実際に担う分を漏れなく列挙』を求めるが、skill-brief-C02.json の checklist_covered は null で、C02 は goal-spec の checklist 項目を 1 件も宣言していない。分割対象が存在しないため C08 側では閉じられない。C02 は逆抽出 (HTML→構成データ) の唯一の担い手であり、被覆が null のままだと goal-spec の該当項目が誰の担当でもない状態になる

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/command-brief-C08.json`

## 作業

`plugin-plans/guide-doc-generator/briefs/skill-brief-C02.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P02-c02-checklist-covered-declare.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

skill-brief-C02.json の checklist_covered が null でなく、goal-spec.checklist のうち C02 が担う項目を列挙し、隣接する C20 (script 実装側) との重複分は副として理由つきで宣言していること。担わない隣接項目は担当 component が明示されていること
