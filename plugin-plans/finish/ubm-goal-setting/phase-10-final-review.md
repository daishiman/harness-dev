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
完成したプラグイン全体を final-gate として elegant-review C1-C4 (final) + governance で審査し、unassigned component が 0 件であることを確認する。sub-agent 10 本・script 3 本という規模が水増しでなく goal-spec の明示要求 (C3/C4) に基づくことを proposer≠approver で最終確認する。

## 背景
個々の component が緑でも、全体として矛盾・漏れ・orphan が残りうる。final-gate はプラグイン全域を C1-C4 (final scope) + governance で審査し、提案者と別の approver が最終承認する。detect-unassigned で orphan 0 件・13 フェーズ完全性を機械再確認するのがこのゲートの決定論部分。移植プロジェクトである本 plan では、sub-agent 10 本・script 3 本という規模が「原資産をそのまま数合わせで移植しただけ」に見えないか、goal-spec の明示要求 (C3/C4) に基づくかを最終確認する。

## 前提条件
- P09 の qa gate を全 component が通過している。
- `detect-unassigned.py` / `verify-index-topsort.py` が利用可能。
- 独立 approver がプラグイン全体をレビューできる (proposer≠approver)。

## ドメイン知識
- design-gate (P03) との差: P03 は設計物のみ、final-gate は組み上がった実体全域 (governance=runbook/CI 配線を含む) を審査する。
- orphan = どの phase の `entities_covered` にも現れない component (漏れの機械指標・0 件が床)。
- 決定論部分 (detect-unassigned/verify-index-topsort) と意味判定 (approver) の二層で審査する。

## 成果物
- elegant-review C1-C4 を final スコープ (プラグイン全域) で実行した判定記録。
- governance-check (runbook / CI 配線) の確認結果。
- detect-unassigned による orphan component 0 件・13 フェーズ完全性の再確認結果。
- 独立 approver によるプラグイン全体 (18 component + plugin_level_surfaces) の承認記録。

## スコープ外
- 指摘の是正実装 (該当 phase へ差し戻し・gate 内で直さない)。
- evidence 記録 (P11)・文書化 (P12)・配布 (P13)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が final スコープで全 PASS。
- [ ] governance-check (runbook / CI 配線) が PASS。
- [ ] detect-unassigned が orphan 0 件・13 フェーズ完全で、独立 approver が承認している。

## 参照情報
- elegant-review C1-C4 (final scope) / governance-check。
- `detect-unassigned.py` / `verify-index-topsort.py`。
- 後続 P11 (evidence)。
