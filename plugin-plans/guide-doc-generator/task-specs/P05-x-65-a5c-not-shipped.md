---
id: "P05-x-65-a5c-not-shipped"
title: "provenance ゲート付き必須性 (A5c) を出荷 schema と validate へ実装する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "provenance を持つ構成データで normalize 充填クラスのフィールドが欠落すると E-FIELD-MISSING で exit 1 になり、provenance を持たない手書き入力では exit 0 のままであることを両側から測るテストが存在する"
objective: "出荷 schemas/handout-config.schema.json の top-level required 16 件に presentation_order が不在で、validate-handout-config.py にも C12 A5c 相当 (provenance を持つ構成データでは normalize 充填クラスが非空) の検査が無い。現状は verify-handout-narrative.py:77 の REQUIRED_CONFIG_KEYS が偶然の第 2 防壁になっているだけで C11 / C20 の経路には防壁が無い。normalize 後に手で presentation_order を削ると C56 の実画面先行検査が黙って無効化される"
verify: "provenance を持つ構成データで normalize 充填クラスのフィールドが欠落すると E-FIELD-MISSING で exit 1 になり、provenance を持たない手書き入力では exit 0 のままであることを両側から測るテストが存在する"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-65-a5c-not-shipped.md"]
consumes: []
---

# provenance ゲート付き必須性 (A5c) を出荷 schema と validate へ実装する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 出荷 schemas/handout-config.schema.json の top-level required 16 件に presentation_order が不在で、validate-handout-config.py にも C12 A5c 相当 (provenance を持つ構成データでは normalize 充填クラスが非空) の検査が無い。現状は verify-handout-narrative.py:77 の REQUIRED_CONFIG_KEYS が偶然の第 2 防壁になっているだけで C11 / C20 の経路には防壁が無い。normalize 後に手で presentation_order を削ると C56 の実画面先行検査が黙って無効化される

**発見時の証跡**: `plugins/guide-doc-generator/schemas/handout-config.schema.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-65-a5c-not-shipped.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

provenance を持つ構成データで normalize 充填クラスのフィールドが欠落すると E-FIELD-MISSING で exit 1 になり、provenance を持たない手書き入力では exit 0 のままであることを両側から測るテストが存在する
