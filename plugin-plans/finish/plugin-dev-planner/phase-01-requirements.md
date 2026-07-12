---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
plugin-dev-planner 自身に残る 3 つの機械検証可能性の残債 (target_plugin_slug 未束縛 / entry_points 未突合 / harness-coverage 自己適用ギャップ、C1-C3) に加え、(層A: C6-C9) 生成される phase 本文の曖昧語彙・未カスタマイズを機械検出し下流実行着手可能な具体度を genuine 判定する仕組みと、(層B: C10-C12) 各 phase 本文が下流 builder の受入例・事前解決済み判断を内包しハーネスとして実効性を持つかを機械検出+genuine 判定する仕組みを、観測可能な完了条件として `goal-spec.json` に固定する。

## 背景
plugin-dev-planner は過去 3 回の elegant-review (2026-06-30/07-02/07-04) で 4 条件 PASS 済みであり、harness-creator-spec-reflection.md の 46 行マトリクスも反映済/含意済/意図的除外で完全性証明済みである。一方で直近の再現性レビューが 3 つの未解消 residual (MEDIUM-3/MEDIUM-4/dogfooding F1) を明示した。これはゼロベースの再構築ではなく、既存 skill の機械ゲートを狭く強化する改修である。さらにユーザーの外側ループ指示により、機械ゲート全緑だけでは (層A) 生成される phase 本文が汎用テンプレ埋めのまま残り、(層B) 仕様書自体が下流構築者にとって実質的なハーネスとして機能しない余地が二重に残る (「緑のパラドクス」) ことが判明したため、この 2 層を本計画のスコープへ追加する。

## 前提条件
- goal-spec.json の schema (`schemas/plugin-goal-spec.schema.json`) と `check-plugin-goal-spec.py` による検証が利用できる。
- `artifact_class: existing-plugin-update` かつ `target_plugin_slug: plugin-dev-planner` (自己参照計画) であることを前提とする。

## ドメイン知識
- 要件の正本は `goal-spec.checklist` (C1-C12) であり、後続の全フェーズはその被覆でしかない (spec-first)。
- C1/C2/C3 は「機械検証可能化」であって新機能追加ではない。既存の check-runtime-portability.py / check-build-handoff.py / governance-check.yml の検査範囲を狭く拡張する。
- C4/C5/C9 は退行防止条件 (既存テスト・46 行マトリクス整合・既存決定論ゲート全本の green 維持) であり、C1-C3/C6-C8/C10-C11 の実装が既存契約を破壊しないことを保証する。
- **層A (C6-C8・生成時精度)**: C6 (曖昧語彙 denylist 検出) と C7 (`_PHASE_SECTION_HINT` 完全一致=未カスタマイズ検出) は機械層に留め、意味の正否 (具体性が真に課題解決に資するか) の最終判定は fork evaluator (C8) の意味評価に委ねる (二層分離・Goodhart 回避・既存 anti-goodhart INVARIANTS を維持)。
- **層B (C10-C12・仕様書=下流ハーネス)**: C10 (受入例の存在検出) と C11 (事前解決済み判断の存在検出) は機械層に留め、実効性 (下流実行者が追加質問なく構築に着手できるか) の genuine 判定は fork evaluator (C12) に委ねる。受入例の「数」や「語数」を Goodhart 指標化しない。

## 成果物
- `goal-spec.json` (purpose/background/goal/artifact_class/target_plugin_slug/checklist(C1-C12)/constraints/handoff_targets/max_loops/open_questions を含む・確定済み)。

## スコープ外
- C1/C2/C3 の具体的な実装方式の確定 (R2/R3 = P02 以降の設計判断に委ねる)。
- harness-creator 側の残債 (envelope 生成器の executor 化) — constraints により本 goal のスコープ外。
- 空 component 退化防止の機械ゲート新設 — 既存 evaluator 層で担保する二層分離境界として本 goal では対象外。

## 完了チェックリスト
- [ ] goal-spec.json が `check-plugin-goal-spec.py` で exit0 検証済みである。
- [ ] checklist の C1-C12 各項目が id/criterion/done/verify_by を備えている。
- [ ] constraints (harness-creator 側残債除外・実装方式は R2/R3 委譲・空 component 境界維持・改名 churn 除外・C6/C7 は機械層に留め意味判定は C8 に委ねる・C10/C11 の埋め込み形式は R2/R3 委譲) が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `goal-spec.checklist` に C1-C12 の 12 項目全てが id/criterion/done/verify_by を備えて存在し、`check-plugin-goal-spec.py` が exit0 で検証済みである。
- 満たさない例: checklist に一部の id (例: C6-C12) が欠落している、または verify_by が省略されたまま `check-plugin-goal-spec.py` が未実行のまま次フェーズへ進む。

### 事前解決済み判断
- 分岐点: 層B (C10/C11 の受入例・事前解決済み判断) を 13 phase 全てに一律要求するか、判定行為中心の gate 系 phase (P03/P07/P09/P10) は縮小要件にするか → 判断: gate 系 4 phase は縮小要件 (判定記録そのものが受入例的性質を持つため)、他 9 phase はフル要件とする (根拠は phase-02-design.md に記録)。
- 分岐点: 曖昧語彙 denylist の一致判定を完全一致とするか部分一致まで広げるか → 判断: 部分文字列一致を採用する (日本語は分かち書きされないため。具体的な denylist 語彙集合は phase-02-design.md に記録)。

## 参照情報
- `plugin-plans/plugin-dev-planner/goal-spec.json`。
- `schemas/plugin-goal-spec.schema.json`。
- 後続 P02 (design)。
