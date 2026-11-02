---
graph_node_id: "LT-FEATURE-001-P06"
artifact_kind: "task"
artifact_subtypes: []
title: "P06 テスト実行"
project_id: "feature-package-LT-FEATURE-001"
domain: "delivery-graph"
status: "active"
priority: "medium"
start_date: null
target_date: null
iteration: null
owners: ["harness maintainers"]
tags: ["live-trial", "p06"]
file_path: "tasks/LT-FEATURE-001/phase-06-test-run.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluator": "system-dev-plan-evaluator", "evidence_ref": ".dev-graph/cache/system-dev-planner-handoff/plan-findings.json", "evaluated_digest": "d85dfa3dc8b643020a2f9c37d897d34a71e63a6e8198c599794b3cc791aa7e84"}
source_lineage: {"origin_kind": "system-dev-planner", "source_plugin": "system-dev-planner", "source_path": ".dev-graph/cache/system-dev-planner-handoff/published/LT-FEATURE-001/task-specs/phase-06-test-run.md", "source_version": "0.1.11", "source_digest": "d85dfa3dc8b643020a2f9c37d897d34a71e63a6e8198c599794b3cc791aa7e84", "imported_at": "2026-09-07T06:10:00Z"}
created_at: "2026-09-07T06:10:00Z"
updated_at: "2026-09-07T06:10:00Z"
depends_on: ["LT-FEATURE-001-P05"]
related_nodes: []
resource_scope: ["tests/"]
purpose: null
goal: null
scope_in: []
scope_out: []
acceptance: []
architecture_refs: []
parent_feature: "LT-FEATURE-001"
feature_package_id: "feature-package/LT-FEATURE-001"
phase_ref: "P06"
classification_confidence: 0.99
classification_reason: "system-dev-planner が promote した exact-13 package の phase slot であるため task へ確定した"
classification_candidates: [{"artifact_kind": "task", "confidence": 0.99, "candidate_path": "tasks/LT-FEATURE-001/phase-06-test-run.md"}]
tracker_binding: "beads"
beads_linkage: null
github_publication: {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": null}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"policy": "linked_pr_merged_all", "status": "in_progress", "source": null, "completed_at": null, "reconciled_at": null, "evidence_refs": []}
implementation_readiness: {"status": "complete", "missing_sections": [], "checked_at": "2026-09-07T06:10:00Z"}
---

# 目的

設計した試験を実行し結果を収集する。完了時に tests/render/run-report.json が所定の品質で存在している状態を成立させる。

## 背景

feature LT-FEATURE-001 は graph 実値に基づく静的 render 可視化を提供する。本 task はその
P06 slot として、architecture ARCH-LT-001 の制約 (外部依存 0 件、決定論) を満たす形で
テスト実行を担当する。

## 入力と前提条件

- 入力: canonical graph `.dev-graph/state/graph.json` と feature ノード LT-FEATURE-001。
- 前提: 先行 phase の成果物が確定していること。

## 出力と成果物

- 生成物: tests/render/run-report.json
- 更新対象: graph ノード LT-FEATURE-001-P06 の status と completion_evidence。

## 依存関係

- `depends_on`: LT-FEATURE-001-P05
- ブロッカー: 先行 phase が done でない場合は着手しない。

## 実装対象

- Frontend: N/A: 本 feature は静的 HTML 出力のみで UI framework を持たない。
- Backend/API: 決定論試験と外部依存試験を実行し、失敗時は実装へ差し戻す
- Database/Data: N/A: 永続 store は canonical graph JSON だけで追加 schema を持たない。
- Infrastructure: N/A: 追加の実行基盤を導入しない。
- Security/Privacy: secret と絶対 path を成果物へ書かない。
- Documentation: 本 task の結果を P12 の運用文書へ反映する。

## Write scope と競合制約

- `touches`: tests/
- 排他資源: tests/
- 並列実行条件: 同一 resource_scope を持つ task と同時に実行しない。
- branch: feature branch 1 本に 1 task を割り当てる。
- worktree lease: 実装前に LT-FEATURE-001-P06 の lease を取得し、heartbeat 維持後に release する。
- completion projection: feature branch では pending event のみ記録し、default branch の
  reconciliation が done を書く。

## GitHub publication

- Mode: local_only
- Project aliases: N/A: repo config の github.enabled が false のため Projects へ投影しない。
- Issue labels/milestone: N/A: Issue を起票しない。
- Initial Project fields: N/A: Projects 連携を行わない。
- Publication gate: `status=active && confirmation_status=confirmed && evaluation_status=pass && implementation_readiness.status=complete`
- Failure policy: pending_retry とし、local に登録済みの task は rollback しない。
- Completion policy: manual (execution_tracker は beads であり GitHub PR を完了根拠にしない)
- PR linkage requirement: N/A: GitHub Issue/PR 連携を使わない。
- Closed without merge: keep_active
- Local reconciliation: manual sync と Claude hook による収束を用いる。

## 実行手順

1. 決定論試験と外部依存試験を実行し、失敗時は実装へ差し戻す。
2. 成果物を所定 path へ原子的に配置する。
3. 検証を実行し、結果を証跡として記録する。

## 受入条件

- [ ] 全試験が exit 0 で完了している
- [ ] 成果物が repository root 配下に収まっている。

## 検証方法

- 自動検証: 試験 runner の exit code を確認する
- 手動検証: 成果物を開き、記載内容が受入条件を満たすことを確認する。
- 証跡: `.dev-graph/cache/evidence/LT-FEATURE-001-P06.json`

## リスクとロールバック

- リスク: 試験環境差により再現しない失敗が出る
- ロールバック: 直前 revision の成果物へ戻し、graph ノードの status を active へ戻す。

## Handoff

- 実装 route: task-graph-build
- 次に利用するノード: P07
