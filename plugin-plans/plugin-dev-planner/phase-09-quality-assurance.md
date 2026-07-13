---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C02]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
C01/C02 の `quality_gates` (p0_lint 8 本・build_trace:required・elegant_review C1-C4 all_pass・content_review PASS+sha_match・evaluator threshold≥80,high_max:0) を確定し、component-inventory.json へ反映する。

## 背景
P0 lint (8 本)・build-trace・schema parity・content-review は既存 run-plugin-dev-plan/assign-plugin-plan-evaluator の両 skill が既に備える品質機構であり、本サイクルの新規ファイル追加・既存ファイル Edit 拡張後もこれらのゲートが変わらず適用される。

## 前提条件
- P08 の SSOT 重複判定が完了している。

## ドメイン知識
- p0_lint: lint-skill-name/lint-skill-description/lint-skill-tree/validate-frontmatter/lint-dependency-direction/lint-skill-dep-step7/lint-forbidden-deps/lint-manifest-contents の 8 本 (C01/C02 共通)。
- elegant_review: C1-C4 (design と final の両方で適用、proposer≠approver)。
- content_review: PASS + sha_match (生成コンテンツと評価対象 sha の一致)。
- evaluator: threshold 80 + high_max 0 (assign-plugin-plan-evaluator の verdict がこの閾値を満たす)。

## 成果物
- C01/C02 の `quality_gates` ブロック (component-inventory.json に反映済み)。

## スコープ外
- 実測ゲート実行結果の記録 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] C02 evaluator skillを更新し、C01/C02双方についてp0_lint/build_trace/elegant_review/content_review/evaluatorの5要素とC17/C19のgenuine判定を検証できる。

### 受入例
（本 phase は縮小要件対象 (REDUCED_REQUIREMENT_PHASES) のため、見出し直下の本文は簡略形で足りる。）

### 事前解決済み判断
（本 phase は縮小要件対象のため、見出し直下の本文は簡略形で足りる。）

## 参照情報
- P08 (refactoring)。
- `plugin-plans/plugin-dev-planner/component-inventory.json`。
- 後続 P10 (final-review)。
