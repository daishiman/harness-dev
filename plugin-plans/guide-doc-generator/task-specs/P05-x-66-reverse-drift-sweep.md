---
id: "P05-x-66-reverse-drift-sweep"
title: "実装から設計へ向けた逆向き突合を全 AC へ一度通す"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugin-plans/guide-doc-generator/evidence/"
acceptance_criterion: "全 component の AC について『出荷実装が brief より厳しい / 適用対象が広い』箇所を列挙した evidence が存在し、各件が順向き・逆向きのどちらのドリフトかで分類されている"
objective: "本 cycle で初めて『出荷実装の方が正しく設計散文が古い』逆向きドリフトが 2 件検出された (C46 の slug 名指し / C49 の必須性欠落。出荷側は ATTR_MAX_ITEMS の属性駆動と REQUIRED_CONFIG_KEYS で既に正しい)。これまでの RG-01 / RG-02 / RG-04 / DT-1 はすべて『設計が正しく出荷が未追随』の順向きで、逆向きを検出する手段が無い。brief だけを読んで修正すると実装側を壊す方向の提案になる"
verify: "全 component の AC について『出荷実装が brief より厳しい / 適用対象が広い』箇所を列挙した evidence が存在し、各件が順向き・逆向きのどちらのドリフトかで分類されている"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-66-reverse-drift-sweep.md"]
consumes: []
---

# 実装から設計へ向けた逆向き突合を全 AC へ一度通す

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 本 cycle で初めて『出荷実装の方が正しく設計散文が古い』逆向きドリフトが 2 件検出された (C46 の slug 名指し / C49 の必須性欠落。出荷側は ATTR_MAX_ITEMS の属性駆動と REQUIRED_CONFIG_KEYS で既に正しい)。これまでの RG-01 / RG-02 / RG-04 / DT-1 はすべて『設計が正しく出荷が未追随』の順向きで、逆向きを検出する手段が無い。brief だけを読んで修正すると実装側を壊す方向の提案になる

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/`

## 作業

`plugin-plans/guide-doc-generator/evidence/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-66-reverse-drift-sweep.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

全 component の AC について『出荷実装が brief より厳しい / 適用対象が広い』箇所を列挙した evidence が存在し、各件が順向き・逆向きのどちらのドリフトかで分類されている
