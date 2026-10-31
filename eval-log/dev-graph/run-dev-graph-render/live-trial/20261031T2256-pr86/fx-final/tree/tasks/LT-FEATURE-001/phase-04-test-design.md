---
graph_node_id: "LT-FEATURE-001-P04"
artifact_kind: "task"
artifact_subtypes: []
title: "P04 テスト設計"
project_id: "feature-package-LT-FEATURE-001"
domain: "delivery-graph"
status: "done"
priority: "medium"
start_date: null
target_date: null
iteration: null
owners: ["harness maintainers"]
tags: ["live-trial", "p04"]
file_path: "tasks/LT-FEATURE-001/phase-04-test-design.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluator": "system-dev-plan-evaluator", "evidence_ref": ".dev-graph/cache/system-dev-planner-handoff/plan-findings.json", "evaluated_digest": "d85dfa3dc8b643020a2f9c37d897d34a71e63a6e8198c599794b3cc791aa7e84"}
source_lineage: {"origin_kind": "system-dev-planner", "source_plugin": "system-dev-planner", "source_path": ".dev-graph/cache/system-dev-planner-handoff/published/LT-FEATURE-001/task-specs/phase-04-test-design.md", "source_version": "0.1.11", "source_digest": "d85dfa3dc8b643020a2f9c37d897d34a71e63a6e8198c599794b3cc791aa7e84", "imported_at": "2026-09-07T06:10:00Z"}
created_at: "2026-09-07T06:10:00Z"
updated_at: "2026-09-07T06:20:00Z"
depends_on: ["LT-FEATURE-001-P03"]
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
phase_ref: "P04"
classification_confidence: 0.99
classification_reason: "system-dev-planner が promote した exact-13 package の phase slot であるため task へ確定した"
classification_candidates: [{"artifact_kind": "task", "confidence": 0.99, "candidate_path": "tasks/LT-FEATURE-001/phase-04-test-design.md"}]
tracker_binding: "beads"
beads_linkage: null
github_publication: {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": null}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"policy": "manual", "status": "done", "source": "manual", "completed_at": "2026-09-07T06:20:00Z", "reconciled_at": "2026-09-07T06:20:00Z", "evidence_refs": [".dev-graph/cache/evidence/LT-FEATURE-001-P04.json"]}
implementation_readiness: {"status": "complete", "missing_sections": [], "checked_at": "2026-09-07T06:10:00Z"}
---

# 目的

決定論と外部依存 0 件を検証する試験を設計する。完了時に tests/render/test-design.md が所定の品質で存在している状態を成立させる。

## 背景

feature LT-FEATURE-001 は graph 実値に基づく静的 render 可視化を提供する。本 task はその
P04 slot として、architecture ARCH-LT-001 の制約 (外部依存 0 件、決定論) を満たす形で
テスト設計を担当する。

## 入力と前提条件

- 入力: canonical graph `.dev-graph/state/graph.json` と feature ノード LT-FEATURE-001。
- 前提: 先行 phase の成果物が確定していること。

## 出力と成果物

- 生成物: tests/render/test-design.md
- 更新対象: graph ノード LT-FEATURE-001-P04 の status と completion_evidence。

## 依存関係

- `depends_on`: LT-FEATURE-001-P03
- ブロッカー: 先行 phase が done でない場合は着手しない。

## 実装対象

- Frontend: N/A: 本 feature は静的 HTML 出力のみで UI framework を持たない。
- Backend/API: 二回 render の digest 一致と外部 resource 参照 0 件の検査手順を設計する
- Database/Data: N/A: 永続 store は canonical graph JSON だけで追加 schema を持たない。
- Infrastructure: N/A: 追加の実行基盤を導入しない。
- Security/Privacy: secret と絶対 path を成果物へ書かない。
- Documentation: 本 task の結果を P12 の運用文書へ反映する。

## Write scope と競合制約

- `touches`: tests/
- 排他資源: tests/
- 並列実行条件: 同一 resource_scope を持つ task と同時に実行しない。
- branch: feature branch 1 本に 1 task を割り当てる。
- worktree lease: 実装前に LT-FEATURE-001-P04 の lease を取得し、heartbeat 維持後に release する。
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

1. 二回 render の digest 一致と外部 resource 参照 0 件の検査手順を設計する。
2. 成果物を所定 path へ原子的に配置する。
3. 検証を実行し、結果を証跡として記録する。

## 受入条件

- [ ] 設計した試験が feature acceptance を全件被覆している
- [ ] 成果物が repository root 配下に収まっている。

## 検証方法

- 自動検証: 試験項目と acceptance の対応表を突き合わせる
- 手動検証: 成果物を開き、記載内容が受入条件を満たすことを確認する。
- 証跡: `.dev-graph/cache/evidence/LT-FEATURE-001-P04.json`

## リスクとロールバック

- リスク: 試験設計が実装詳細に依存し脆くなる
- ロールバック: 直前 revision の成果物へ戻し、graph ノードの status を active へ戻す。

## Handoff

- 実装 route: task-graph-build
- 次に利用するノード: P05
