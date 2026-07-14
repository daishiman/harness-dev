---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
P04で設計したIssue #17完全fixture matrixに対し、P05で実装された全11 componentを実行してgreen/redの実測結果を得る。

## 背景
tdd-greenと実測を分ける。C11のfull-diff completeness/digest、C01/C03の4軸+semantics一致、C02/C04の提案・監査・承認・適用、C10/C07のproposal-only拒否を実測する。scriptはC08/C09/C10/C11の4件である。

## 前提条件
- P05 の実装が完了している。
- `EVALS.json` の既知正解セット (diff→影響フィールド) が利用可能である。

## ドメイン知識
- script (C08/C09/C10/C11) の tests_min=80 はカバレッジ%の実測要件である。
- loop skill (C01/C02) の outer criteria は test-run で precision/recall を実測し、EVALS.json の threshold (precision_min=80, recall_min=80) と突合する。
- sub-agent (C03/C04) は独立 context での監査結果 (見逃し/誤検出、反映漏れ/過剰変更の検出可否) を実測する。

## 成果物
- 各 component の実測結果 (テスト実行ログ・カバレッジ%・precision/recall%)。
- 未達 component のリストと差し戻し理由 (該当時のみ)。

## スコープ外
- 実測結果に基づく合否の最終判定 (P07 acceptance-criteria の責務)。
- リファクタリング (P08 の責務)。

## 完了チェックリスト
- [ ] C08/C09/C10/C11のテストカバレッジが80%以上で、Issue #17の945行完全diff digestと全source categoryが実測されている。
- [ ] C01/C02 の outer criteria が既知正解セットに対して precision/recall いずれも 80% 以上で実測されている。
- [ ] C03/C04 が独立 context で監査を実行し、少なくとも 1 件の合成された見逃し/誤検出/反映漏れ/過剰変更ケースを検出できることが確認されている。
- [ ] proposal-only/未承認/監査FAIL/hash driftは変更0件かつclose拒否、承認済みcaseはallowlist限定apply後にpost hash/validator一致、no-changeは独立verdict一致を確認している。

## 参照情報
- `EVALS.json` (C5 の既知正解セットと閾値定義)。
- `component-inventory.json` (harness_coverage.min=80 の契約値)。
- 後続 P07 (この実測結果を acceptance-criteria で判定する)。
