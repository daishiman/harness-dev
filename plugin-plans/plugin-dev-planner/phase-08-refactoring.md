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
新規スクリプト群 (derive-task-graph.py/validate-task-graph.py/compute-ready-set.py/accept-discovered-task.py/apply-handoff-notes.py) が既存スクリプト (check-generative-fidelity.py/check-downstream-harness.py 等) と重複ロジックを持たないことを `lint-ssot-duplication.py` で確認する設計を確定する。

## 背景
前サイクル (旧 C1-C12・generative-fidelity/downstream-harness 層) と本サイクル (task-graph 層) は同一 skill 内に共存するため、検出ロジック (denylist 検出・完全一致検出等) と本サイクルの検出ロジック (DAG 検証・ready-set 計算等) が観点として重複しないことを明示する必要がある。

## 前提条件
- P07 の受入観点が確定している。

## ドメイン知識
- 前サイクルのスクリプト群は「生成された phase 本文の具体度・仕様書自体の実効性」を検出する層 A/B であり、本サイクルの新規スクリプト群は「task-graph という第 3 の射影のデータ構造・依存解決」を検出する層であって、検出対象 (テキスト内容 vs グラフ構造) が異なるため、SSOT 重複は生じない。

## 成果物
- SSOT 重複なしの判定根拠 (index.md `plugin_meta.ssot_dedup` へ反映)。

## スコープ外
- 実際の `lint-ssot-duplication.py` 実行 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] 新規スクリプト群と既存スクリプト群の検出対象が重複しないことが具体的に説明されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 「denylist 検出 (テキスト内容の文字列走査)」と「DAG 検証 (グラフ構造のノード/エッジ走査)」が対象データ型 (文字列 vs グラフ) の点で明確に異なると具体的に説明されている。
- 満たさない例: 「重複していないはず」とだけ記され、両者の検出対象の違いが具体的に説明されない。

### 事前解決済み判断
- 分岐点: 本 phase の entities_covered を空にするか C01 を計上するか → 判断: 空 (本 phase は SSOT 重複の有無を確認する判断フェーズであり、C01 の build_target への生成/検証作業そのものではないため。component-domain.md の entities_covered 割当規則に従う)。

## 参照情報
- P07 (acceptance-criteria)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-generative-fidelity.py` / `check-downstream-harness.py`。
- 後続 P09 (quality-assurance)。
