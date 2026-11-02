---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P10 — final-review

## 目的
実装者と異なる観点で完成と残課題を判定する。

## 背景
作成者の自己確認だけでは似た構図や公開範囲の見落としが残る。独立担当が仕様と実出力を照合する。

## 前提条件
P09の画像SHA付き所見と機械検査、planの最新digestを独立担当へ渡す。

## ドメイン知識
独立評価者は実装物とplanを書き換えず、矛盾・漏れ・用語整合・依存整合の所見を返す。

## 成果物
plan-findings.jsonとverificationの独立implementation review記録。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] 独立担当がC1〜C4を最新入力SHAで判定し、high/medium残件が0である。
- [ ] 独立担当が改善版の実出力を原依頼の本質成果E*で判定し、好みだけの所見を必須修正に混ぜず、利用者への提案として分けて返す。本質区分の所見を抜き出して観測と区分が合うかを確かめ、essence-approvals.jsonlの各承認記録を利用者の発言原文と照合する(C15/C17)。
- [ ] python3 scripts/flyer.py essence-checkがプラグイン全体と納品projectの両方でexit 0である(C16/C17)。
- [ ] 今回未実施のhost session/新生成/13案制作/global installを最終説明で未検証・deferredとして残し、自己レビューを独立実施と称しない。

### 受入例
- 満たす例: PASS所見にも評価範囲と未検証経路が明記される。
- 満たさない例: 機械ゲートexit0だけで意味検証済み・全実行完了と書く。

### 事前解決済み判断
修正後はchanged inputの鮮度を再評価する。最大3周で未解決ならその理由を明示しPASSを捏造しない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
