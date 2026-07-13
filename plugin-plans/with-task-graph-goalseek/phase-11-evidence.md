---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: 
---

# P11 — evidence (検証)

## 目的
11 決定論ゲートの実行ログを evidence として保全し、goal-spec checklist C11 の実測裏付けを固定化する。

## 背景
「exit0 になった」という主張は再現可能な実行ログを伴わなければ検証不能である。本 phase は実行コマンドと実際の stdout/exit code を記録として残す。

## 前提条件
Phase10 最終レビュー完了。

## ドメイン知識
(引用)index.md ## ゲート一覧(11 本・core5/拡張6 内訳)。差分なし。

## 成果物
11 ゲート(`verify-index-topsort.py` / `detect-unassigned.py` / `check-spec-frontmatter.py` / `check-spec-gates.py` / `validate-task-graph.py` / `check-spec-matrix-coverage.py --self-test` / `check-spec-matrix-coverage.py` / `check-surface-inventory.py` / `check-build-handoff.py` / `check-requirements-coverage.py` / `check-runtime-portability.py`)の実行コマンドと exit code の記録(index.md ## ゲート一覧の evaluator gate id G1-G11 と 1:1 対応)。

## スコープ外
ゲート実装自体の変更(evidence 記録のみを扱う)。

## 完了チェックリスト
- [ ] 11 ゲート全ての実行コマンドと exit0 結果が記録されている

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 11 ゲート全ての実行コマンド全文 + 実際の exit code が記録され、`validate-task-graph.py` の実行ログに検査対象 `task-graph.json` のパスと violation 0 件(no output)が明記される。
- 満たさない例: 「全ゲート exit0 だった」という結論のみが記され、個別コマンドや stdout/stderr の実出力が記録されない。

### 事前解決済み判断
- 分岐点: evidence 記録の形式(生ログ全文 vs サマリのみ)→ 判断: 各ゲートについてコマンド全文 + exit code + violation 有無(0 件なら「no output」)を記録し、後続監査者が再実行なしに結果を検証できる粒度にする(FAIL-1/2/3 の finalize 反復自体もこの粒度の evidence として本 phase へ引き継ぐ)。

## 参照情報
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/`(11 ゲート実体)
