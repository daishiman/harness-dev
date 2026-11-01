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
  reason: チラシ制作の再現性と導入品質のため適用
---

# P03 — design-review

## 目的
要件漏れと生成/権限/中心軸の矛盾を設計時に検出する。

## 背景
紙面全幅の中心とQR除外幅の中心を取り違えると、文字を整理しても下部が偏る。要件と実装境界を独立した担当で照合する。

## 前提条件
goal-spec.json・index.md・inventory・handoff・13phaseがそろう。作成者と評価担当を分ける。

## ドメイン知識
計画の4条件PASSは設計契約の整合だけを示す。新規背景生成やglobal導入の実行証拠にはならない。

## 成果物
独立評価担当が作るplan-findings.jsonとevaluated_inputs。設計者はfindingsを編集しない。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] 独立担当がassign-plugin-plan-evaluatorの11ゲートと意味検証を実行し、C1〜C4/重大度/入力SHAを記録する。
- [ ] high/mediumの修正を13phase・inventory・handoffへ反映後、canonical deriveを実行して再評価へ渡す。

### 受入例
- 満たす例: live:falseの理由が「未依頼」と一致し、QR保護と紙面中心が別条件になっている。
- 満たさない例: global導入必須と禁止が共存、またはgateの値だけ書き換えてPASSにする。

### 事前解決済み判断
review修正は最大3周。判断を変える大幅な方向転換だけユーザー確認、既定の不足修正は自律実行する。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
