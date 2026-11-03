---
graph_node_id: "doc-ubm-goal-contract"
artifact_kind: "document"
artifact_subtypes: []
title: "目標の書き方を揃える機能の案内"
project_id: "ubm-goal-setting"
domain: "goal-setting"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["ubm-goal-setting", "mvp"]
file_path: "docs/ubm-goal-contract.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T13:06:15.890619Z"
updated_at: "2026-11-03T13:06:15.890619Z"
depends_on: []
related_nodes: ["feature-ubm-goal-contract", "spec-ubm-goal-contract", "arch-ubm-goal-contract", "task-ubm-goal-contract"]
resource_scope: []
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.97
classification_reason: "利用者向けの案内なので文書である。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/ubm-goal-contract.md", "confidence": 0.97}, {"artifact_kind": "task", "candidate_path": "tasks/ubm-goal-contract.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T13:06:15.890619Z", "missing_sections": [], "status": "complete"}
---

# 目的

今回の目標設定の変更を、使う人向けと開発者向けに説明する。

## 対象読者

目標を書く人、目標を読む人、ubm-goal-setting を保守する人。

## 要約

売上を目的にし、そのために必要な成果と行動を、年・期・月・週で同じ規則にする。人に渡す文書と自分用の文書で項目がずれない。

## 本文

中学生向け：テストの点数目標だけを大きく書いて、毎日の勉強を書かないと届かない。この機能は、届きたい売上から逆算して、必要な成果と毎日の行動を同じ名前で揃える。人に見せる紙と自分用の紙で、項目の名前と数が違わないようにする。

専門説明：output-formats.md の共通部品を正本にし、validate-goal-output.py 0.4.0 と validate-cross-level.py 0.4.0 が期日トークン、貢献0の括弧、前回ブロック、売上2値を検査する。actions 配列へ行動項目を統合し、1ターンは3問までとする。

## 決定事項

月報の簡潔版は既定にしない。既存月報本文は自動変換しない。層間の機械照合は今期の売上目標と累計売上実績だけ。個人名は項目名に入れない。

## 運用・更新方法

書式を変えるときは共通部品、契約、対話、検査、テストを同じ変更で直す。版は CHANGELOG と plugin.json を同時に上げる。SKILL.md を直したあとは content-review を取り直す。

## 関連資料

仕様・設計・機能・案内・このタスクの5ノード。実装は plugins/ubm-goal-setting。受領書は system-spec/ubm-goal-setting/spec-impact-receipt.json。

## 変更履歴

2026-11-03：版 0.9.3 の作業ツリーを最終レビューし、正規文書と仕様影響の受領書を追加した。

