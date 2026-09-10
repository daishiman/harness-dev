---
id: "P05-x-67-new-section-kinds-stale"
title: "r21_decisions.new_section_kinds の読み方を確定し R25 追加分との関係を明記する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/component-inventory.json"
acceptance_criterion: "new_section_kinds が R21 由来の記録であることが明示されるか、R25 追加分を含めて section_kind 追加の完全な履歴になるかのいずれかに決着し、どちらかが機械検査される"
objective: "component-inventory.json#r21_decisions.new_section_kinds が 6 件のままで R25/REQ-4 で足した timeline / map / thesis が入っていない。R21 の記述としては正しいが new_section_kinds を section_kind 追加の履歴と読むと不完全。P05-x-62 (出荷 config への 3 種未反映) と同じ根"
verify: "new_section_kinds が R21 由来の記録であることが明示されるか、R25 追加分を含めて section_kind 追加の完全な履歴になるかのいずれかに決着し、どちらかが機械検査される"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-67-new-section-kinds-stale.md"]
consumes: []
---

# r21_decisions.new_section_kinds の読み方を確定し R25 追加分との関係を明記する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: component-inventory.json#r21_decisions.new_section_kinds が 6 件のままで R25/REQ-4 で足した timeline / map / thesis が入っていない。R21 の記述としては正しいが new_section_kinds を section_kind 追加の履歴と読むと不完全。P05-x-62 (出荷 config への 3 種未反映) と同じ根

**発見時の証跡**: `plugin-plans/guide-doc-generator/component-inventory.json`

## 作業

`plugin-plans/guide-doc-generator/component-inventory.json` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-67-new-section-kinds-stale.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

new_section_kinds が R21 由来の記録であることが明示されるか、R25 追加分を含めて section_kind 追加の完全な履歴になるかのいずれかに決着し、どちらかが機械検査される
