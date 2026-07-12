---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
C01-C08 の `quality_gates` (p0_lint・build_trace:required・elegant_review C1-C4 all_pass・content_review PASS+sha_match・evaluator threshold≥80,high_max:0) を確定し、component-inventory.json へ反映する。

## 背景
p0_lint はスクリプト系 (C01-C05/C07/C08) が `lint-script-frontmatter`、slash-command 系 (C06) が `validate-frontmatter` を用いる。既存 harness-creator の CI 配線 (governance-check) が本サイクル追加後もそのまま適用される。

## 前提条件
- P08 の SSOT 重複判定が完了している。

## ドメイン知識
- p0_lint: C01-C05/C07/C08 (script) は `lint-script-frontmatter`、C06 (slash-command) は `validate-frontmatter`。
- elegant_review: C1-C4 (proposer≠approver、design と final の両方で適用)。
- content_review: PASS + sha_match。
- evaluator: threshold 80 + high_max 0。

## 成果物
- C01-C08 の `quality_gates` ブロック (component-inventory.json に反映済み)。

## スコープ外
- 実測ゲート実行結果の記録 (build 後・本 plan の対象外)。

## 完了チェックリスト
- [ ] C01-C08 全ての quality_gates が p0_lint/build_trace/elegant_review/content_review/evaluator の 5 要素を全て持つ。

### 受入例
（本 phase は縮小要件対象 [REDUCED_REQUIREMENT_PHASES] のため、見出し直下の本文は簡略形で足りる。）

### 事前解決済み判断
（本 phase は縮小要件対象のため、見出し直下の本文は簡略形で足りる。）

## 参照情報
- P08 (refactoring)。
- `plugin-plans/harness-creator/component-inventory.json`。
- 後続 P10 (final-review)。
