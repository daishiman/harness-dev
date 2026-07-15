---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入判定)

## 目的
P06 の実測結果を goal-spec の checklist C1-C6 と各 component の feedback_contract.criteria に照らして受入可否を判定する。全 component が受入基準を満たすことを以て P08 (改善) 以降へ進める。

## 背景
checklist C1(完全diff)・C2(4軸+semantics独立再検査)・C3(監査/承認済み限定apply)・C4(applied_verified/no-changeだけclose可)・C5(Issue #17 fixture matrix)・C6(既存検知との非重複)を実測と突合する。

## 前提条件
- P06 の実測結果 (テストログ・カバレッジ・precision/recall) が揃っている。
- goal-spec.json の checklist C1-C6 を参照できる。

## ドメイン知識
- C1→C11+C08、C2→C09+C01+C03、C3→C02+C04+C06、C4→C10+C07、C5→EVALS、C6→C05/C06+handoffで判定する。C03/C04 verdict未配線、proposal-only close可、truncated history受理はいずれも即不合格。
- 一部でも未達の checklist 項目があれば P08 で改善対象として持ち越す。

## 成果物
- checklist C1-C6 ごとの受入判定結果 (合格/要改善)。
- 要改善項目がある場合の P08 への申し送り事項。

## スコープ外
- 改善作業そのもの (P08 の責務)。
- 最終品質保証 (P09 の責務)。

## 完了チェックリスト
- [ ] checklist C1-C6 の全項目について対応する component の実測結果との突合が完了している。
- [ ] 未達項目がある場合、具体的な component id と不足内容が明記されている。
- [ ] C6 (既存責務との非重複) が `handoff-run-plugin-dev-plan.json` の記述と整合していることが確認されている。

## 参照情報
- `goal-spec.json` (checklist C1-C6)。
- `component-inventory.json` / P06 実測結果。
- 後続 P08 (要改善項目の改善)。
