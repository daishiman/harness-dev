---
id: "P05-x-43-heading-marker-terminal"
title: "render-handout.py へ span.section-title data-hb-field=heading を実装する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "render-handout.py が span.section-title data-hb-field=heading を出し、ROUNDTRIP-CONTRACT.md の marker_status が present になり、round-trip で heading が復元される"
objective: "P03-x-02 で C11 brief 側の終端が確定した (付与先は h2 ではなく見出しテキストだけを内容に持つ内側の span.section-title 1 個。h2 へ付けると C20 が span.section-num の連番を見出しテキストの一部として復元してしまう)。出荷側 render-handout.py の build_section は未実装で、ROUNDTRIP-CONTRACT.md の marker_status も absent のまま。この終端が無い間は plugin 自身が出した HTML でも /sections/*/heading が E-EXTRACT-UNRECOVERABLE となり C02 feedback_contract OUT1 が成立しない"
verify: "render-handout.py が span.section-title data-hb-field=heading を出し、ROUNDTRIP-CONTRACT.md の marker_status が present になり、round-trip で heading が復元される"
depends_on: ["P03-x-02"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-43-heading-marker-terminal.md"]
consumes: []
---

# render-handout.py へ span.section-title data-hb-field=heading を実装する

## 由来

build 実行中に `P03-x-02` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: P03-x-02 で C11 brief 側の終端が確定した (付与先は h2 ではなく見出しテキストだけを内容に持つ内側の span.section-title 1 個。h2 へ付けると C20 が span.section-num の連番を見出しテキストの一部として復元してしまう)。出荷側 render-handout.py の build_section は未実装で、ROUNDTRIP-CONTRACT.md の marker_status も absent のまま。この終端が無い間は plugin 自身が出した HTML でも /sections/*/heading が E-EXTRACT-UNRECOVERABLE となり C02 feedback_contract OUT1 が成立しない

**発見時の証跡**: `plugin-plans/guide-doc-generator/briefs/`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-43-heading-marker-terminal.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

render-handout.py が span.section-title data-hb-field=heading を出し、ROUNDTRIP-CONTRACT.md の marker_status が present になり、round-trip で heading が復元される
