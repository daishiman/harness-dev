---
id: "P05-x-64-c46-rowdetail-scope-asymmetry"
title: "forbid_row_detail の走査対象を cards へ拡張し row 本文の手順記述も検出する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "forbid_row_detail を持つ section_kind について rows と cards の両方が検査され、cards で組んだ冒頭概観でも E-SECTIONKIND-ROWDETAIL が発火する。かつ row/card 本文へ手順・操作の詳細を書いた構成データが exit 1 になる。回帰テストは走査対象キーをデータファイルから導出し ('rows','cards') をテストへ literal で書かない"
objective: "C46 の検査は属性駆動化後もなお criterion に届いていない。validate-handout-config.py:1075 の max_items 検査は ('rows','cards') 両方を走査するのに対し :1081-1087 の forbid_row_detail 検査は :1082 で rows ブロックに限定し cards を見ない。冒頭概観を B04 cards で組むと forbid_row_detail が 1 件も検査されず max_items だけが効く。さらに検査対象が row.sub is not None のみのため row 本文へ手順を書けば『個々の手順・操作の詳細を冒頭の流れに含めない』を素通りする。P03-x-04 の修正 (brief:674 と回帰 AC:947-948) はいずれも rows 前提のままでこの 2 つの穴を塞いでいない"
verify: "forbid_row_detail を持つ section_kind について rows と cards の両方が検査され、cards で組んだ冒頭概観でも E-SECTIONKIND-ROWDETAIL が発火する。かつ row/card 本文へ手順・操作の詳細を書いた構成データが exit 1 になる。回帰テストは走査対象キーをデータファイルから導出し ('rows','cards') をテストへ literal で書かない"
depends_on: ["P03-x-04"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-64-c46-rowdetail-scope-asymmetry.md"]
consumes: []
---

# forbid_row_detail の走査対象を cards へ拡張し row 本文の手順記述も検出する

## 由来

build 実行中に `P03-x-04` が発見したタスク (change_level=
structural)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C46 の検査は属性駆動化後もなお criterion に届いていない。validate-handout-config.py:1075 の max_items 検査は ('rows','cards') 両方を走査するのに対し :1081-1087 の forbid_row_detail 検査は :1082 で rows ブロックに限定し cards を見ない。冒頭概観を B04 cards で組むと forbid_row_detail が 1 件も検査されず max_items だけが効く。さらに検査対象が row.sub is not None のみのため row 本文へ手順を書けば『個々の手順・操作の詳細を冒頭の流れに含めない』を素通りする。P03-x-04 の修正 (brief:674 と回帰 AC:947-948) はいずれも rows 前提のままでこの 2 つの穴を塞いでいない

**発見時の証跡**: `plugins/guide-doc-generator/scripts/validate-handout-config.py`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-64-c46-rowdetail-scope-asymmetry.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

forbid_row_detail を持つ section_kind について rows と cards の両方が検査され、cards で組んだ冒頭概観でも E-SECTIONKIND-ROWDETAIL が発火する。かつ row/card 本文へ手順・操作の詳細を書いた構成データが exit 1 になる。回帰テストは走査対象キーをデータファイルから導出し ('rows','cards') をテストへ literal で書かない
