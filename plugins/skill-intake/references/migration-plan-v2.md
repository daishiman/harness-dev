# Migration Plan: section-templates.json (v1) → section_canonical_map.json (v2)

> **STATUS: COMPLETE (2026-05-22)** — v1 (`section-templates.json` / `apply_section_template.py` / `section_quality_check.py`) は本リリースで削除済み。正本は `intake-final-template.md.tmpl` + `intake-final-schema.json` + `section_canonical_map.json` (v2)。以下は履歴として保持。
>
> **削除予定: 2026-08-22** (COMPLETE から 90 日後)。それまでに `scripts/ci_dogfooding_retest.py` / `scripts/m3_deprecation_reverse_index.py` の本ファイル参照を除去すること。除去後は本ファイルを削除し、必要なら git tag (`migration-v2-complete`) から参照する。

## 1. 設計原則の転換

| 観点 | v1 (現状) | v2 (新正本) |
|---|---|---|
| 単一正本 | section-templates.json | **section_canonical_map.json** + **intake.schema.json** |
| 章定義 | 11セクション(混在:0/1/2/3/4/5/6/7/7.5/8/9/10) | **12セクション(§0〜§11、ユーザー正本に整合)** |
| purpose 表現 | `purpose_text: string` (絵文字頭付き) | `purpose_slots: {role_label, decides_what, ensures_what, prevents_what}` (4スロット階層・絵文字なし) |
| 可視化 | `viz_type: string` (1種固定) | `viz_slots: [{role, asset_id, mandatory}]` (配列・宣言的章別割当) |
| 検証 | section_quality_check.py の散文ルール | **JSON Schema Draft 2020-12** (intake.schema.json) で機械検証 |
| メタ集約 | SKILL.md / scripts に散在 | **runtime-config.json** に集約・変数参照 |
| knowledge_asset | §3.five_axes と §7.5 に二重正本 | **§6.axes[axis_id=knowledge_asset]** に集約 (DRY 解消) |
| 回帰検証 | 無し | **dogfooding_regression.py** (info-collector-agent baseline) |
| 公開前ガード | quality_gate.py のみ | **pre-publish-schema-validate hook** + quality_gate.py |

## 2. v1 → v2 セクションキー対応

`runtime-config.json#migration.rename_map` を参照。要点:

- `0_cover_meta` → 拡張して `0_executive_summary` (メタ + サマリ統合)
- `1_purpose` (§1) → `3_purpose_excavator` (§3 に移設)
- `3_five_axes` → `6_five_axes_summary` (位置変更 + knowledge_asset 統合)
- `7_5_knowledge_asset` → **廃止**、`6_five_axes_summary.axes[axis_id=knowledge_asset]` に $ref
- `5_expected_flow` → `4_option_presenter.scheduler` + `5_visualizer.fig3_pipeline` に分割
- `6_value_kpi` → `0_executive_summary.value_realized_score` + `10_self_updater.metrics` に分割
- `7_similar_skills` → `4_option_presenter.decision_tables[axis=責務境界]` に統合
- `9_next_action` → `9_handoff_contract` に改名・契約強化
- `10_appendix_vocabulary` → `2_user_profile.vocabulary_tier` + `section_canonical_map.policies` に分割

新規追加: `0_executive_summary`, `1_assumption_challenger`, `5_visualizer`, `7_design_decisions`, `9_handoff_contract`, `10_self_updater`, `11_artifact_index`。

## 3. 段階移行手順 (3ステップ)

### Step M1: 共存 (本セッションで実装済)
- `section_canonical_map.json` (v2) を新設
- `intake.schema.json` を新設
- `runtime-config.json` を新設
- `section-templates.json` (v1) は触らず温存
- render_notion_page.py は当面 v1 を読むが、`SECTION_CANONICAL_MAP_PATH` 環境変数があれば v2 にスイッチ

### Step M2: 切替 (次セッション、後続 dogfooding 後)
- `render_notion_page.py` / `section_quality_check.py` / 12 SubAgent を v2 参照に切替
- `section-templates.json` を `section-templates.v1.deprecated.json` にリネーム
- aggregator SKILL.md を v2 ベースで書き直し

### Step M3: 廃止 (回帰テスト1ヶ月 PASS 後)
- `section-templates.v1.deprecated.json` を削除
- 旧 quality_gate ルールを撤去

## 4. SubAgent 出力契約の v2 対応表

| 旧出力 | 新出力 (intake.schema.json $defs) | 担当 SubAgent |
|---|---|---|
| `cover_meta.*` | `executive_summary` (§0) | summarizer + handoff |
| `assumption.json` | `assumption_challenger` (§1) | assumption-challenger |
| `profile.json` | `user_profile` (§2) | user-profiler |
| `purpose.json` | `purpose_excavator` (§3) | purpose-excavator |
| `options.json` | `option_presenter` (§4) | option-presenter |
| `figures.md` | `visualizer.figures[]` (§5) | visualizer |
| `sheet.md` (5軸) | `five_axes_summary` (§6) | summarizer |
| (新規) | `design_decisions` (§7) | option-presenter |
| (intake.json 既存) | `open_questions` (§8) | handoff |
| (新規) | `handoff_contract` (§9) | next-action-advisor + handoff |
| `self-update.json` | `self_updater` (§10) | self-updater |
| (新規) | `artifact_index` (§11) | handoff |

## 5. 互換性ブリッジ (Step M1 期間限定)

`scripts/v1_to_v2_adapter.py` が必要 (本セッション後の実装)。
- v1 の `purpose_text` を 4 スロットへ自動分解 (LLM 補助 or 固定ルール)
- v1 の `viz_type: "mermaid_flowchart"` を `viz_slots: [{role:"primary", asset_id:"mtmpl-flowchart-lr"}]` に展開
- v1 の `7_5_knowledge_asset.*` を v2 の `6_five_axes_summary.axes[knowledge_asset]` にコピー

## 6. ロールバック条件

dogfooding_regression.py で **embedding_cosine < 0.85** が3回連続発生したら Step M2 を凍結し、原因究明する。
