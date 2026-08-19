---
id: "P05-x-62-overview-three-types-not-shipped"
title: "全体像 3 種の型 (timeline/map/thesis) を出荷 section_kinds へ反映し version を drift 検出子にする"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "出荷 config/handout-sections.json の section_kinds が timeline / map / thesis を含み flow-overview に deprecated と superseded_by が付く。かつ plan 側と出荷側の section_kinds が内容一致することを機械検査するゲートが存在し、内容が異なるのに version が同値なら fail する"
objective: "利用者裁定『全体像は timeline / map / thesis の 3 種の型に集約』は plan 側 briefs/config/handout-sections.json にのみ反映済み (section_kinds に timeline/map/thesis が実在し flow-overview は deprecated:true + superseded_by:timeline)。出荷 config/handout-sections.json には 3 件とも不在で flow-overview も現役。にもかかわらず両ファイルとも version:2 を宣言しており version が drift 検出子として機能していない。DT-1 (dir_token 8/8 不一致) と同型の第二正本問題だが、利用者裁定そのものが出荷へ届いていない点でより重い"
verify: "出荷 config/handout-sections.json の section_kinds が timeline / map / thesis を含み flow-overview に deprecated と superseded_by が付く。かつ plan 側と出荷側の section_kinds が内容一致することを機械検査するゲートが存在し、内容が異なるのに version が同値なら fail する"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-62-overview-three-types-not-shipped.md"]
consumes: []
---

# 全体像 3 種の型 (timeline/map/thesis) を出荷 section_kinds へ反映し version を drift 検出子にする

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 利用者裁定『全体像は timeline / map / thesis の 3 種の型に集約』は plan 側 briefs/config/handout-sections.json にのみ反映済み (section_kinds に timeline/map/thesis が実在し flow-overview は deprecated:true + superseded_by:timeline)。出荷 config/handout-sections.json には 3 件とも不在で flow-overview も現役。にもかかわらず両ファイルとも version:2 を宣言しており version が drift 検出子として機能していない。DT-1 (dir_token 8/8 不一致) と同型の第二正本問題だが、利用者裁定そのものが出荷へ届いていない点でより重い

**発見時の証跡**: `plugins/guide-doc-generator/config/handout-sections.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-62-overview-three-types-not-shipped.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

出荷 config/handout-sections.json の section_kinds が timeline / map / thesis を含み flow-overview に deprecated と superseded_by が付く。かつ plan 側と出荷側の section_kinds が内容一致することを機械検査するゲートが存在し、内容が異なるのに version が同値なら fail する
