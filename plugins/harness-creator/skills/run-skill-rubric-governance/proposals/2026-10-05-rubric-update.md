---
date: 2026-10-05
kind: rubric-update-proposal
status: draft
trigger: aggregate-evals (SessionEnd)
---

# rubric 更新提案 (自動生成ドラフト)

## 集計サマリ

- 評価件数: 297
- FAIL 率: 3.37%
- 平均スコア: 89.364

## 検出された異常

- **run-dev-graph-node**: friction_density — {"friction_records": 2, "window": 6, "evidence": [{"date": "2026-10-05", "iterations": 2, "negative_feedback_count": 2, "findings_count": 0}, {"date": "2026-10-05", "iterations": null, "negative_feedback_count": 1, "findings_count": 3}]}
- **run-dev-graph-render**: friction_density — {"friction_records": 2, "window": 6, "evidence": [{"date": "2026-10-05", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-10-05", "iterations": null, "negative_feedback_count": 0, "findings_count": 3}]}
- **run-dev-graph-sync**: friction_density — {"friction_records": 2, "window": 6, "evidence": [{"date": "2026-09-08", "iterations": null, "negative_feedback_count": 3, "findings_count": 0}, {"date": "2026-10-05", "iterations": 2, "negative_feedback_count": 3, "findings_count": 0}]}

## 主要 finding カテゴリ (top5)

- goal 判定未実施 (trial が完走せず fresh evaluator を起動できない): 3 件
- Not booted: required macOS write-contained native interactive session unavailable in prior schedule host probe. No individual target launch or goal execution is claimed.: 3 件
- L120 writes graph-before.sha/tree-before.sha and L136 redirects preview.json into the native scratchpad outside the explicit fixture/proof-dir-only write boundary. Authentic macro preview does not excuse an invalid full trial.: 1 件
- Initialization preparation executed writer at L54 without reading init responsibility prompts before those outputs, contrary to the task's responsibility-prompt-before-output execution rule.: 1 件
- The real Skill call loaded instructions, but the trial never executed build-init-scaffold, R1-R5/C11 validation or the required second initialization. Six roots/config/state/templates/idempotence are not established.: 1 件

## 提案アクション (要 human review)

- 該当 rubric_id の閾値 / 観点を見直し
- 主要 finding カテゴリに対応する評価項目を新設または重み調整
- 関連する run-* / assign-* Skill の templates を更新

## 備考

本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。
