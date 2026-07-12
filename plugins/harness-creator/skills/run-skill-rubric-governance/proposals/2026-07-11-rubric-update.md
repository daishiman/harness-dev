---
date: 2026-07-11
kind: rubric-update-proposal
status: draft
trigger: aggregate-evals (SessionEnd)
---

# rubric 更新提案 (自動生成ドラフト)

## 集計サマリ

- 評価件数: 165
- FAIL 率: 0.61%
- 平均スコア: 91.714

## 検出された異常

- **run-intake-option-catalog**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-notion-intake-publish**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 3, "findings_count": 0}, {"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 2, "findings_count": 0}]}
- **run-cross-deck-review**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-05", "iterations": 2, "negative_feedback_count": 2, "findings_count": 0}, {"date": "2026-07-05", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-slide-report-generate**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-11", "iterations": 1, "negative_feedback_count": 2, "findings_count": 0}, {"date": "2026-07-11", "iterations": 1, "negative_feedback_count": 2, "findings_count": 0}]}
- **assign-system-spec-completeness-evaluator**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-11", "iterations": 1, "negative_feedback_count": 3, "findings_count": 0}, {"date": "2026-07-11", "iterations": 1, "negative_feedback_count": 2, "findings_count": 0}]}

## 主要 finding カテゴリ (top5)

- (なし)

## 提案アクション (要 human review)

- 該当 rubric_id の閾値 / 観点を見直し
- 主要 finding カテゴリに対応する評価項目を新設または重み調整
- 関連する run-* / assign-* Skill の templates を更新

## 備考

本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。
