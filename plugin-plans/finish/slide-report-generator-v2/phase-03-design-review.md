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
P02 の再配置設計(component-inventory.json の rebalance_disposition/rebalance_rationale/progressive_disclosure)を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。とりわけ「no-split threshold が無条件分割になっていないか」「vendor/schemas が変更対象に紛れ込んでいないか」「単一 skill 退化(3 skill を1つに畳んでいないか)」を実装前に確認する gate フェーズ。

## 背景
再配置設計段階の欠陥(恣意的な薄化判定・分離便益の水増し・vendor/schemas への意図しない波及・既存機能のオミット)を実装後に発見すると手戻りが大きい。提案者と承認者を分離(proposer≠approver)し、独立 context で審査して指摘を P02 へ差し戻す。responsibility rebalance という性質上、通常の design-gate に加えて「分離判断が各 component の実測根拠を伴っているか」の追加審査観点を持つ。

## 前提条件
- P02 の `component-inventory.json`(全24 component + rebalance フィールド)が生成済み。
- 既存 build 済 `plugins/slide-report-generator/`(23 component・289 files・未コミット)が read-only で対比参照できる。
- レビュアは提案者と別 context で評価する(構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4(矛盾なし/漏れなし/整合性/依存整合)を設計スコープ(inventory + progressive_disclosure 設計)に適用したもの(C1-C4 の定義は index `## ドメイン知識` 参照)。
- no-split threshold 審査の焦点: 11 thin-adapter 判定の各々が実測行数(410-990行・measured_at参照)+ 具体的な procedural knowledge/rubric の所在を rebalance_rationale に持つか(印象論での分割を許さない)。5 maintain 判定が「単に分離したくないから」ではなく抽出可能な汎用塊の不在を根拠にしているか。
- スコープ越境審査の焦点: vendor(byte維持)・schemas(共通コア)の値が P02 で一切変更されていないこと(goal-spec C7 の境界確認)。
- 単一 skill 退化 = 3 skill(generate/modify/cross-deck-review)分離の妥当性が維持されているか、及び progressive disclosure 導入を口実に worker sub-agent を skill 本体へ逆に畳んでいないか。

## 成果物
- design-gate の判定記録(C1-C4 全 PASS / no-split threshold 審査結果 / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの(P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計(P04)・実装(P05)。
- 機械 lint の実行(P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] 16 sub-agent 全件の rebalance_disposition が実測行数根拠を伴い、無条件分割になっていないことが確認済み(goal-spec C3)。
- [ ] vendor/schemas の既存設計値が P02 で一切変更されていないことが確認済み(goal-spec C7)。
- [ ] 差し戻しが解消され後続フェーズへ進める状態になっている。

## 参照情報
- P02 成果物(`component-inventory.json`)/ 既存 `plugins/slide-report-generator/`(read-only 対比参照)。
- `assign-plugin-plan-evaluator`(評価ロジックの正本・proposer≠approver)。
- 後続 P04(test-design)。
