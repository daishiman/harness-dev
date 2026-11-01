---
graph_node_id: "task-lt-task-000"
artifact_kind: "task"
artifact_subtypes: []
title: "LT fixture base task"
project_id: "lt"
domain: "fixture"
status: "closed"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "tasks/lt-task-000.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T14:30:22.986452Z"
updated_at: "2026-10-31T14:30:39.215152Z"
depends_on: []
related_nodes: []
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
classification_confidence: 0.92
classification_reason: "実装作業単位 (実行手順・受入条件を持つ単一責務の作業) なので task"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/lt-task-000.md", "confidence": 0.92}, {"artifact_kind": "issue", "candidate_path": "issues/lt-task-000.md", "confidence": 0.05}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T14:30:39.215152Z", "missing_sections": ["入力と前提条件", "出力と成果物", "依存関係", "実装対象", "Write scope と競合制約", "GitHub publication", "実行手順", "受入条件", "検証方法", "リスクとロールバック", "Handoff"], "status": "incomplete"}
---

# 目的

status fixture の前提となる基盤 task が完了している。

## 背景

task-lt-task-001 の依存先として用意する。

## 入力と前提条件

- 入力: <artifact-or-data>
- 前提: <precondition>

## 出力と成果物

- 生成物: <path-or-artifact>
- 更新対象: <path-or-node>

## 依存関係

- `depends_on`: <graph_node_id>
- ブロッカー: <condition>

## 実装対象

- Frontend: <change-or-N/A: reason>
- Backend/API: <change-or-N/A: reason>
- Database/Data: <change-or-N/A: reason>
- Infrastructure: <change-or-N/A: reason>
- Security/Privacy: <change-or-N/A: reason>
- Documentation: <change-or-N/A: reason>

## Write scope と競合制約

- `touches`: <file-or-directory-pattern>
- 排他資源: <resource-key>
- 並列実行条件: <condition>
- branch: <one task per feature branch>
- worktree lease: <claim graph_node_id before implementation; heartbeat/release policy>
- completion projection: <feature branch records pending event only; default branch reconciliation writes done>

## GitHub publication

- Mode: <local_only|issue|issue_and_projects>
- Project aliases: <repo-config alias list or N/A: default auto-add policy>
- Issue labels/milestone: <values or N/A: reason>
- Initial Project fields: <status/priority/date/iteration values or N/A: reason>
- Publication gate: `status=active && confirmation_status=confirmed && evaluation_status=pass && implementation_readiness.status=complete`
- Failure policy: <pending_retry; local promoted task is not rolled back>
- Completion policy: <linked_pr_merged_all|linked_pr_merged_any|manual; default is linked_pr_merged_all>
- PR linkage requirement: <PR body contains `Closes #<issue>` and `dev-graph: <graph_node_id>`, targets default branch>
- Closed without merge: <keep_active|mark_blocked; never auto-done>
- Local reconciliation: <manual sync + optional post-merge hook + scheduled repair>

## 実行手順

1. <single-responsibility-step>

## 受入条件

- [ ] <Given/When/Then または観測可能な結果>

## 検証方法

- 自動検証: `<command>`
- 手動検証: <procedure>
- 証跡: <path>

## リスクとロールバック

- リスク: <risk>
- ロールバック: <procedure>

## Handoff

- 実装 route: <capability-build|task-graph-build|human>
- 次に利用するノード: <graph_node_id>

