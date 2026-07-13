---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 完了
gate_type: none
entities_covered: [C01, C02, C09]
applicability:
  applicable: true
  reason:
---

# P06 — test-run (テスト)

## 目的
P04 で確定した検証観点 (criteria/tests_min) を実際に決定論ゲート (check-spec-*.py 等) で実行し、GREEN 状態を機械的に確認する。

## 背景
本 plan 自体が11 script / 12 invocations の決定論ゲート (core 5 scripts/6 invocations + 拡張6本) で自己検証される (C6)。内訳は plan-scoped 10 invocations、input-gate 1 invocation、dogfood 1 invocation とする。

## 前提条件
P05 で handoff-run-plugin-dev-plan.json が確定していること。

## ドメイン知識
GATE_SCOPE は plan-scoped/input-gate/dogfood に分類される。check-plugin-goal-spec.py は input-gate として goal-spec を検証する。check-plugin-surface-audit.py は dogfood として plugin-dev-planner 自身の現物 surface を検証するため、plan-findings.json の G1-G10 には含まれないが、C6 の拡張ゲート証跡として progress/evidence に記録する。

## 成果物
11 script / 12 invocations の実行結果 (exit code 一覧)。

## スコープ外
なし。

## 完了チェックリスト
- [ ] plan-scoped 10ゲート (core 6 invocations + check-requirements-coverage/check-surface-inventory/check-build-handoff/check-runtime-portability) が全て exit0
- [ ] input-gate (check-plugin-goal-spec.py) と dogfood (check-plugin-surface-audit.py) が別枠証跡として exit0 記録されている

## 参照情報
scripts/specfm.py (GATE_SCRIPTS/GATE_SCOPE)
