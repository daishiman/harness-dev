---
id: "P05-x-39-content-side-image-emission"
title: "構成データ生成側が画像を 1 枚も指定しない欠陥を直す (当たり先は C11 ではない)"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "構成データ生成が全 main section へ図解 1 点以上と画像 1 点以上を必ず割り当て、handout-config.json の assets が非空になる。P05-x-36 の per-section ゲートと対で緑になる"
objective: "既存生成物 4 件の handout-config.json を実測: assets が 4 件すべて 0 件、image / screenshot の語も 0 件。出力 HTML 側も img と data:image が 4 文書 26 セクション全部で 0 件。したがって画像 0 は描画側 C11 の取りこぼしではなく、構成データを作る段階 (C05 handout-content-architect / C23 resolve-handout-preset) で画像が 1 点も指定されないことに由来する。diagrams キーは app と review-3 が 5 件だが review と review-2 はキー自体が存在せず、図解も生成が不安定"
verify: "構成データ生成が全 main section へ図解 1 点以上と画像 1 点以上を必ず割り当て、handout-config.json の assets が非空になる。P05-x-36 の per-section ゲートと対で緑になる"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-39-content-side-image-emission.md"]
consumes: []
---

# 構成データ生成側が画像を 1 枚も指定しない欠陥を直す (当たり先は C11 ではない)

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 既存生成物 4 件の handout-config.json を実測: assets が 4 件すべて 0 件、image / screenshot の語も 0 件。出力 HTML 側も img と data:image が 4 文書 26 セクション全部で 0 件。したがって画像 0 は描画側 C11 の取りこぼしではなく、構成データを作る段階 (C05 handout-content-architect / C23 resolve-handout-preset) で画像が 1 点も指定されないことに由来する。diagrams キーは app と review-3 が 5 件だが review と review-2 はキー自体が存在せず、図解も生成が不安定

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-39-content-side-image-emission.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

構成データ生成が全 main section へ図解 1 点以上と画像 1 点以上を必ず割り当て、handout-config.json の assets が非空になる。P05-x-36 の per-section ゲートと対で緑になる
