---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: [C03, C07]
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P01 — requirements

## 目的
利用環境と全会話の要件を確定する。

## 背景
写真の顔・子供・画面保護は素材ごとに異なる。制作担当の思い込みを検査者へ持ち込まないため、独立検査担当C03の入力と拒否条件を先に確定する。1.2.0では改善提案も別担当が評価するため、提案評価担当C07の入力と拒否条件も同じ段階で確定する(C13)。1.2.0では構図・文字・配色の知見を3専門役agentへ相談していたが、段階ごとに起動するとLLM呼出しが段階数×専門役数で増え、相談先から評価が書き換わる経路も残る。知見はreferences/design-knowledge-index.jsonのlensとして各担当が読む形に固定する(C13/C16)。あわせて、両担当が判定の基準にする原依頼と本質成果(references/essence.json)の形をここで決めないと、周回ごとに基準が動いて本質からずれる(C15)。

## 前提条件
goal-spec.jsonのC5/C9/C13/C15/C16とassets/catalog.json、references/hyogo-v13-feedback.md、references/production-history/の4素材の公開範囲、schemas/analysis-review.schema.jsonとschemas/visual-review.schema.jsonを読む。

## ドメイン知識
U01の指定crop、U02の本人以外の顔、U03の子供除去、U04の参加者とPC/電話画面を個別に扱う。本人と公開スクリーンは許可に従う。

## 成果物
C03: skills/assign-flyer-review/agents/visual-review-coordinator.md・skills/assign-flyer-review/references/review-contract.md・prompts/visual-review.mdの入力/判定契約。C07: skills/assign-flyer-analysis-review/agents/analysis-evaluator.md・references/evaluation-contract.mdの入力/判定契約。references/essence.json(本質課題・二値の本質成果E*・非目的・予算・golden事例)の項目契約と、references/design-knowledge-index.jsonの構図/文字/配色lens。素材の正本はassets/catalog.json。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] C03が全案の最終PNGとSHAを受け取り、各画像に中央軸・公開範囲・読み順の具体所見を返す契約がreview-contract.mdにあり、旧agents/flyer-reviewer.mdの共通完成レビュー手順がそこへ吸収されている。
- [ ] C03が未実見・素材許可未確認・必須修正残ありをPASSにせず、C5/C9に対応する拒否条件をprompts/visual-review.mdに持つ。制作へ直接戻した修正の再評価では、briefの必須事実の欠落と公開範囲の変化も拒否条件にする(C15)。
- [ ] C07が元画像・最新要望・analysis.jsonのSHAを受け取り、観察一致・網羅・変更規律・実現性の根拠とPASS/FIXの戻り先を返し、未照合の元画像をPASSにしない契約がevaluation-contract.mdにある。
- [ ] references/essence.jsonが本質課題・二値の本質成果E*・非目的・予算・golden事例の5項目を持ち、C03/C07が所見ごとに本質成果IDと本質/好みの区分を返す契約がある。本質区分の所見は該当E*の二値基準の失敗を示す観測(画像SHA・領域・失敗した基準の文言)を必須とし、観測の無い所見とE*に結び付かない所見はFIXにせず、好みの提案として分けて返す(C15)。
- [ ] C03/C07がchecks.json・analysis-validateで判定済みの項目を再判定せず、実見が要る項目だけを返し、構図・文字・配色の知見はdesign-knowledge-index.jsonのlensから必要な分だけ読む(C16)。
- [ ] C03/C07のtoolsがReadのみで、判定JSONの書込みは呼出元assign skillが行い、評価担当が制作物・分析を変更できない。専門役をagentとして起動する経路が無い(C13)。

### 受入例
- 満たす例: U02は本人のみ明瞭、他者を匿名化した最終PNGを見て画像SHAと所見を返す。
- 満たさない例: 参考人物を転載、子供が残る、またはPNGを見ずに「全案PASS」とする。本質成果に結び付かない色味の好みをFIXにして周回を1つ使う。

### 事前解決済み判断
素材の使用可否はcatalogの公開範囲を正本とし、判断不能なら制作担当へ確認を返す。既存許可を勝手に拡大しない。評価担当の書込み禁止は本文の約束でなくtools許可で保証する(現物1.2.0のagentはtools未指定で全ツールを継承しているため)。本質成果の文言は計画で決めず、build時にproduction-historyとhyogo-v13-feedbackの実事例から起こして利用者の確認を経る。build後にE*を足す・変える時も利用者の確認を経て、確認記録の無い追加はessence-checkが拒否する。計画が固定するのは項目の形と、所見をE*へ結ぶ義務だけである。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
