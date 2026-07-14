---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビュー / final-gate)

## 目的
P09 の品質保証結果と P07 の受入判定結果を総合し、`spec-drift-guardian` plan 一式 (13 phase + component-inventory + index + handoff) が build フェーズへ引き渡し可能な最終状態にあるかを final-gate として承認する。

## 背景
final-gate は個別 component の合否 (P09) や個別 checklist 項目の合否 (P07) とは別に、plan 全体の一貫性 (依存 DAG の非循環、handoff のルーティング網羅、envelope draft の妥当性) を横断的に確認する最後の関門である。ここを通過した plan のみが後続 build (evaluator/L4) へ handoff される。

## 前提条件
- P09 の qa ゲートが合格している。
- `verify-index-topsort.py` / `check-build-handoff.py` / `validate-task-graph.py` による plan 全体の機械検証を実行できる環境がある。

## ドメイン知識
- final-gate は「個別に合格した部品を集めても全体として矛盾がないか」を見る観点であり、component 単位の qa (P09) の単純な再実行ではない。
- handoffのroutes[]がinventory全11 idと1:1対応し依存辺も一致すること、required surfaceにownerがあること、task_graph_refが宣言されることを確認する。

## 成果物
- final-gate 承認結果 (合格/差し戻し理由)。
- `verify-index-topsort.py` / `check-build-handoff.py` / `validate-task-graph.py` の実行結果。

## スコープ外
- エビデンス (実行ログ・証跡) の集約そのもの (P11 の責務)。
- ドキュメント整備 (P12 の責務)。

## 完了チェックリスト
- [ ] `component-inventory.json` の依存 DAG が非循環であり、全 component が phase の entities_covered union に含まれる (orphan なし)。
- [ ] `handoff-run-plugin-dev-plan.json` のroutes[]がinventoryの全11 component id/depends_onと過不足なく対応している。
- [ ] 30思考法の全適用証跡が`elegant-verification-30.json`にあり、4条件が全PASSである。
- [ ] `verify-index-topsort.py` / `check-build-handoff.py` / `validate-task-graph.py` が exit0。

## 参照情報
- `index.md` / `component-inventory.json` / `handoff-run-plugin-dev-plan.json` / `task-graph.json`。
- 後続 P11 (final-gate 承認をエビデンスとして記録する)。
