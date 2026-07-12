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
  reason: ""
---

# P13 — release (完了/PR・リリース)

## 目的
L3 plan (goal-spec + 13 phase + typed task specs + inventories + DAG + handoff + evaluator + promotion/registration contracts) の完了を宣言する。実build/PR/配布は実行しない。

## 背景
goal-spec の constraints「実プラグインは生成せず、goal-spec + 13 phase + workstream-inventory + task-graph + handoff の L3 plan までに留める」に従い、本フェーズは plan の終端を宣言するのみで build/PR は行わない。

## 前提条件
- P12 の documentation が確定している。
- 全決定論ゲートが exit0 (P11 の evidence で裏付け済み)。

## ドメイン知識
- release フェーズ = 完了/PR・リリースだが、system-dev-planner の L3 plan では「後段 (評価/build) への handoff 準備完了」を意味する。
- handoff 先は `handoff_targets: ["plugin-dev-plan-architect"]` (goal-spec) であり、次段は独立評価 (R4) または `run-skill-create`/`run-build-skill` による実 build。

## 成果物
- plan 完了宣言。
- `handoff-run-plugin-dev-plan.json` (次段への引き渡し可能な状態)。

## スコープ外
- 実際の build 実行 (harness-creator/task-graph build/capability-build へ委譲)。
- PR 作成・配布登録 (ユーザー承認後)。

## 完了チェックリスト
- [ ] 全決定論ゲート (core + 拡張) が exit0 で確認済み。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、後段 build へ引き渡し可能である。
- [ ] system-build handoffはatomic promotion receiptとdev-graph登録完了をentry gateとし、L3 draft自体は実装をauthorize/executeしない。

## 参照情報
- `handoff-run-plugin-dev-plan.json` / `task-graph.json`。
- goal-spec.json `handoff_targets`。
