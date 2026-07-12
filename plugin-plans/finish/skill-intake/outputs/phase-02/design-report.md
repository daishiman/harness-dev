# Phase 02 — 設計レポート

## スキーマ設計 (additive・後方互換)

### `skills/run-intake-interview/schemas/output.schema.json`
- `procedure` を properties に追加 (**required には入れない**=既存 fixture 非破壊)。
- `allOf` if/then で mode 別要件を宣言:
  - `mode=detailed` → `steps` minItems 1、各要素 action/input/output/tool/frequency。
  - `mode=overview_fallback` → `difficulty_flag const true` + `overview` (step_count_estimate/participants/frequency)。

### `references/intake.schema.json`
- `$defs/procedure`, `$defs/validation_block` (procedure_completeness: complete/mode/missing/contamination) を新設。
- `sections.6_five_axes_summary.procedure` と root `validation` へ `$ref`。
- 既存 fixture への回帰は無し (検証済: 既存エラーは pre-existing な notion_target のみ、procedure 由来 0)。

## 決定論分岐設計 (C2)

`validate-answer-abstraction.py` を `axis=procedure` へ拡張。空/未回答フレーズ (`UNANSWERED_PATTERNS`) を検出したら abstract=True かつ unanswered=True。**2 連続**の abstract/unanswered で `overview_fallback` へ切替。同一入力→同一経路の決定論を保証 (LLM 判断を介在させない)。

## contamination 語彙設計 (C7)

新 reference `to-be-vocabulary-patterns.md` を正本とし 3 層で機械パース:
- **強シグナル**: 単独出現で混入 (べきである/理想は/本来は/一般的には 等)。
- **弱シグナル**: 名詞的用法は as-is、当為表現との共起でのみ混入 (最適化/効率化/自動化 等)。
- **当為表現**: 弱シグナルの近傍共起語。

名詞的用法 (例:「在庫最適化ツールを毎日使う」) は `detected=false` のまま `warn` 記録 (誤検知の透明化)。

## dual-gate 設計 (C3)

`quality_gate.py` に `check_procedure_gate(intake, require_procedure=False)` を追加。true_purpose は **2 経路** (`sections.3.true_purpose` OR `sections.6.axes[real_problem].answer`) から抽出 (dual-source 冗長性)。procedure 非認識 intake には `migration_warn` を返し**既存 45 テストを緑維持** (fail-closed でなく後方互換ゲート)。

## 設計判断: migration_warn パターン

計画の「fail-closed」記述と既存コードの後方互換要件が衝突。procedure 軸を持つ intake のみゲートを発火させる `_procedure_aware` 述語を導入し、既存 v1 intake は警告のみに降格することで両立させた。
