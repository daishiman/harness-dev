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
  reason: ""
---

# P10 — final-review (最終審査ゲート)

## 目的
P09のplan-scoped gate通過を前提に、独立contextの評価者がL3 plan全域をC1-C4で最終承認する。実plugin完成度のfinal reviewは後段L4 build側の別gateとして契約のみ残す。

## 背景
design-gate (P03) は設計段階の欠陥を止めるが、最終成果物は改めて全域で審査する。P10 はplan全体 (24 component + envelope + handoff) を独立評価する。

## 前提条件
- P09のplan-scoped gateが全緑で、後段QA契約が揃っている。
- `plugin-dev-plan-evaluator` または `assign-plugin-plan-evaluator` が独立 context で起動できる。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。

## ドメイン知識
- final-gate = plan 全体 (component + envelope + handoff) を対象にした elegant-review C1-C4 (design-gate は設計段階限定・final-gate は完成後全域が対象という射程差)。
- 独立 context 評価: 評価者は生成主体と別 SubAgent/別セッションで起動し、生成側の前提を持ち込まない (自己承認の無効化)。
- 差し戻し先: 指摘の性質に応じて P02 (設計)・P05 (実装)・P08 (改善) のいずれかへ戻す。

## 成果物
- L3 plan final-gateの判定記録と、後段L4 final reviewの入力契約。

## スコープ外
- 指摘の修正そのもの (差し戻し先フェーズで対応)。
- エビデンス収集そのもの (P11)。
- 新規要件の追加 (goal-spec 変更が必要な場合は plan 外)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、独立 context の評価者が承認している。
- [ ] 指摘があった場合は該当フェーズへ差し戻され再審査で解消されている。
- [ ] 承認記録が P11 (evidence) へ引き渡せる状態になっている。

### 受入例
- 満たす例: `assign-plugin-plan-evaluator` が別contextで24 component + envelope + handoffを評価しC1-C4全PASSを返す。
- 満たさない例: 評価者が生成側の前提 (会話履歴) を引き継いだまま審査する → proposer≠approver の構造的分離が崩れ自己承認相当として無効。
- 満たさない例: 指摘 (例: C16 の hoist 根拠不備) が出たにもかかわらず差し戻し先フェーズが特定されないまま完了扱いになる → 本フェーズの完了条件を満たさない。

### 事前解決済み判断
- final-gate の対象範囲はplan全体 (24 component + envelope + handoff) に固定する。
- 差し戻し先は指摘の性質で P02 (設計)・P05 (実装)・P08 (改善) のいずれかに機械的に振り分ける (新規フェーズを作らない)。

## 参照情報
- `plugin-dev-plan-evaluator` / `assign-plugin-plan-evaluator` (評価ロジックの正本)。
- P09 成果物 (qa gate 通過ログ)。
- 後続 P11 (evidence)。
