---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
plugin-dev-planner 側 (producer) が既に提供する task-graph (schema/導出器/validator/ready-set 計算器・handoff 契約 `task_graph_ref`) を、harness-creator 側 (consumer) が実際に消費する 7 責務 (並列 dispatch・task state 単一 writer write-back・produces/consumes 成果物注入・discovered-task emit・進捗集計・未処理 discovered-task 完了ブロック・task-graph 実行知見の knowledge 化) へ落とし込むという `goal-spec.json` (`target_plugin_slug: harness-creator`・checklist C1-C13・constraints 追加含む) を確定する。

## 背景
producer 側 plan (`plugin-plans/plugin-dev-planner/`) は R2/R3 が完了し、`task-graph.json` (schema_version "1.0")・`task-graph.schema.json` (parent_of/depends_on/produces/consumes の 4 エッジ型・blocks は逆向き導出専用)・`derive-task-graph.py`/`validate-task-graph.py`/`compute-ready-set.py`・`discovered-task.schema.json`+受理機構・`handoff-notes.schema.json` を SSOT として確定済みである。本 plan (consumer 側) はこれらを再実装せず消費し、`/capability-build` (E2 route モード) へ実際の並列 dispatch 実行本体・state write-back・produces 成果物の consumes 注入・discovered-task の emit を追加する。

## 前提条件
- 対象プラグイン `plugins/harness-creator/` は既存プラグイン (distributable:false・version 1.1.0) であり、本 plan は `artifact_class: existing-plugin-update` として自己拡張を行う。
- 直前の plan サイクル (`plugin-plans/finish/harness-creator/`) は E1 (新規作成フロー)/E2 (改善フロー R1)/E3 (改善還流) の境界を対象にしており build 済み。本 plan の checklist C1-C13 は task-graph という別テーマであり、`references/pipeline-boundary-contract.md` へ新たな境界 (task-graph 消費・E4) と completion/knowledge gate を追記する立場にある。
- producer 側 `handoff-run-plugin-dev-plan.json` の `open_issues[0]` が本 plan の責務範囲・task state ファイル仮置きパス・境界正本の所在を明示済みで、これを前提として引き継ぐ。

## ドメイン知識
- goal-spec の checklist は 13 件 (C1-C13)。C1 (並列 dispatch)・C2 (state write-back)・C3 (produces/consumes 注入)・C4 (discovered-task emit)・C5 (進捗集計) は script/test 主体、C6 (後方互換) は test、C7 (境界契約文書追記) は script/human 混在、C8 (fork evaluator の意味判定) は human、C9 (elegant-review 4条件+全ゲート exit0) は横断完了条件、C10 (冪等再開・実行排他・graph_hash pin)・C11 (実行イベントログ)・C12 (実行時停滞検出) は実行時契約、C13 (未処理 discovered-task 完了ブロック + knowledge 化) は完了前ゲートである。
- constraints の要旨: (1) task-graph の schema/導出器/validator/ready-set 計算器は producer 側 SSOT・再実装複製禁止、(2) task state ファイルの writer は consumer 側 L4 実行系のみ (単一 writer)、(3) canonical serialization は producer 側 canonicalizer が SSOT、(4) 13 ファイル固定解除後も consumer は task-graph を構成の正本として読む、(5) discovered-task emit は追補提案であり受理判断は producer 側二段受理に従い plan を直接編集しない、(6) script は Python 標準ライブラリのみ (.sh/.js 新規禁止・yaml import 禁止)、(7) 既存 route-build-report 契約 (PR#70) は additive 拡張のみ、(8) harness 現状未達数値は component へ焼かない (Goodhart 回避)、(9) 未処理 discovered-task は completed を block、(10) harness は graph を直接 mutate せず proposal/knowledge のみを書く、(11) knowledge は生ログではなく bounded summary と source_ref に蒸留する。
- handoff_targets: run-skill-create / run-build-skill / capability-build。max_loops: 5。open_questions 3 件 (並列度既定値/リトライ規約/state file 配置仮置き)。

## 成果物
- `goal-spec.json` (確定済み・本 phase 時点で再読込による内容確認のみ行い、書き換えは行わない)。

## スコープ外
- component-inventory.json の分解 (P02 の責務)。
- task-graph 自体の schema/導出/ready-set 計算ロジックの詳細設計 (producer 側の責務。本 plan は消費のみ)。

## 完了チェックリスト
- [ ] purpose/background/goal が「task-graph consumer 責務の実装」という改善要求の文脈で一貫している。
- [ ] checklist C1-C13 それぞれに verify_by (script/test/human) が付与されている。
- [ ] target_plugin_slug が `harness-creator` に固定され、plan_dir が `plugin-plans/harness-creator` に固定されている。
- [ ] constraints の 10 点 (本文要旨では 11 項目に分解) が本 plan 全体の設計判断へ反映される前提が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: goal-spec の goal 文が「producer 側 task-graph を re-implement せず consume し、7 責務を capability-build へ実装する」ことを明示し、checklist 13 件それぞれが独立した verify_by を持つ。
- 満たさない例: task-graph 消費の目的が「並列実行を追加する」とだけ記され、producer/consumer の責務境界 (SSOT 遵守/単一 writer) が未確定のまま P02 へ進む。

### 事前解決済み判断
- 分岐点: open_questions[2] (task state ファイル配置は仮置き) をどう扱うか → 判断: producer 側 handoff の `open_issues[0]` が既に `eval-log/<slug>/build/task-state.json` (route-build-report と同居) を仮置きとして示しており、本 plan (consumer 側) がこれを最終確定する (P02 で反映)。

## 参照情報
- `plugin-plans/harness-creator/goal-spec.json`。
- `plugin-plans/plugin-dev-planner/handoff-run-plugin-dev-plan.json` (`open_issues[0]`)。
- `plugins/harness-creator/references/pipeline-boundary-contract.md`。
- 後続 P02 (design)。
