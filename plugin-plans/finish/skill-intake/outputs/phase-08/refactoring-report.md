# Phase 08 — リファクタリングレポート

Green を維持したまま重複排除と責務整理を行った。

## SSOT 集約

- **語彙正本の一本化**: to-be 判別語彙を `to-be-vocabulary-patterns.md` に集約し、C02 は機械パースで参照 (`DEFAULT_*` は fail-open 防止のフォールバックのみ)。判別基準の SSOT を reference 側に置き、コード内ハードコードを排除。
- **完全性判定の非重複**: procedure 完全性ロジックを C01 skill 内に重複実装せず C02 script に一本化。C01 (Phase4 完了ゲート) と C04/finalize (Phase9 ゲート) の両消費者が同一 script を参照 (no-split threshold 充足)。

## 抽出したヘルパ

- `quality_gate.py`: `_extract_true_purpose` / `_extract_procedure` / `_procedure_aware` に分解し、`check_procedure_gate` を単一責務の純関数化 (`{ok, violations}` or `{ok, migration_warn}` を返す)。
- `validate-answer-abstraction.py`: `_judge_abstract` を分離し `judge(..., axis)` へ集約。axis 別分岐を 1 箇所に局在化。

## 後方互換の保全

- procedure は schema の required 外 (additive)。
- migration_warn により既存 intake は非破壊。
- question-plan.json の procedure_axis は axis_order 非追加で 5 軸ループに影響なし。

## lint 確認

- `validate-frontmatter`: exit 0 (新規エラーなし。既存 run-skill-feedback warn のみ)。
- `lint-test-discovery-coverage`: orphan 0。
- build-questions は procedure_axis を無視 (5 軸のみ) — 既存挙動不変を確認。
