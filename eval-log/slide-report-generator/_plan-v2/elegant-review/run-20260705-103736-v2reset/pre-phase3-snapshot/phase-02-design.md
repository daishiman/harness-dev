---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
既存 23 component (C01-C23) を温存しつつ、16 sub-agent 全件について「維持(maintain)」か「薄化(thin-adapter)」かを no-split threshold で判定し、薄化対象の手続き知識/rubric の委譲先 (delegation_target/extracted_reference) を確定する。3 skill (C01/C02/C03) には progressive disclosure (SKILL.md 残置範囲 + references_new + scripts_new) を設計し、新設 script C24 (lint-reference-attribution.py) で references 帰属を機械検証可能にする、N=24 component への分解フェーズ。

## 背景
P01 で確定した goal-spec を、実際に build 可能な再配置設計へ落とす最初の設計フェーズ。既存 build 済 plugin の component_kind/build_target/builder は変更せず(機能非破壊)、新たに `placement_scope`(全24component 明示)・`rebalance_disposition`・`rebalance_rationale`・`delegation_target`・`extracted_reference`(sub-agent)・`progressive_disclosure`(skill)の再配置区分フィールドを inventory へ追加する。意匠/技術層(vendor+schemas)は本設計の対象外(goal-spec C7)であり、agent⇔skill 間の情報配置境界のみを再設計する。

## 前提条件
- P01 の `goal-spec.json` と既存 `plugin-plans/slide-report-generator/component-inventory.json`(C01-C23 の温存対象値)が確定している。
- 16 sub-agent の実測行数(baseline cluster 328-342行 vs 過重 410-990行・measured_at=2026-07-05 09:31 JST)が要件フェーズで測定済み。
- 5 種の component_kind の写像規約(`references/component-domain.md`)と envelope 物理契約を参照できる。

## ドメイン知識
- no-split threshold の判定基準: baseline cluster (328-342行・hearing-facilitator/visual-strategist/report-composer/structure-validator/slide-renderer の5件) は抽出可能な汎用手続き知識の塊を持たないため maintain。それを超過する 11 件 (410-990行) は procedural knowledge/rubric が本文に直書きされ、委譲先 skill の references/ へ抽出することで分離便益(単一SSOT化・agent本文の elegant-review C1-C4 検証面積縮小)が分離コスト(参照 indirection)を上回るため thin-adapter とする。
- 委譲マッピングの不変条件: 11 thin-adapter agent は既存 depends_on 関係に基づき 1:1 で委譲先 skill を持つ(C01×9: structure-designer/d3-diagram-designer/data-visualizer/html-generator/layout-optimizer/ui-quality-reviewer/deck-evaluator/ai-image-diagram-producer/report-structure-designer、C02×1: slide-report-modifier、C03×1: cross-deck-reviewer)。
- 共有 script の hoist 拡張: 新設 C24 (lint-reference-attribution.py) は 3 skill (C01/C02/C03) 全てが consumers になる(depends_on へ追加)ため placement_scope=plugin-root で hoist する(既存 C23 と同一パターン)。
- references 帰属マップ再構成: 旧 resource-map.md (散文) を resource-map.yaml (owner_component/consumers[]/category の構造化宣言) へ置換し、C24 が機械検証する。

## 成果物
- `component-inventory.json`(build 軸の唯一 SSOT・全 24 component + 8 plugin_level_surfaces + no_split_threshold ブロック)。
- 16 sub-agent 全件の rebalance_disposition(5 maintain / 11 thin-adapter)+ rebalance_rationale(実測行数根拠)。
- 3 skill(C01/C02/C03)の progressive_disclosure 設計(skill_md_scope/references_new/scripts_new/no_split_reason)。

## スコープ外
- 設計の合否判定(P03 design-review へ委譲・自己承認しない)。
- 受入 criteria の導出(P04 へ委譲)。
- 実体の生成・既存ファイルの削除/上書き(build 適用は後段の別セッションに委譲・本計画は L3 のみ)。
- vendor Node engine・schemas 共通コアの再設計(goal-spec C7 により変更対象外)。

## 完了チェックリスト
- [ ] 全 24 component(C01-C24)が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、8 plugin_level_surfaces の採否が明示されている。
- [ ] 16 sub-agent 全件に rebalance_disposition(maintain/thin-adapter)と実測行数根拠を伴う rebalance_rationale が付与されている(goal-spec C1)。
- [ ] 3 skill 全件に progressive_disclosure(references_new/scripts_new/no_split_reason)が付与されている(goal-spec C2)。
- [ ] vendor/schemas surface に「既存設計は変更対象外(goal-spec C7)」が derivation として記録されている。

## 参照情報
- `goal-spec.json`(purpose/checklist C1-C7)。
- `plugin-plans/slide-report-generator/component-inventory.json`(温存対象値の read-only 参照テンプレート)。
- `references/component-domain.md` / `references/io-contract.md`。
- 対象 component C01-C24(`component-inventory.json`)、後続 P03(design-review)。
