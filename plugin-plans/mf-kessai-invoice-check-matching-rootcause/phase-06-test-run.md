---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: 
---

# P06 — test-run (テスト)

## 目的
harness coverage (≥80%・component_kind 別 kind_pass) を C01-C07 全 7 component へ拡充確定し、確定6要因根治 (C1 収集拡張/C2 R1決定論化/C3 NEW・年契約分類/C4 取消継続性/C5 代理店collapse/C6 顧客ID結合) がテストで実測可能な状態にする。現状値 (実測 coverage%) は焼かず設計値のみを確定する。

## 背景
P04(test-design) で feedback_contract.criteria が test-first で導出され、P05(implementation) で build 委譲経路 (routes) が確定した後、本フェーズは旧「テスト実行 (vitest 80%)」の精神を pytest harness-coverage ≥80% (6 種別×二軸・kind 別パス) へ transform する (phase-lifecycle.md §7 P6行)。

## 前提条件
component-inventory.json の C01-C07 が build_target/quality_gates/depends_on 確定済み (P02-P05 由来)。goal-spec.json checklist C1-C13 (特に verify_by=test の C1/C2/C4-C7/C9-C12) が harness coverage の受入観点として存在すること。

## ドメイン知識
kind_pass 契約は component_kind 別に異なる (io-contract.md §9 kind→必須キー表): C01-C05 (script) は `kind_pass: content-review-verdict+coverage`、C06 (sub-agent) は `kind_pass: content-review-verdict+verdict`、C07 (skill loop) は `kind_pass: loop=criteria-test+content-review-verdict`。tests_min:80 は C01-C05 各 script の CLI self-test/pytest カバレッジ下限 (component-inventory.json 記載値)。

## 成果物
C01-C07 各 component の `harness_coverage` ブロック (`min: 80` 以上・kind_pass が component_kind と整合) が component-inventory.json へ確定した状態。

## スコープ外
実テストコードの記述・実行 (pytest 実走・coverage 計測) は `run-skill-create`/`run-build-skill` (L4 build) へ委譲する。本フェーズは harness_coverage 設計の確定に留まる。

## 完了チェックリスト
- [ ] C01-C07 全ての `harness_coverage.min` が 80 以上である
- [ ] kind_pass が component_kind と整合する (script→content-review-verdict+coverage、sub-agent→content-review-verdict+verdict、skill→loop=criteria-test+content-review-verdict)
- [ ] 現状値 (実測 coverage%) を焼いていない (設計値のみ)

## 参照情報
component-inventory.json (harness_coverage ブロック SSOT) / io-contract.md §10 (harness-coverage 検証) / phase-lifecycle.md §8 P06 セル / index.md ## ドメイン知識 (用語集は差分のみ・本節で足りる)
