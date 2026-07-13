---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
P05 の実装仕様と P11 の evidence 結果を反映し、goal-spec C5 (handoff-contract.md への procedure→build 参照契約追加) を含む文書更新仕様を確定する。

## 背景
procedure 軸の追加はヒアリング担当 (skill-intake) とハーネス構築担当 (`run-skill-create`/`run-plugin-dev-plan`) の間の情報連携契約であるため、コード変更だけでなく `references/handoff-contract.md`・README・CHANGELOG の更新が必須である。文書更新を怠ると goal-spec が解消しようとした「情報乖離による構築のやり直し」が文書レベルで再発する。

## 前提条件
- P05 の実装仕様 (schema/handoff-contract 差分内容) が確定している。
- P11 の evidence 結果が確定している。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。

## 成果物
- **`references/handoff-contract.md` (root, 正本) 更新仕様**: procedure 抽出結果 (`interview.json.procedure` / `intake.json.sections.6_five_axes_summary.procedure`) を build 時に参照する契約行を追加する。「purpose のみ参照し procedure を無視する既存経路」を残さない旨を明記する (goal-spec C5)。契約行には interview.json 側 `five_axes.rows[name="真の課題"]` ↔ intake.json 側 `axes[axis_id="real_problem"]` のフィールド対応 (変換は既存 render 経路が担い本改善で変更しない・対応表の正本は P02 ドメイン知識) を 1 行含める。`skills/run-skill-intake/references/handoff-contract.md` は pointer のまま変更しない (複製禁止 invariant)。
- **`plugins/skill-intake/README.md` 更新仕様**: 5 軸ヒアリングの説明に procedure 軸 (6 本目) の追加と、as-is 忠実性原則 (平均回帰禁止・相手固有の具体性・as-is/to-be 分離、goal-spec C7/C8) を追記する。
- **`plugins/skill-intake/CHANGELOG.md` 更新仕様**: 現行 version の PATCH bump (具体値の正本=P13) のエントリに procedure 軸追加・決定論フォールバック・purpose+procedure 両方ゲート・as-is/to-be 混入検証ゲート (C7)・相手固有の具体性記録指示 (C8) の 5 点を追記する。
- **`references/intake.schema.json` の変更履歴注記**: schema_version 2.0.0 のまま既存 `sections.6_five_axes_summary` に `procedure` property を追加し、root に任意 `validation.procedure_completeness` を追加する場合は後方互換 (additive) であることを明記する。13 番目 section は新設しない。
- **`references/to-be-vocabulary-patterns.md` (新規, run-intake-interview 配下) 文書化仕様**: 既存 `abstract-answer-patterns.md` と対の構成で、to-be 語彙パターン集 (べきである/理想は/最適化/より良い方法/一般的には 等) と contamination check (C02) からの参照方法を記述する (goal-spec C7)。名詞的用法 (業務名としての「最適化」等、ユーザー自身の as-is 業務語彙) と提案的用法 (「〜を最適化すべき」等の to-be 提案) の判別基準を含める (C02 false-positive escape の判定正本、C7 混入検出×C8 忠実記録の衝突回避)。

## スコープ外
- 実際のファイル編集の実行 (本 plan は仕様書であり、実編集は後段 build へ委譲)。
- Notion 公開ページのテンプレート変更 (goal-spec constraints によりスコープ外)。

## 完了チェックリスト
- [ ] `references/handoff-contract.md` (root) への procedure 参照契約追加内容が具体的に記述されている (goal-spec C5)。
- [ ] README/CHANGELOG の更新内容がバージョン番号とともに具体的に記述されている (C7/C8 の追記を含む)。
- [ ] `skills/run-skill-intake/references/handoff-contract.md` の pointer 構造 (複製禁止 invariant) を維持する旨が明記されている。
- [ ] `to-be-vocabulary-patterns.md` (新規) の文書化仕様が明記されている (goal-spec C7)。

## 参照情報
- `plugins/skill-intake/references/handoff-contract.md` / `plugins/skill-intake/skills/run-skill-intake/references/handoff-contract.md`。
- goal-spec C5/C7/C8。
- 後続 P13 (リリース: version bump と PR 化)。
