---
date: 2026-07-16
kind: rubric-update-proposal
status: draft
trigger: aggregate-evals (SessionEnd)
---

# rubric 更新提案 (自動生成ドラフト)

## 集計サマリ

- 評価件数: 222
- FAIL 率: 0.45%
- 平均スコア: 91.714

## 検出された異常

- **run-skill-create**: friction_density — {"friction_records": 2, "window": 5, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-elegant-review**: friction_density — {"friction_records": 2, "window": 5, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-company-master-backfill**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-company-master-build**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-template-sync**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **assign-blueprint-fidelity-evaluator**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-blueprint-apply**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-skill-update-notifier**: friction_density — {"friction_records": 2, "window": 4, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-mf-invoice-db-setup**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-mf-invoice-report**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-intake-option-catalog**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-notion-intake-publish**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 3, "findings_count": 0}, {"date": "2026-07-02", "iterations": 2, "negative_feedback_count": 2, "findings_count": 0}]}
- **run-slide-report-generate**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-slide-report-modify**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}]}
- **run-ubm-consult**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-ubm-goal-setting**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 0, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}
- **run-ubm-knowledge-sync**: friction_density — {"friction_records": 2, "window": 2, "evidence": [{"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}, {"date": "2026-07-12", "iterations": 2, "negative_feedback_count": 1, "findings_count": 0}]}

## 主要 finding カテゴリ (top5)

- (なし)

## 提案アクション (要 human review)

- 該当 rubric_id の閾値 / 観点を見直し
- 主要 finding カテゴリに対応する評価項目を新設または重み調整
- 関連する run-* / assign-* Skill の templates を更新

## 備考

本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。
