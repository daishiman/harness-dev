---
id: "P05-x-41-prerequisite-section-missing"
title: "前提セクションの器そのものを新設する"
phase_ref: "P05"
execution_kind: "direct-task"
write_scope: "plugins/guide-doc-generator/"
acceptance_criterion: "handout-sections.json に前提セクションが定義され、外部コネクタが前提セクション内へ描画される"
objective: "既存生成物 4 件の実在見出しは 要点 / 現行の大きな流れ / 突き合わせて分かったこと / 自動化の可否をどう見るか / 次にやること / 補足 のみで、前提 に相当するセクションが 1 つも無い。P05-x-34 で config/handout-vocabulary.json#connectors を新設しても、それを描画する器が無ければ利用者要件 R10 (前提に Google Drive / OneDrive / kintone を記述) は満たせない。両者は対で必要"
verify: "handout-sections.json に前提セクションが定義され、外部コネクタが前提セクション内へ描画される"
depends_on: ["P02-x-01"]
produces: ["plugin-plans/guide-doc-generator/discovered/P05-x-41-prerequisite-section-missing.md"]
consumes: []
---

# 前提セクションの器そのものを新設する

## 由来

build 実行中に `P02-x-01` が発見したタスク (change_level=
additive)。本 spec は planner の外ループ (accept-discovered-task.py) が
discovered-task form から決定論生成したものであり、derive 由来の spec と同じ契約で扱う。

**発見理由**: 既存生成物 4 件の実在見出しは 要点 / 現行の大きな流れ / 突き合わせて分かったこと / 自動化の可否をどう見るか / 次にやること / 補足 のみで、前提 に相当するセクションが 1 つも無い。P05-x-34 で config/handout-vocabulary.json#connectors を新設しても、それを描画する器が無ければ利用者要件 R10 (前提に Google Drive / OneDrive / kintone を記述) は満たせない。両者は対で必要

**発見時の証跡**: `plugin-plans/guide-doc-generator/evidence/P02.json`

## 作業

`plugins/guide-doc-generator/` の範囲で上記を解消する。編集先 (write_scope) と
完了トークン (produces) は別物である点に注意する — 実体の変更は write_scope 配下へ行い、
完了したことの記録を `plugin-plans/guide-doc-generator/discovered/P05-x-41-prerequisite-section-missing.md` へ残す。write_scope は複数タスクで共有されうるため
成果物の鍵にはできない (producer 一意制約)。

## 受入条件

handout-sections.json に前提セクションが定義され、外部コネクタが前提セクション内へ描画される
