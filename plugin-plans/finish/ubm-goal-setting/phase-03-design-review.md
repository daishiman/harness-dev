---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 完了
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 の設計 (inventory と envelope draft) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。18 実体という規模が水増しでなく goal-spec checklist (C3: sub-agent 10 本明示列挙 / C4: script 3 本明示登録) の要求に基づくことを確認する。

## 背景
設計段階の欠陥を実装後に発見すると手戻りが大きい。特に本 plan は移植プロジェクトであり、原資産 (sub-agent 11 本・shell script 3 本) をそのまま数合わせで移植すると水増しに見えかねない。提案者と承認者を分離 (proposer≠approver) することで、単一 skill への退化や不要な水増しといった設計の歪みを実装前に検出する。審査は独立 context で行い、指摘は P02 へ差し戻す。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ (inventory+envelope draft) に適用したもの (C1-C4 の定義は index `## ドメイン知識` 参照)。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一 skill 退化 = capability A (目標設定対話) と capability B (ナレッジ同期) が 1 skill に畳まれ分解価値が失われた状態 (本 plan では 2 skill 分離が判定対象)。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] sub-agent 10 本 (旧 phase3-interviewer は消費者ゼロの後方互換スタブと判明したため独立component化せず phase3-coordinator+steps へ統合済み) と script 3 本 (旧 .sh 書き換え対象) が単一 skill への退化でも不要な水増しでもなく goal-spec の明示要求に基づくことを確認済み。
- [ ] vault_root_env 変数化と knowledge の data-tier 3 層判断 (L1 curated=vendor同梱シード / L2 raw vault sources=外部env解決 / L3 bookkeeping=registry.json は実台帳初期シード・sync-log.jsonl は空の初期シード。書込は plugin 同梱 knowledge/ への直書き=writeback-config 不要と build で確定) の妥当性が確認され、差し戻しが解消され後続フェーズへ進める状態になっている。

## 参照情報
- P02 成果物 (`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator` (評価ロジックの正本・proposer≠approver)。
- 後続 P04 (test-design)。
