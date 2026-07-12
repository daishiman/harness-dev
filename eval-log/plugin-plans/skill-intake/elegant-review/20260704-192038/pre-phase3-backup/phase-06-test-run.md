---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
後段 build (`run-skill-create`/`plugin-scaffold`) が P05 の実装仕様に基づき C01-C04 を実装した後、P04 で設計した受入テストケース (C1/C2/C3/C6/C7) を実行し、tdd-red から tdd-green への遷移を確認する (本 plan 内では「実行手順の宣言」までを成果物とする)。

## 背景
本 plan は実装を含まないため、本 phase 自体もテストコードの実行結果を持たない。代わりに「build 後どのテストをどの順序・どの入力データで実行すべきか」という実行手順を宣言し、build 側 (実装者) がそのまま再現できるようにする。

## 前提条件
- P05 の実装仕様に基づく実装が build 側で完了している (本 plan のスコープ外・build 側の前提)。
- P04 のテストケース仕様が確定している。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。

## 成果物
- **実行手順の宣言**: (1) `validate-procedure-completeness.py` (C02) の純粋ロジック単体テスト (detailed 完全/不完全/overview_fallback 完全/不完全の 4 ケース + handoff 対象 as-is フィールドへの to-be 語彙混入あり/なしの 2 ケース、exit code 検証、goal-spec C7)。(2) `run-intake-interview` (C01) の procedure 軸ヒアリングの受入テスト (詳細発話入力→`interview.json.procedure` validate PASS、抽象回答 2 連続入力→`overview_fallback` 切替)。(3) `run-intake-finalize` (C03) の統合テスト (Phase1-8 成果物一式を入力し `intake.json.sections.6_five_axes_summary.procedure` と `intake.json.validation.procedure_completeness` に procedure+検証結果が格納され、contamination が無いことを確認)。(4) `quality_gate.py` (C04) 拡張の受入テスト (purpose/procedure 片方欠落 → exit 1、`validation.procedure_completeness.contamination.detected=true` → exit 1、両方非空かつ contamination なし → exit 0)。
- 実行順序: C02 純粋ロジック単体テストは依存をモックして先行実行してよい。統合順序は依存 DAG に従い C01 受入テスト → C02 実データ検証 → C03 統合テスト → C04 gate テストとする。

## スコープ外
- 実際のテスト実行そのもの (build 環境が無いため本 plan では実行しない。実行は後段 build のパイプラインが担う)。
- CI 配線 (governance-check ワークフローへの追加は本 plan のスコープ外、既存 CI がそのまま拾う)。

## 完了チェックリスト
- [ ] C01-C04 それぞれについて実行すべきテストケースと実行順序が宣言されている。
- [ ] 各テストケースの合格基準 (exit code / JSON フィールド値) が観測可能な形で明記されている。

## 参照情報
- P04 (テストケース設計)。
- P05 (実装仕様)。
- 後続 P07 (テスト結果を goal-spec checklist へ RTM としてマッピングする)。
