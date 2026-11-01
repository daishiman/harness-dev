---
graph_node_id: "tasks/T-SYNC-001"
artifact_kind: "task"
artifact_subtypes: []
title: "Sync import target task (remote revision 2)"
project_id: "r5-sync"
domain: "delivery"
status: "active"
priority: "high"
start_date: "2026-08-03"
target_date: "2026-08-20"
iteration: "Sprint 2026-08"
owners: ["fixture-owner"]
tags: ["live-trial", "sync"]
file_path: "tasks/T-SYNC-001.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluated_digest": "6944c4e81735ebeca22e0797ca87ee8df26ce839b53be63a64b1523ae85f5a15", "evaluator": "dev-graph-fixture-evaluator", "evidence_ref": "eval-log/r5-sync-fixture-evaluation.md"}
source_lineage: {"imported_at": "2026-07-20T00:00:00Z", "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-07-20T00:00:00Z"
updated_at: "2026-10-31T14:46:30.898068Z"
depends_on: []
related_nodes: []
resource_scope: ["src/t-sync-001"]
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
classification_reason: "fixture task authored directly under the canonical tasks root"
classification_candidates: []
tracker_binding: "github"
beads_linkage: null
github_publication: {"labels": ["dev-graph"], "milestone": null, "mode": "issue_and_projects", "project_aliases": ["delivery"]}
issue_linkage: {"issue_number": 101, "linked_at": "2026-08-01T00:00:00Z", "repo": "local-fixture/r5-sync"}
github_project_linkages: [{"field_snapshot": {"Priority": "High", "Status": "In Progress", "Target date": "2026-08-20", "priority": "High", "status": "In Progress", "target_date": "2026-08-20"}, "item_id": "PVTI_lADOFIXTURE0001zgA0101", "last_error_code": null, "last_synced_at": "2026-10-31T14:47:57.406218Z", "linked_at": "2026-08-01T00:00:00Z", "owner_login": "fixture-owner", "owner_type": "user", "project_alias": "delivery", "project_id": "PVT_kwDOFIXTURE0001", "project_number": 1, "sync_state": "synced"}]
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "linked_pr_merged_all", "reconciled_at": "2026-08-01T00:00:00Z", "source": null, "status": "in_progress"}
implementation_readiness: {"checked_at": "2026-10-31T14:46:30.898068Z", "missing_sections": [], "status": "complete"}
---
# 目的

このタスクは r5-sync live trial 用に、GitHub binding の同期経路を決定論的に検証できる状態を保つ。

## 背景

adapter fixture だけを remote authority として扱い、同一状態の二回目同期が差分0になることを確認する。

## 入力と前提条件

- 入力: .dev-graph/state/github-sync-snapshot.json の last-synced base
- 前提: confirmation_status=confirmed, evaluation_status=pass, implementation_readiness=complete

## 出力と成果物

- 生成物: eval-log/run-dev-graph-sync-pass-N.json の sync receipt
- 更新対象: .dev-graph/state/graph.json の当該 task node

## 依存関係

- `depends_on`: なし (単発 task)
- ブロッカー: なし

## 実装対象

- Frontend: N/A: fixture task で UI 変更を伴わない
- Backend/API: N/A: fixture task で API 変更を伴わない
- Database/Data: N/A: fixture task で schema 変更を伴わない
- Infrastructure: N/A: fixture task で infra 変更を伴わない
- Security/Privacy: N/A: secret を扱わない
- Documentation: fixture README の同期手順を保守する

## Write scope と競合制約

- `touches`: src 配下の当該 task ディレクトリのみ
- 排他資源: なし
- 並列実行条件: resource_scope が重複しないこと
- branch: main (fixture は default branch のみ)
- worktree lease: 取得しない (single worktree fixture)
- completion projection: default branch でのみ durable 更新を書く

## GitHub publication

- Mode: issue_and_projects
- Project aliases: delivery
- Issue labels/milestone: dev-graph ラベルのみ、milestone なし
- Initial Project fields: Status=In Progress, Priority=High, Target date=期日どおり
- Publication gate: `status=active && confirmation_status=confirmed && evaluation_status=pass && implementation_readiness.status=complete`
- Failure policy: pending_retry として残し local promotion は戻さない
- Completion policy: linked_pr_merged_all
- PR linkage requirement: PR 本文に closing reference と dev-graph marker を持ち default branch を target にする
- Closed without merge: keep_active
- Local reconciliation: manual sync と scheduled repair

## 実行手順

1. adapter fixture の remote state を読む。
2. last-synced base との 3-way 差分を分類する。
3. 分類どおりに import と export を適用する。

## 受入条件

- 二回目同期の imports/exports がともに 0 件である。
- stable IDs と snapshots が二回目で不変である。

## 検証方法

- validate-graph-schema.py が violations 0 を返す。
- adapter fixture の mutation_log が二回目で増えない。

## リスクとロールバック

- リスク: adapter fixture 外の remote へ接続すること。
- ロールバック: fixture repository を再生成する。

## Handoff

- 次段: run-dev-graph-schedule の ready 判定。
