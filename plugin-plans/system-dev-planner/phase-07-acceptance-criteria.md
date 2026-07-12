---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
goal-spec `purpose` (「system-spec-harness の確定成果物から task-spec + task-graph が implementation_readiness を満たして確定した状態」) 由来の受入観点を index.md の受入確認表へ焼く。

## 背景
system-dev-planner の受入は 2 層に分かれる: (1) system-dev-planner 自体 (本 plan の component 群) の受入と、(2) system-dev-planner が生成する task-spec/task-graph の受入 (C02/C05 が担う 4 条件=矛盾なし/漏れなし/整合性あり/依存関係整合)。本フェーズは (1) を確定し、(2) は index の受入確認表へ C02/C05 の責務として記載する。

## 前提条件
- P06 の harness coverage 実測が完了している。

## ドメイン知識
- 受入は「契約として焼く」だけで実行は build 後 (run-skill-create の harness criteria-test)。purpose の正本は `goal-spec.purpose`。
- C01 の OUT1 (implementation_readiness=complete の入力から生成した task-spec/task-graph が dev-graph 登録形式で全件検証可能) が受入テストで確認される。
- C09/C10/C11 (repo containment・冪等 init・atomic promotion) の受入は index.md 受入確認表の multi-repo isolation / no-overwrite init / partial-publish 拒否の各行として C01 OUT2 と併記される。
- C12 (validate-system-plan.py) の validation report は C11 promotion gate2 の判定入力であり、partial-publish 拒否行の前提として受入確認表に紐づく。

## 成果物
- index.md 受入確認表確定 (受入観点 / 確認の見方 / 焼き先の対応表)。

## スコープ外
- リファクタリング (P08)。

## 完了チェックリスト
- [ ] 受入観点表が purpose 語彙から導出され build 後確認プロセスと紐づいている。
- [ ] system-dev-planner 生成物側の 4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) が C02/C05 の責務として受入確認表に記載されている。
- [ ] promoted N task registrationがtracker binding/publication intent、empty linkage/execution、in-progress completion、one-task-one-branch/worktree leaseを持ち、all-or-none receiptのcount/exact-set一致後だけmutation/reconciliationをdev-graphへ委譲すると判定できる。

## 参照情報
- index.md 受入確認章。
- 対象 component C01-C12。
- 後続 P08 (refactoring)。
