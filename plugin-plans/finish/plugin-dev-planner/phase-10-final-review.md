---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビューゲート)

## 目的
P09 の品質保証結果を踏まえ、P03 (design-review) と同様に提案者とは別 context の approver が、C1-C12 全項目の達成・既存契約の非破壊・C3 配線先確定の妥当性・C6/C7/C10/C11 (機械層) と C8/C12 (意味層) の二層分離維持を最終承認する。

## 背景
proposer≠approver の環境ポリシーに従い、実装完了後の最終ゲートとして独立した承認を要求する。final-gate を通過して初めて P11 (evidence) 以降の完了プロセスへ進む。

## 前提条件
- P09 の品質保証が全項目 PASS している。
- P07 の受入基準判定が PASS している。

## ドメイン知識
- **最終承認基準**: (1) goal-spec.checklist C1-C12 全項目が done:true、(2) quality_gates/harness_coverage 全項目 PASS (C01/C02 双方)、(3) 既存テスト件数が退行していない (C9)、(4) C3 の governance-check.yml 編集 gap が open_issues に id 付き (GAP-GOVERNANCE-CI-001) で severity=blocking-release として起票され build 後の反映経路が明示されている、(5) C6/C7/C10/C11 が機械検出のみに留まり意味判定を兼ねていないこと・C8/C12 の genuine 判定が plan-findings.schema.json の conditions (C1-C4) を変更せず findings[] 新規 bucket に留まっていることを再確認した。
- **差し戻し条件**: いずれか未達の場合 P05 (implementation) または P08 (refactoring) へ差し戻す。

## 成果物
- 最終承認記録。

## スコープ外
- 新規要件の追加 (goal-spec.checklist の範囲外の変更は別 goal として扱う)。

## 完了チェックリスト
- [ ] goal-spec.checklist C1-C12 全項目が done:true であることを確認した。
- [ ] quality_gates/harness_coverage 全項目 PASS を C01/C02 双方で確認した。
- [ ] 既存テスト件数の退行が無いことを確認した (C9)。
- [ ] C6/C7/C10/C11 (機械層) と C8/C12 (意味層) の二層分離が維持されていることを確認した。
- [ ] 提案者と別 context の approver が最終承認した。

### 受入例 (満たす例 / 満たさない例・判定行為ゲート簡略形)
- 満たす例: 上記 5 判定基準の全てについて確認結果 (承認 or 具体的差し戻し理由) が本ファイルに記録される。
- 満たさない例: C1-C5 のみ確認し C6-C12 (層A/層B 拡張分) の確認を省略したまま承認する。

### 事前解決済み判断
- 分岐点: C8/C12 の genuine 判定結果に軽微な指摘 (critical でない改善余地) が残る場合の扱い → 判断: 承認自体はブロックせず open_issues へ改善余地として記録し、次回改訂の入力とする (critical な曖昧箇所指摘がある場合のみ差し戻し対象とする)。

## 参照情報
- `phase-09-quality-assurance.md`。
- `handoff-run-plugin-dev-plan.json` (open_issues)。
- 後続 P11 (evidence)。
