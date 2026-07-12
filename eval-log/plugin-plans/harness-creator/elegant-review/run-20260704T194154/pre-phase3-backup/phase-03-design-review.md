---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 の設計 (inventory と envelope draft) を design-gate として elegant-review 4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。特に cross-plugin build_target routing と no-split threshold 適用の妥当性を実装前に検証する。

## 背景
パイプライン境界契約は 2 plugin にまたがるため、設計段階での見落とし (build_target の routing 誤り、script の過剰分解/過小分解) は実装後の手戻りが大きい。提案者と承認者を分離 (proposer≠approver) することで、単一 skill への退化や不要な水増しを実装前に検出する。審査は独立 context で行い、指摘は P02 へ差し戻す。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review 4 条件を設計スコープ (inventory+envelope draft) に適用したもの。評価器の JSON フィールドでは `conditions.C1`..`C4` を使うが、goal-spec checklist `C1`..`C12` とは別名前空間として扱う。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一 skill 退化 = E1/E2/E3 の 3 断線が本来別責務の component (C01/C06 の skill 更新、C04/C05/C08 の gate script、C10/C11 の独立レビュー/hook) にもかかわらず 1 skill へ畳まれ分解価値が失われた状態 (本 plan では 5 種 11 component への分解が判定対象)。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review 4 条件が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] 単一 skill への退化や不要な水増しが無い (5 種写像・no-split threshold 適用の妥当性が確認済み)。
- [ ] cross-plugin build_target routing (E1/E2/E3 各修正の所有 plugin 側配置) が妥当と承認されている。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。
