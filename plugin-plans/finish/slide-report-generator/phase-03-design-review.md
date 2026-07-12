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
P02 の設計(inventory と envelope draft)を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。とりわけ「既存全資産の抜け漏れ 0」「Node engine の vendor 携行(Python 化していない)」「単一 skill 退化がない」を実装前に確認する gate フェーズ。

## 背景
設計段階の欠陥(既存機能のオミット・平均回帰・Node engine の誤った stdlib 書き換え・不要な水増し component)を実装後に発見すると手戻りが大きい。提案者と承認者を分離(proposer≠approver)し、独立 context で審査して指摘を P02 へ差し戻す。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- source-inventory §5 被覆チェックリストが参照でき、既存全資産の対応先が追える。
- レビュアは提案者と別 context で評価する(構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4(矛盾なし/漏れなし/整合性/依存整合)を設計スコープ(inventory+envelope draft)に適用したもの(C1-C4 の定義は index `## ドメイン知識` 参照)。
- 抜け漏れ審査の焦点: 13 agents→C04-C16 の 1:1、report 新規(C17-C19)、Codex Image2 チェーン→C14+vendor、30種思考法→C13+C20+vendor、118 templates/42 references/30 Node scripts→surface が全て対応するか。
- 単一 skill 退化 = 3 skill(generate/modify/cross-deck-review)分離の妥当性、及び worker を 1 skill に畳んでいないか。

## 成果物
- design-gate の判定記録(C1-C4 全 PASS / 差し戻し理由 / 被覆漏れ指摘)。

## スコープ外
- 指摘の修正そのもの(P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計(P04)・実装(P05)。
- 機械 lint の実行(P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] source-inventory §5 の既存全資産が component/surface へ漏れなく対応していることが確認済み(抜け漏れ 0)。
- [ ] Node engine が vendor 携行で stdlib 書き換えされておらず、単一 skill 退化や不要な水増しが無い。
- [ ] 差し戻しが解消され後続フェーズへ進める状態になっている。

## 参照情報
- P02 成果物(`component-inventory.json` / `envelope-draft/plugin.json`)/ `source-inventory.md` §5。
- `assign-plugin-plan-evaluator`(評価ロジックの正本・proposer≠approver)。
- 後続 P04(test-design)。
