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
再配置後のプラグイン全体を final-gate として elegant-review C1-C4(final)+ governance で審査し、unassigned component が 0 件・13 フェーズ完全であることを確認する。加えて、vendor Node engine と schemas 共通コアが本計画を通じて一切変更されていないこと(goal-spec C7)を最終確認する、proposer≠approver で最終承認を下すゲート。

## 背景
個々の component が緑でも、全体として矛盾・漏れ・orphan が残りうる。final-gate はプラグイン全域を C1-C4(final scope)+ governance(runbook/CI 配線)で審査し、提案者と別の approver が最終承認する。責務再均衡計画特有の確認点として、既存機能の非回帰(v1 build 済 plugin との入出力契約一致)と、agent⇔skill 間の情報配置境界のみが再設計対象であったこと(vendor/schemas 不可侵)を最終確認する。

## 前提条件
- P09 の qa gate を全 component が通過している。
- `detect-unassigned.py` / `verify-index-topsort.py` が利用可能。
- 独立 approver がプラグイン全体をレビューできる(proposer≠approver)。

## ドメイン知識
- design-gate(P03)との差: P03 は設計物のみ、final-gate は組み上がった実体全域(governance=runbook/CI 配線を含む)を審査する。
- orphan = どの phase の `entities_covered` にも現れない component(漏れの機械指標・0 件が床)。
- スコープ不可侵の最終確認: vendor(byte維持)・schemas(共通コア)が P02-P09 を通じて一切変更されていないこと(goal-spec C7 の最終境界確認)。

## 成果物
- final-gate の判定記録(C1-C4 全 PASS / governance PASS / unassigned 0 / vendor・schemas 不可侵確認)。

## スコープ外
- 指摘の是正実装(該当 phase へ差し戻し・gate 内で直さない)。
- evidence 記録(P11)・文書化(P12)・配布(P13)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が final スコープで全 PASS。
- [ ] governance-check(runbook / CI 配線)が PASS。
- [ ] detect-unassigned が orphan 0 件・13 フェーズ完全で、独立 approver が承認している。
- [ ] vendor/schemas が本計画を通じて一切変更されていないことが最終確認されている(goal-spec C7)。

## 参照情報
- elegant-review C1-C4(final scope)/ governance-check。
- `detect-unassigned.py` / `verify-index-topsort.py`。
- 後続 P11(evidence)。
