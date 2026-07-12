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

# P10 — final-review (最終レビューゲート)

## 目的
完成したプラグイン全体を final-gate として elegant-review C1-C4 (final) + governance で審査し、unassigned component が 0 件であることを確認する。加えて既存 capability A/B の非後退 (goal-spec C11) を全域審査の一部として最終確認するゲート。

## 背景
shape greenとrunnable/end-to-end greenを分離し、独立approverが両方を最終確認する。

## 前提条件
- P09 の qa gate を全 component が通過している。
- `detect-unassigned.py` / `verify-index-topsort.py` が利用可能。
- 独立 approver がプラグイン全体をレビューできる (proposer≠approver)。

## ドメイン知識
- design-gate (P03) との差: P03 は設計物のみ、final-gate は組み上がった実体全域 (governance=runbook/CI 配線を含む) を審査する。
- orphan = どの phase の `entities_covered` にも現れない component (漏れの機械指標・0 件が床)。
- 非後退: owner matrix内はadditive parity、外はdiff空。runtime/metadata/docs/evalを別群で検査する。

## 成果物
- final-gate の判定記録 (C1-C4 全 PASS / governance PASS / unassigned 0 / 非後退 diff 確認)。

## スコープ外
- 指摘の是正実装 (該当 phase へ差し戻し・gate 内で直さない)。
- evidence 記録 (P11)・文書化 (P12)・配布 (P13)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が final スコープで全 PASS。
- [ ] governance-check (runbook / CI 配線) が PASS。
- [ ] detect-unassigned が orphan 0 件・13 フェーズ完全で、独立 approver が承認している。
- [ ] shape gates、全route runnable、無人sync、full coverage、non-zero graph、real artifact dereferenceが全PASS。
- [ ] owner matrix内additive/外diff空と既存contract回帰がPASS。

### 受入例
4条件、governance、orphan 0、runnable routes、end-to-end 4観点が独立approverでPASSする。

### 事前解決済み判断
upstream task-graph射影advisoryはruntime artifact graph C05と分離し、本planの依存DAG判定を曖昧にしない。

## 参照情報
- elegant-review C1-C4 (final scope) / governance-check。
- `detect-unassigned.py` / `verify-index-topsort.py`。
- 後続 P11 (evidence)。
