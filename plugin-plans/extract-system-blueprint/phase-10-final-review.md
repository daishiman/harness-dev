---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 完了
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビューゲート)

## 目的
完成したプラグイン全体を final-gate として elegant-review C1-C4 (final) + governance で審査し、unassigned component が 0 件であることを確認する。proposer≠approver で最終承認を下すゲート。

## 背景
個々のcomponentが緑でも、全体の因果鎖が切れれば安全・忠実性は保証できない。final-gateはC12→C09/C15/C08→C03、local draft→C02 PASS(ローカル品質verdict・外部公開なし)、低負荷budget、fact/inference/gap、P05だけがbuild_targetをproduceするtask-graph射影を独立approverが最終確認する。

## 前提条件
- P09 の qa gate を全 component が通過している。
- `detect-unassigned.py` / `verify-index-topsort.py` が利用可能。
- 独立 approver がプラグイン全体をレビューできる (proposer≠approver)。

## ドメイン知識
- design-gate (P03) との差: P03 は設計物のみ、final-gate は組み上がった実体全域 (governance=runbook/CI 配線を含む) を審査する。
- orphan = どの phase の `entities_covered` にも現れない component (漏れの機械指標・0 件が床)。
- 決定論部分 (detect-unassigned/verify-index-topsort) と意味判定 (approver) の二層で審査する。

## 成果物
- final-gate の判定記録 (C1-C4 全 PASS / governance PASS / unassigned 0)。

## スコープ外
- 指摘の是正実装 (該当 phase へ差し戻し・gate 内で直さない)。
- evidence 記録 (P11)・文書化 (P12)・配布 (P13)。

## 完了チェックリスト
- [x] elegant-review C1-C4 が final スコープで全 PASS。
- [x] governance-check (runbook / CI 配線) が PASS。
- [x] detect-unassigned が orphan 0 件・13 フェーズ完全で、独立 approver が承認している。
- [x] handoff routes=inventory components=task-graph producesが15件1:1で、P02から実build_targetをproduceせず、P05のcomponent taskだけがproduceする。
- [x] C1-C9のE2E evidenceが揃い、重要fact欠測・無断アクセス・request budget超過が0件である。

### 受入例
- C1-C9のE2E因果鎖が閉じ、visual assets/field gaps/prompt guards/ローカル出力/低負荷ledgerに断裂がないと独立approverが判定する。

### 事前解決済み判断
- component個別PASSだけでは承認せず、C12→C03→C11→C02→C01(ローカルdraft完成・外部公開なし)の全体順序と、C14がC02 PASS済blueprintのみを消費する下流順序を最終条件とする。

## 参照情報
- elegant-review C1-C4 (final scope) / governance-check。
- `detect-unassigned.py` / `verify-index-topsort.py`。
- 後続 P11 (evidence)。
