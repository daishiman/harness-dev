---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P07 — acceptance-criteria

## 目的
用途に合う新構図と全案の検証完了を判定する。

## 背景
構図署名と試験が通っても、制作用途や漫画/手書きの希望を満たすとは限らない。実際に達した範囲を受入結果へ分離する。

## 前提条件
verification/results.jsonとtests結果、references/interview.mdの形式選択項目を読む。

## ドメイン知識
標準13案は枚数であり13固定テンプレートではない。白黒各1案必須、単一案依頼なら矛盾を確認する。

## 成果物
verification/requirements.jsonに要件別の実装証拠・実測証拠・未検証範囲を記録する。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] C1/C2のヒアリングと新構図設計、C3の白黒、C6の生成未実施境界、C9の全案実見条件をrequirements.jsonで個別判定する。
- [ ] 写真以外の表現形式を受理する契約と、漫画/手書きの本番画像を実生成した証拠の有無を区別する。
- [ ] C13の4段階分離(担当の別context・local agentとstage契約・評価担当の読取専用)とC14の工程全体3周上限を、実走記録と試験結果の両方で個別判定する。
- [ ] C15-C17を、実走記録(原依頼hash・所見の本質/好み区分・FIXの振分先・再利用した判定・起動したLLM担当数)とessence-checkの結果で個別判定し、試験の成功だけで本質に適合したと扱わない。

### 受入例
- 満たす例: 漫画選択と生成プロンプトは検証済み、漫画本番描画は未検証、と分ける。
- 満たさない例: photo2案成功を全形式13案成功と一般化する。essence-checkのexit 0だけを見て、実走で好みの所見が周回を使っていたことを見落とす。

### 事前解決済み判断
受入は機能成立と今回の制作実測範囲を併記する。未検証を自動PASSへ昇格しない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
