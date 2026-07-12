---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 完了
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09]
applicability:
  applicable: true
  reason:
---

# P09 — quality-assurance (品質)

## 目的
全9 component の quality_gates (p0_lint/build_trace/elegant_review/content_review/evaluator) と harness_coverage (min80/kind_pass) が値域検証 (check-spec-gates.py) を通過する状態を確認する。

## 背景
harness_coverage.kind_pass の判定基準は kind によって異なる (skill run は "loop=criteria-test+content-review-verdict" 系トークン、sub-agent/script は "content-review-verdict" 系トークン) ため、component kind ごとの整合確認が必要。

## 前提条件
P02-P08 が完了していること。

## ドメイン知識
expected_kind_pass_tokens/kind_pass_ok (specfm.py) が定義する kind 別トークン集合。

## 成果物
check-spec-gates.py の実行結果 (exit0)。

## スコープ外
なし (全 component が対象)。

## 完了チェックリスト
- [ ] 9 component 全ての quality_gates.evaluator.threshold >= 80 かつ high_max = 0
- [ ] harness_coverage.min が全 component で80以上

## 参照情報
component-inventory.json、scripts/check-spec-gates.py
