---
graph_node_id: "task-base-schema"
artifact_kind: "task"
artifact_subtypes: []
title: "基盤スキーマ定義"
project_id: "gm4b-schedule"
domain: "data"
status: "done"
priority: "medium"
start_date: null
target_date: null
iteration: null
owners: ["<redacted-user>"]
tags: ["live-trial", "schedule"]
file_path: "tasks/base-schema.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence:
  evaluator: "run-dev-graph-node/R2-preview"
  evidence_ref: "tasks/base-schema.md#body-digest"
  evaluated_digest: "4aa460fda71de48794db7a7b1e11899cd80012691a03c40e6a5f38a0156cbc14"
source_lineage:
  origin_kind: "manual"
  source_plugin: null
  source_path: null
  source_version: null
  source_digest: null
  imported_at: null
created_at: "2026-09-07T05:00:00Z"
updated_at: "2026-09-07T05:00:00Z"
depends_on: []
related_nodes: []
resource_scope: ["src/db/"]
purpose: "基盤スキーマ定義を完了させる"
goal: "基盤スキーマ定義が受入条件を満たし後続 task が着手できる"
scope_in: ["src/db/"]
scope_out: ["宣言した resource_scope の外にある全ファイル"]
acceptance: ["依存が全て done であること", "resource_scope 外への書込みが0件であること"]
architecture_refs: []
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.95
classification_reason: "本文が目的/依存関係/Write scope/受入条件を持つ実行単位であり task テンプレート契約に一致する"
classification_candidates: [{"artifact_kind": "task", "confidence": 0.95, "candidate_path": "tasks/base-schema.md"}, {"artifact_kind": "issue", "confidence": 0.72, "candidate_path": "issues/base-schema.md"}]
tracker_binding: "none"
beads_linkage: null
github_publication:
  mode: "local_only"
  project_aliases: []
  labels: []
  milestone: null
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence:
  policy: "manual"
  status: "done"
  source: "manual"
  completed_at: "2026-09-07T05:00:00Z"
  reconciled_at: "2026-09-07T05:00:00Z"
  evidence_refs: ["manual-verification:task-base-schema"]
implementation_readiness:
  status: "complete"
  missing_sections: []
  checked_at: "2026-09-07T05:00:00Z"
---

<!-- body-digest sha256:4aa460fda71de48794db7a7b1e11899cd80012691a03c40e6a5f38a0156cbc14 / graph_node_id は不変、file_path は routing policy から再計算する -->
# 目的

基盤スキーマ定義を完了し、後続 task が着手可能な状態にする。

## 背景

本 trial fixture の schedule 経路を検証するため、依存と resource_scope の組合せを実データで再現する。

## 入力と前提条件

- 入力: `.dev-graph/state/graph.json` の既存ノード
- 前提: C24 receipt で containment 検証済みであること

## 出力と成果物

- 生成物: 本 task artifact
- 更新対象: `.dev-graph/state/graph.json` の当該ノード

## 依存関係

- `depends_on`: N/A: 依存なし
- ブロッカー: 依存ノードが done になるまで着手しない

## 実装対象

- Frontend: N/A: 本 task は対象外
- Backend/API: 対象範囲の実装
- Database/Data: N/A: 既存スキーマを利用
- Infrastructure: N/A: 変更なし
- Security/Privacy: 既存認証境界を維持
- Documentation: 変更点を runbook へ反映

## Write scope と競合制約

- `touches`: src/db/
- 排他資源: src/db/
- 並列実行条件: 同一 batch 内で resource_scope が重複しないこと
- branch: devgraph/task-base-schema
- worktree lease: 実装前に task-base-schema を claim し heartbeat 中は保持、完了時に release する
- completion projection: feature branch は pending event のみ記録し、default branch の reconciliation が done を書く

## GitHub publication

- Mode: local_only
- Project aliases: N/A: GitHub は enabled:false
- Issue labels/milestone: N/A: local_only のため未使用
- Initial Project fields: N/A: local_only のため未使用
- Publication gate: `status=active && confirmation_status=confirmed && evaluation_status=pass && implementation_readiness.status=complete`
- Failure policy: pending_retry (local task はロールバックしない)
- Completion policy: manual
- PR linkage requirement: N/A: local_only
- Closed without merge: keep_active
- Local reconciliation: manual sync

## 実行手順

1. 依存ノードの done を確認する
2. 対象 resource_scope 配下だけを変更する
3. 受入条件を満たすまで検証を反復する

## 受入条件

- [ ] Given 依存が全て done、When 本 task を実行、Then resource_scope 外への変更が0件である

## 検証方法

- 自動検証: `python3 scripts/validate-graph-schema.py --graph .dev-graph/state/graph.json`
- 手動検証: schedule 出力の batch 重複を目視確認する
- 証跡: `.dev-graph/state/graph.json`

## リスクとロールバック

- リスク: resource_scope の宣言漏れによる並列衝突
- ロールバック: 当該ノードの status を blocked へ戻し lease を解放する

## Handoff

- 実装 route: task-graph-build
- 次に利用するノード: schedule ready-set の後続 task
