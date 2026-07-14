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

# P10 — final-review (最終レビューゲート)

## 目的
proposer≠approver 原則に基づき、P03 の design-gate とは別 context の approver が P01-P09 全体の一貫性を最終承認する。

## 背景
final-gate は design-gate と同じ approver に固定しない (単一視点の見落としを防ぐ)。system-dev-planner 自身の計画が plugin-dev-planner 同型の決定論ゲート群で検証可能であることの最終確認点でもある (goal-spec C6)。

## 前提条件
- P09 の quality-assurance が完了している。

## ドメイン知識
- final-gate は `gate_type: final-gate` で識別される。
- goal-spec checklist C1-C13がindexとtyped tasksへ全件traceされることが必須。

## 成果物
- final-review 記録 (承認/差し戻しと理由)。

## スコープ外
- evidence 収集 (P11)。

## 完了チェックリスト
- [ ] 最終承認者が P01-P09 全体の一貫性を確認する。
- [ ] goal-spec checklist C1-C13がindex/task specsへ全件トレースされている。

## 参照情報
- goal-spec.json checklist C1-C13。
- 後続 P11 (evidence)。
