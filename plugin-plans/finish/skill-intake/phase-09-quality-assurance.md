---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証ゲート)

## 目的
C01-C04 それぞれが `component-inventory.json.quality_gates` (p0_lint(kind別)/build_trace/elegant_review の 4 条件/content_review/evaluator) と `harness_coverage` (min≥80/kind_pass) を build 後に満たす設計になっていることを、現状未達数値を焼き込まずに確認する (Goodhart 回避)。elegant_review の 4 条件は no_contradiction/no_missing/consistent/dependency_integrity を指し、goal-spec checklist C1-C8 とは別名前空間である。

## 背景
本 plan の環境ポリシー (index `## 環境ポリシー`) は「≥80% を満たす設計」を要件化し、harness 現状未達数値をコンポーネントエントリへ焼かないことを定める。本 phase はこの規律が C01-C04 の quality_gates/harness_coverage として一貫して宣言されているかを確認する QA ゲートである。

## 前提条件
- P08 のリファクタリング確認 (no-split threshold・重複排除) が完了している。
- `component-inventory.json` の全 component が quality_gates/harness_coverage block を持つ。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **qa ゲート**: 個別テストの合否 (P06/P07) とは別に、品質機構 (lint/review/evaluator) 一式が設計として揃っているかを確認するゲート。

## 成果物
- **C01/C03 (skill) quality_gates 確認**: p0_lint (lint-skill-name/lint-skill-description/lint-skill-tree/validate-frontmatter/lint-dependency-direction/lint-skill-dep-step7/lint-forbidden-deps/lint-manifest-contents) が既存 skill-intake の lint 網羅と一致することを確認。
- **C02/C04 (script) quality_gates 確認**: p0_lint (lint-script-frontmatter) + build_trace + elegant_review (no_contradiction/no_missing/consistent/dependency_integrity) + content_review + evaluator (threshold=80, high_max=0) が宣言されていることを確認。
- **harness_coverage 確認**: 全 component が `min: 80` を要件として持ち、現状の skill-intake の実測未達値 (もしあれば) を component エントリへ焼いていないことを確認。C02 の `kind_pass` が contamination check 追加後も `content-review-verdict+coverage+contamination-check` として整合していることを確認する (goal-spec C7)。
- **feedback_contract 拡張確認**: C01 の `feedback_contract.criteria` が IN2 (contamination check 非検出, verify_by=script) / OUT2 (相手固有の具体性, verify_by=elegant-review) を goal-spec C7/C8 に対応する形で保持していることを確認する。

## スコープ外
- 実際の lint/evaluator 実行そのもの (build 後に build 側パイプラインが実施)。
- 新規品質機構の追加 (既存 skill-intake の quality_gates 規約をそのまま継承し、新規発明はしない)。

## 完了チェックリスト
- [ ] C01-C04 の全てが quality_gates (p0_lint/build_trace/elegant_review/content_review/evaluator) を kind 別契約で持つ。
- [ ] C01-C04 の全てが harness_coverage (min≥80/kind_pass) を持ち、現状未達数値を焼いていない。
- [ ] `check-spec-gates.py` が想定する値域 (p0_lint 網羅/elegant_review の4条件/evaluator threshold=80,high_max=0) を満たす。

## 参照情報
- `plugin-plans/skill-intake/component-inventory.json` (quality_gates/harness_coverage の正本)。
- `skills/run-plugin-dev-plan/references/harness-creator-spec-reflection.md` (焼き先マトリクス)。
- 後続 P10 (最終レビューゲート)。
