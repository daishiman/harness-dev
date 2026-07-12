---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 で確定した component 分解 (C01-C04)・依存 DAG・procedure スキーマ形状・決定論閾値・as-is 忠実性原則 (as-is/to-be 分離+具体性記録) の設計を、提案者 (P02 実行者) とは別 context の approver が独立レビューし、goal-spec C1-C8 の網羅性と DAG 非循環を確認した上で合否判定する (proposer≠approver)。

## 背景
本 plan の環境ポリシー (index `## 環境ポリシー`) は設計/最終レビューを提案者と別 context の approver が承認することを要求する。procedure 軸の追加は既存 skill-intake の中核ハンドオフ経路 (5 軸→intake.json→build) に影響するため、設計段階での独立検証が手戻りコストを最小化する。

## 前提条件
- P02 の成果物 (`component-inventory.json` 確定版、C01-C04 の component 定義・依存 DAG) が存在する。
- レビュー担当は P02 の設計判断を行った context とは独立した context (別 SubAgent または別セッション) である。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **design-gate**: 本 plan の 13 phase 中で唯一 P02 直後に置かれる合否ゲート。不合格時は P02 へ差し戻す (`goal-spec.max_loops=5` を上限に反復)。

## 成果物
- 独立レビュー結果 (PASS/FAIL) と、FAIL の場合の differential findings (P02 への差し戻し事項)。
- レビュー観点チェック結果: (1) goal-spec C1-C8 が component-inventory の component/checklist/feedback_contract に過不足なく反映されているか (C7/C8 は IN2/OUT2 criterion と C02 contamination check として反映されているか)、(2) 依存 DAG (C01→C02→C03→C04) に循環が無いか、(3) 新規 sub-agent/slash-command/hook 非新設の根拠が妥当か、(4) plugin-level surfaces の required/omitted 判定に根拠が伴っているか、(5) to-be 専用フィールドを新設せず as-is フィールドへの混入検出のみで C7 を満たす設計が goal-spec constraints (ヒアリング段階で to-be 設計をしない) と整合しているか。

## スコープ外
- 設計内容自体の再設計 (FAIL 時は P02 へ差し戻し、本 phase では再設計を行わない)。
- 実装レビュー (P10 final-review の責務)。

## 完了チェックリスト
- [ ] レビュー担当が P02 の設計者と別 context である (proposer≠approver)。
- [ ] goal-spec C1-C8 の全項目が component-inventory 側で過不足なく反映されていることを確認した (C7/C8 を含む)。
- [ ] 依存 DAG (C01→C02→C03→C04) の非循環を確認した。
- [ ] gate_type=design-gate の合否判定 (PASS/FAIL) が記録されている。

## 参照情報
- `plugin-plans/skill-intake/component-inventory.json` (レビュー対象)。
- P02 (レビュー対象の設計成果物)。
- 後続 P04 (PASS 確定後、テスト設計へ進む)。
