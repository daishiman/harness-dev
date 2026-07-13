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
完成したプラグイン全体 (plugin-dev-planner 7 component + harness-creator 4 component) を final-gate として elegant-review 4 条件 (final) + governance で審査し、unassigned component が 0 件であることを確認する。proposer≠approver で最終承認を下すゲート。

## 背景
個々の component が緑でも、全体として矛盾・漏れ・orphan が残りうる。特に cross-plugin routing (E1/E2/E3 各修正が所有 plugin 側へ正しく配置されているか) は個別 component レビューでは見落としやすいため、final-gate はプラグイン全域を 4 条件 (final scope) + governance で審査し、提案者と別の approver が最終承認する。detect-unassigned で orphan 0 件・13 フェーズ完全性を機械再確認するのがこのゲートの決定論部分。

## 前提条件
- P09 の qa gate を全 11 component が通過している。
- `detect-unassigned.py` / `verify-index-topsort.py` が利用可能。
- 独立 approver がプラグイン全体 (2 plugin にまたがる変更) をレビューできる (proposer≠approver)。

## ドメイン知識
- design-gate (P03) との差: P03 は設計物のみ、final-gate は組み上がった実体全域 (governance=runbook/CI 配線を含む) を審査する。
- orphan = どの phase の `entities_covered` にも現れない component (漏れの機械指標・0 件が床)。
- cross-plugin 一貫性: plugin-dev-planner 側 7 component (C01-C05,C10,C11) と harness-creator 側 4 component (C06-C09) の間で provenance chain (C05/C11) が正しく両側を橋渡ししていることを最終確認する。
- 決定論部分 (detect-unassigned/verify-index-topsort/check-runtime-portability) と意味判定 (approver) の二層で審査する。

## 成果物
- final-gate の判定記録 (4 条件全 PASS / governance PASS / unassigned 0)。

## スコープ外
- 指摘の是正実装 (該当 phase へ差し戻し・gate 内で直さない)。
- evidence 記録 (P11)・文書化 (P12)・配布 (P13)。

## 完了チェックリスト
- [ ] elegant-review 4 条件が final スコープで全 PASS。
- [ ] governance-check (runbook / CI 配線) が PASS。
- [ ] detect-unassigned が orphan 0 件・13 フェーズ完全で、独立 approver が承認している。
- [ ] cross-plugin routing (E1/E2/E3 各修正の所有 plugin 側配置) が最終確認され、plugin-plans/plugin-dev-planner・plugin-plans/skill-intake への影響が皆無であることが再確認されている。

## 参照情報
- elegant-review 4 条件 (final scope) / governance-check。
- `detect-unassigned.py` / `verify-index-topsort.py` / `check-runtime-portability.py`。
- 後続 P11 (evidence)。
