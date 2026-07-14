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
P02 の設計 (inventory と envelope draft) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。設計段階の欠陥を実装前に止める gate フェーズ。

## 背景
設計段階の欠陥を実装後に発見すると手戻りが大きい。提案者と承認者を分離 (proposer≠approver) することで、GitHub 同期と要件定義導出を単一 skill へ畳み込む退化や、不要な水増しといった設計の歪みを実装前に検出する。審査は独立 context で行い、指摘は P02 へ差し戻す。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ (inventory+envelope draft) に適用したもの (C1-C4 の定義は index `## ドメイン知識` 参照)。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一 skill 退化 = 複数責務が 1 skill に畳まれ分解価値が失われた状態 (本 plan では init/node/sync/requirements/render の 5 分離が判定対象)。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] 単一 skill への退化や不要な水増しが無い (5 種写像の妥当性・GitHub 同期と要件定義導出の分離妥当性が確認済み)。
- [ ] 差し戻しが解消され後続フェーズへ進める状態になっている。

### 受入例
- 満たす例: 提案者 (plugin-dev-plan-architect) とは別 context の approver が inventory を審査し、C1 (矛盾なし)〜C4 (依存整合) 全て PASS の判定記録を残す。
- 満たさない例: 同一 context/セッションが設計と承認を両方行う (proposer=approver) → 自己承認として無効、差し戻し。
- 満たさない例: C03 (sync) と C04 (requirements) が 1 skill へ畳み込まれている → 単一 skill 退化として差し戻し。

### 事前解決済み判断
- design-gate の判定基準は elegant-review C1-C4 (矛盾なし/漏れなし/整合性/依存整合) に固定し、本フェーズで新規基準を発明しない。
- 差し戻し先は常に P02 (設計) とする (P03 内で直接修正しない)。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。
