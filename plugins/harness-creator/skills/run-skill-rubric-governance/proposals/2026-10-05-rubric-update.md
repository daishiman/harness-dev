---
date: 2026-10-05
kind: rubric-update-proposal
status: draft
trigger: aggregate-evals (SessionEnd)
---

# rubric 更新提案 (自動生成ドラフト)

## 集計サマリ

- 評価件数: 273
- FAIL 率: 1.47%
- 平均スコア: 89.364

## 検出された異常

- **run-dev-graph-sync**: friction_density — {"friction_records": 2, "window": 6, "evidence": [{"date": "2026-09-08", "iterations": null, "negative_feedback_count": 3, "findings_count": 0}, {"date": "2026-10-04", "iterations": 1, "negative_feedback_count": 2, "findings_count": 0}]}

## 主要 finding カテゴリ (top5)

- goal 判定未実施 (trial が完走せず fresh evaluator を起動できない): 3 件
- fixture resetの危険なrm permission gateで自走停止: 1 件
- 本題2の feature 入力が C02 writer ではなくその場で書いた2分岐スタブ (step 27) に渡され、fail-closed の証拠にならない: 1 件
- step 22/24/27 で R0-R4 の責務を自作 Python 1 本で代行 (R1 confidence を定数 0.95 で埋め R2 閾値判定が常に真): 1 件
- 被験 skill の責務 R0-R4 を自作 Python heredoc で代行し graph/content をそれで書いた (C02 単一 writer の CLI が無いため): 1 件

## 提案アクション (要 human review)

- 該当 rubric_id の閾値 / 観点を見直し
- 主要 finding カテゴリに対応する評価項目を新設または重み調整
- 関連する run-* / assign-* Skill の templates を更新

## 備考

本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。
