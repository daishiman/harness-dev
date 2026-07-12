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
P02 の設計(inventory と envelope draft)を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。特に「既存プラグインへの改善が単一 skill への水増しに退化していないか」「C05 を新規 `scripts/mfk_actuals.py` へ切り出す再設計が既存 `lib/mfk_reconcile.py` モノリスへの外科手術より妥当か」を実装前に検証する gate フェーズ。

## 背景
設計段階の欠陥を実装後に発見すると手戻りが大きい。本改善は 4 script + 1 skill + 1 sub-agent + 1 slash-command の 7 component 構成であり、判定ロジック(C05 mfk_actuals 抽出/C06 fidelity監査/C03 flowchart切替/C04 Notion sink)を単一 script へ丸めず責務分離した設計であることを、提案者と別 context の approver が確認する。C05 を独立モジュール化したことで plugin-root script の build_target 形式ゲート例外が解消されたことも確認対象。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が生成済み。
- elegant-review 4 条件(矛盾なし/漏れなし/整合性/依存整合)の評価枠組みを参照できる。
- レビュアは提案者と別 context で評価する(構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ(inventory+envelope draft)に適用したもの。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件(自己承認は無効)。
- 設計判断: C05(`scripts/mfk_actuals.py`)は新規切り出しによりテスト容易性・再利用性(reconcile/report/doctor から共通利用)・「MF実績=第一級の真実」の構造的明示を得る。既存 `lib/mfk_reconcile.py` の modify(find_mf_match/classify が C05 を consume する統合配線)は独立 component 化しない。

## 成果物
- design-gate の判定記録(C1-C4 全 PASS / 差し戻し理由 / C05 切り出し設計の承認記録)。

## スコープ外
- 指摘の修正そのもの(P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計(P04)・実装(P05)。
- 機械 lint の実行(P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- [ ] 単一 skill への退化(判定ロジック7要素を1 script/1 skillへ丸める設計)が無いことを確認済み。
- [ ] C05 の新規切り出し設計(`scripts/mfk_actuals.py`)が build_target 形式ゲートを例外なく満たし、`lib/mfk_reconcile.py` との統合配線が P05 本文で明記されていることを確認済み。

## 参照情報
- P02 成果物(`component-inventory.json` / `envelope-draft/plugin.json`)。
- `assign-plugin-plan-evaluator`(評価ロジックの正本・proposer≠approver)。
- 後続 P04(test-design)。
