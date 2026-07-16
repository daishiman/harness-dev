---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (改善 / tdd-refactor)

## 目的
P07 で未達・要改善と判定された component の実装を、criteria の green 状態を維持したまま改善する (tdd-refactor)。

## 背景
tdd サイクル (red→green→refactor) の最終段として、P06/P07 で判明した精度不足 (precision/recall) や決定論 script のカバレッジ不足、独立検証 sub-agent の監査観点漏れなどを、既存テストを壊さずに改善する。本 plan は L3 (plan) 止まりのため、本 phase の成果物は「改善方針・差分計画」であり実コードの改善作業自体は下流 build フェーズが担う。

## 前提条件
- P07 の受入判定結果 (要改善項目一覧) が確定している。
- 改善対象の criteria/EVALS 閾値 (precision/recall≥80、tests_min≥80) が変更されないこと (基準を緩めて帳尻を合わせない)。

## ドメイン知識
- refactor は「基準を満たすまで実装を直す」フェーズであり、「基準自体を下げる」フェーズではない。criteria/EVALS 閾値の変更は本 phase の責務外。
- 共有script (C11/C08/C09/C10) の改善はDAG下流(C01/C02/C03/C04/C06/C07)へ波及するため、task graphで到達する全消費者を再テストする。

## 成果物
- 要改善 component ごとの改善方針・差分計画 (該当 component が無ければ空)。
- 改善後に再実行が必要な下流 component の一覧。

## スコープ外
- criteria/EVALS 閾値そのものの変更 (基準緩和の禁止)。
- 最終品質保証・final-review (P09/P10 の責務)。

## 完了チェックリスト
- [ ] P07 で要改善と判定された component が (存在する場合) 全て改善方針を持つ。
- [ ] 改善によって criteria/EVALS の閾値 (precision/recall≥80、tests_min≥80) が変更されていないことが確認されている。
- [ ] 共有 script を改善した場合、その消費者 component の再テスト対象が明記されている。

## 参照情報
- P07 の要改善項目一覧。
- `component-inventory.json` (depends_on による影響範囲特定)。
- 後続 P09 (改善後の品質保証)。
