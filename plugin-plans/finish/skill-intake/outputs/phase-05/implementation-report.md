# Phase 05 — 実装レポート (TDD Green)

Phase 04 のテストを Green にする実コードを `plugins/skill-intake/` へ実装した。

## 新規ファイル

- `scripts/validate-procedure-completeness.py` (C02)
  - `parse_patterns` (3 バケット) / `extract_procedure` (interview・intake 両形式) / `extract_true_problem` / `check_completeness` (mode 別) / `check_contamination` (強単独 / 弱+当為 / 名詞 warn) / `run` / `main`。
  - argv `--interview FILE --patterns`。exit 0=complete&clean / 1=incomplete or contaminated / 2=usage。
  - 語彙正本欠落時の `DEFAULT_STRONG/WEAK/MODAL` フォールバック内蔵。
- `skills/run-intake-interview/references/to-be-vocabulary-patterns.md` (C02 が機械パースする語彙正本)。

## 拡張ファイル

- `scripts/quality_gate.py` (C04): `_extract_true_purpose` (dual-source) / `_extract_procedure` / `_procedure_aware` / `check_procedure_gate(require_procedure=False)`。`gate()` に `require_procedure` を追加し `procedure_gate` を checks へ。`--require-procedure` フラグ。
- `skills/run-intake-interview/schemas/output.schema.json`: procedure (additive) + allOf if/then。
- `references/intake.schema.json`: `$defs/procedure` / `$defs/validation_block` / section・root への `$ref`。
- `skills/run-intake-interview/scripts/validate-answer-abstraction.py`: `UNANSWERED_PATTERNS` / `judge(answer, ..., axis)` で axis=procedure の未回答検出。
- `skills/run-intake-interview/scripts/build-sheet-json.py`: `extract_procedure(sheet_text)` (`## 現状手順` → json fence) を追加し payload へ additive 出力。
- `skills/run-intake-interview/references/question-plan.json`: `procedure_axis` ブロック (axis_order 非追加=5 軸ループ非破壊)。

## 実装上の判断

- **additive 徹底**: procedure は required に入れず、既存 v1/v2 intake を非破壊。
- **dual-source purpose 抽出**: v1 (`5_axes`) と v2 (`sections.*`) の格納位置差を吸収。
- **migration_warn**: procedure 非認識 intake はゲート降格し既存 45 quality_gate テストを緑維持。
