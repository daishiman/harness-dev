---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: 
---

# P13 — release (完了)

## 目的
L3 plan 一式(13 phase ファイル + `component-inventory.json` + `index.md` + `handoff-run-plugin-dev-plan.json` + `envelope-draft/plugin.json`)を evaluator/build 後段へ handoff できる状態に到達させる。

## 背景
goal-spec.json `handoff_targets` は `plugin-dev-plan-architect`(本 agent 自身)を指し、実際の後続消費者は `plugin-dev-plan-evaluator` または `assign-plugin-plan-evaluator` である。本 phase はその引き渡し可能性を最終確認する。

## 前提条件
Phase11 evidence 保全・Phase12 documentation 完了。

## ドメイン知識
(引用)run-plugin-dev-plan の R4(評価)/ plugin-dev-plan-evaluator。差分なし。

## 成果物
`handoff-run-plugin-dev-plan.json`(mode=update, target_plugin_slug=harness-creator, 8 routes, open_issues)が生成されている。plan ディレクトリが自己完結している(追加の外部参照なしに evaluator が読める)。

## スコープ外
実際の evaluator 起動・実 build(`plugins/harness-creator/` への実ファイル反映)は本 plan(L3)のスコープ外であり後続サイクルへ委譲する。

## 完了チェックリスト
- [ ] `handoff-run-plugin-dev-plan.json` が生成され check-build-handoff.py exit0 である
- [ ] plan ディレクトリ(13 phase + inventory + index + handoff + envelope-draft)が自己完結している

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `handoff-run-plugin-dev-plan.json` が `check-build-handoff.py` exit0 で、`task_graph_ref` が指す `task-graph.json` を含む plan ディレクトリ内の全ファイル(13 phase + inventory + index + handoff + envelope-draft)が揃い、外部参照なしに evaluator が読める。
- 満たさない例: `task-graph.json` や `component-inventory.json` 等、handoff が参照するファイルの一部が plan_dir に欠落したまま release 判定を下す。

### 事前解決済み判断
- 分岐点: `task-graph.json`(build-dispatch メタ成果物)の生成責務を release phase(P13)に置くか別 phase に置くか → 判断: `task-graph.json` は component-inventory.json + 13 phase §5 完了チェックリストから `derive-task-graph.py` が決定論導出する派生成果物であり、Phase05 実装確定後いつでも再導出可能な単一 writer 契約であるため、Phase13(release)で handoff 自己完結性の一部として最終生成・検証(`validate-task-graph.py` exit0)を確定する。

## 参照情報
- `handoff-run-plugin-dev-plan.json`
- `envelope-draft/plugin.json`
