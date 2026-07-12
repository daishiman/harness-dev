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

# P08 — refactoring (リファクタリング・TDD Refactor)

## 目的
P07 で受入基準を満たした実装 (build 後) に対し、テストを green に保ったまま重複除去・命名整理・SSOT 一本化の観点でリファクタリングの要否を判定する。

## 背景
C1/C2 は既存関数へのシグネチャ拡張であるため、新チェック (R) / 新ヘルパー (`_load_inventory_components` 等) が既存の類似ロジック (`_check_inventory_provenance` 等) と重複していないかを確認する必要がある。C3 は新規 script であり、既存 15 本の script_refs との命名・構造整合を確認する。C6/C7/C10/C11 の新規 2 script (`check-generative-fidelity.py`/`check-downstream-harness.py`) も同様に既存 script 群との重複・命名整合を確認する。C8/C12 は R1-evaluate.md/plan-rubric.json への追記であり、既存 S1/S2 semantic_checks パターンとの整合を確認する。なお本 phase の `entities_covered=[]` は意図的である: リファクタリングは特定 component の build_target を直接読み書き/検証するのではなく、C01/C02 双方に跨る重複除去・命名整合・SSOT 一本化という component 非依存の横断観点を扱うため、index の付与規則 (build_target を直接扱う phase のみ id を持つ) に従い空とする (P05/P09 が同型作業でも [C01,C02] を持つのは、それらが特定 component の build_target を直接生成/検証する phase であるのと対照的)。

## 前提条件
- P07 の受入判定が PASS している。

## ドメイン知識
- **重複除去観点**: `_load_inventory_components` (C2 新設) と既存 `_check_inventory_provenance` の component 読み込みロジックが重複した場合、共通ヘルパーへ一本化する (ただし P02 の設計判断で意図的に独立実装とした理由=既存関数への副作用リスク回避が優先される場合はこの限りでない)。
- **SSOT 一本化観点**: `lint-ssot-duplication.py` (F7) の DUP-PASSAGE 検出が新規/拡張コードに対して warn を出す場合、リファクタリングで解消するか意図的な例外として記録する。
- **C6/C7/C10/C11 の重複除去観点**: `check-generative-fidelity.py` の phase 本文走査ロジックと `check-downstream-harness.py` のサブ節検出ロジックが、いずれも specfm.py の `_PHASE_SECTION_HINT`/Markdown パーサに依存するため、走査ヘルパーの共通化余地を確認する (ただし 2 script は検出対象の性質が異なる=語彙検出 vs 見出し検出のため、無理な統合はしない判断も許容する)。
- **C8/C12 の重複除去観点**: `plan-rubric.json` の `semantic_checks` へ追加する S3/S4 エントリが既存 S1/S2 と同型のフィールド構造 (id/text/runner) を持ち、フィールド追加のバラつきが無いことを確認する。

## 成果物
- リファクタリング実施記録 (実施した場合の差分概要、実施不要と判定した場合はその根拠)。

## スコープ外
- 新規機能追加 (本 phase はリファクタリングのみ・機能追加は goal-spec のスコープ外)。

## 完了チェックリスト
- [ ] `_load_inventory_components` と既存 `_check_inventory_provenance` の重複有無を確認した。
- [ ] `lint-ssot-duplication.py` の DUP-PASSAGE warn 有無を確認した。
- [ ] `check-generative-fidelity.py`/`check-downstream-harness.py` と既存 script 群の走査ロジック重複有無を確認した (C6/C7/C10/C11)。
- [ ] `plan-rubric.json` の semantic_checks (S3/S4) が既存 S1/S2 と同型フィールド構造であることを確認した (C8/C12)。
- [ ] リファクタリング実施後もテスト全件が green のままである (P06 のベースラインを下回らない)。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 各重複除去観点について「重複あり→一本化した」または「重複なし/意図的独立実装→根拠付きで維持」のいずれかが明示的に記録される。
- 満たさない例: リファクタリングの要否判定を行わず「問題なし」とだけ記録して次フェーズへ進む。

### 事前解決済み判断
- 分岐点: `check-generative-fidelity.py` と `check-downstream-harness.py` の走査ヘルパーを共通化するか → 判断: 検出対象の性質 (語彙一致 vs 見出し構造検出) が異なるため無理な統合はせず、`_PHASE_SECTION_HINT` 依存部分のみ共有し検出ロジック本体は独立に保つ (過度な抽象化による可読性低下を避ける)。

## 参照情報
- `phase-07-acceptance-criteria.md`。
- `plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py` (`_PHASE_SECTION_HINT`)。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/schemas/plan-rubric.json`。
- 後続 P09 (quality-assurance)。
