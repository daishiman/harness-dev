---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビューゲート)

## 目的
P01-P09 の全成果物 (ギャップ分析・設計・レビュー・テスト設計・実装仕様・テスト実行手順・RTM・リファクタリング確認・QA) を、P02/P03 の設計者とは別 context の approver が最終的に独立レビューし、goal-spec C1-C8 全項目が過不足なく操作化されていることを最終確認する (proposer≠approver)。

## 背景
本 plan の環境ポリシーは最終レビューを提案者と別 context の approver が承認することを要求する。final-gate は P03 (design-gate) と異なり、設計だけでなく実装仕様・テスト・RTM・QA まで含めた全成果物の一貫性を対象とする最後のゲートである。

## 前提条件
- P09 の QA ゲートが PASS している。
- P01-P09 の全成果物 (13 phase 中 9 phase 分) が確定している。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **final-gate**: 本 plan で 2 番目 (最後) の合否ゲート。不合格時は該当 phase (P02/P05 等) へ差し戻す。

## 成果物
- 独立 approver によるレビュー結果 (PASS/FAIL) と、レビュー観点別チェック結果:
  - RTM (P07) が goal-spec checklist C1-C8 の全項目を過不足なくカバーしているか。
  - 実装仕様 (P05) が P04 のテストケースを満たす設計になっているか。
  - `component-inventory.json` の quality_gates/harness_coverage が現状未達数値を焼いていないか (P09 確認の再検証)。
  - 本 plan 全体が「downstream builder 向け仕様」の原則を逸脱し実コード改修を含んでいないか。
  - as-is/to-be フィールド分離 (to-be 専用フィールド非新設 + contamination check, C7) と相手固有の具体性を促す質問設計 (C8) が、ヒアリング段階で to-be 設計を行わない goal-spec constraints と矛盾なく操作化されているか。

## スコープ外
- 内容の再設計 (FAIL 時は該当 phase へ差し戻し、本 phase 自体では再設計を行わない)。
- build 後の実際の受入テスト実行 (P11 evidence の責務)。

## 完了チェックリスト
- [ ] レビュー担当が P02/P03 の担当者と別 context である (proposer≠approver)。
- [ ] goal-spec C1-C8 の全項目が最終的に過不足なくカバーされていることを確認した。
- [ ] gate_type=final-gate の合否判定 (PASS/FAIL) が記録されている。

## 参照情報
- P07 (RTM、レビュー対象)。
- P09 (QA 確認結果、レビュー対象)。
- 後続 P11 (PASS 確定後、手動 trial による証跡収集へ進む)。
