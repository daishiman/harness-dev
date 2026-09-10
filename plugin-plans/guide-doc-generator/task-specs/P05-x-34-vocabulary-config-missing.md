---
id: "P05-x-34-vocabulary-config-missing"
title: "config/handout-vocabulary.json を新設し connectors / attainment_level_labels を実装する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "config/handout-vocabulary.json が実在し connectors に Google Drive / OneDrive / kintone を含む。C11 が前提セクションへ描画し C20 が round-trip で復元する"
objective: "C01/C11/C12/C20 の 4 brief が config/handout-vocabulary.json#connectors と #attainment_level_labels を正本と名指すが、ファイル自体が config ディレクトリに存在せず、出荷 scripts への grep も connectors / handout-vocabulary ともに 0 件。producer も consumer も丸ごと不在で語彙正規化層が存在しない。利用者要件 R10 (前提に Google Drive / OneDrive / kintone を記述) の受け皿がこれに当たる"
verify: "config/handout-vocabulary.json が実在し connectors に Google Drive / OneDrive / kintone を含む。C11 が前提セクションへ描画し C20 が round-trip で復元する"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-34-vocabulary-config-missing.md"]
consumes: []
---

# config/handout-vocabulary.json を新設し connectors / attainment_level_labels を実装する

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: C01/C11/C12/C20 の 4 brief が config/handout-vocabulary.json#connectors と #attainment_level_labels を正本と名指すが、ファイル自体が config ディレクトリに存在せず、出荷 scripts への grep も connectors / handout-vocabulary ともに 0 件。producer も consumer も丸ごと不在で語彙正規化層が存在しない。利用者要件 R10 (前提に Google Drive / OneDrive / kintone を記述) の受け皿がこれに当たる

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-34-vocabulary-config-missing.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

config/handout-vocabulary.json が実在し connectors に Google Drive / OneDrive / kintone を含む。C11 が前提セクションへ描画し C20 が round-trip で復元する
