---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
新規スクリプト群 (dispatch-ready-set.py/sync-task-state.py/inject-task-inputs.py/emit-discovered-task.py/summarize-task-progress.py/manage-build-lease.py/record-task-graph-knowledge.py) が既存 `plugins/harness-creator/scripts/` 配下のスクリプトと重複ロジックを持たないことを `lint-ssot-duplication.py` で確認する設計を確定する。

## 背景
既存 `scripts/` 配下には `build-script-route.py` (route の build 実行)・`emit-improvement-handoff.py` (E3・build 完了後の改善還流 emit)・`check-route-component-parity.py`・`compute-dogfooding-metrics.py`・`validate-plan-coverage.py` が既に存在し、本サイクルの新規スクリプトがこれらと観点/データ型で重複しないことを明示する必要がある。

## 前提条件
- P07 の受入観点が確定している。

## ドメイン知識
- `build-script-route.py` (既存) は「route を実際に scaffold する (build 実行そのもの)」責務であり、`dispatch-ready-set.py` (新規) は「どの route を今バッチで並列投入すべきか決定する (build 実行の前段の順序決定)」責務であって、対象データ (build 実行 vs 依存グラフの ready-set) が異なるため重複しない。両者は連続する 2 段階 (先に dispatch-ready-set.py が対象を決め、決まった対象へ build-script-route.py が実行される) であり、同一ロジックの重複実装ではない。
- `emit-improvement-handoff.py` (E3・既存) と `emit-discovered-task.py` (E4・新規) は、消費するスキーマ (`improvement-handoff.schema.json` vs `discovered-task.schema.json`)・発生時点 (build 完了後 vs build 進行中)・受理経路 (evaluator 後の findings 集約 vs 二段受理) のいずれも異なり、P02 で確定した通り重複しない。
- `sync-task-state.py`/`inject-task-inputs.py`/`summarize-task-progress.py` はいずれも task-state.json/task-graph.json という新規データ構造 (グラフ/状態機械) を対象にし、既存スクリプトが扱う「plan 成果物の内容検証 (テキスト/JSON 構造の lint)」とは対象データの種別自体が異なる。
- `manage-build-lease.py` (新規) は build 開始時の lock/lease/graph_hash pin 安全性ゲートであり、既存の route 実行や handoff emit とは発火タイミング・書込範囲が異なる。`record-task-graph-knowledge.py` (新規) は未処理 discovered-task の completion gate と蒸留済み knowledge 追記を担い、`emit-discovered-task.py` の proposal emit とも `emit-improvement-handoff.py` の改善 handoff emit とも重複しない。

## 成果物
- SSOT 重複なしの判定根拠 (index.md `plugin_meta.ssot_dedup` へ反映)。

## スコープ外
- 実際の `lint-ssot-duplication.py` 実行 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] 新規スクリプト群 7 本それぞれについて、既存スクリプトとの重複懸念点とその非該当理由が具体的に説明されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 「build-script-route.py (build 実行) と dispatch-ready-set.py (投入順序決定)」が処理段階 (実行 vs 事前決定) の点で明確に異なると具体的に説明されている。
- 満たさない例: 「重複していないはず」とだけ記され、両者の責務境界が具体的に説明されない。

### 事前解決済み判断
- 分岐点: 本 phase の entities_covered を空にするか C01-C08 を計上するか → 判断: 空 (本 phase は SSOT 重複の有無を確認する判断フェーズであり、component の build_target への生成/検証作業そのものではないため。component-domain.md の entities_covered 割当規則に従う)。

## 参照情報
- P07 (acceptance-criteria)。
- `plugins/harness-creator/scripts/build-script-route.py` / `emit-improvement-handoff.py`。
- 後続 P09 (quality-assurance)。
