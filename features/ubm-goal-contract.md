---
graph_node_id: "feature-ubm-goal-contract"
artifact_kind: "feature"
artifact_subtypes: []
title: "目標の書き方を売上から行動まで揃える"
project_id: "ubm-goal-setting"
domain: "goal-setting"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["ubm-goal-setting", "mvp"]
file_path: "features/ubm-goal-contract.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T13:06:15.890619Z"
updated_at: "2026-11-03T13:06:58.651561Z"
depends_on: []
related_nodes: ["spec-ubm-goal-contract", "doc-ubm-goal-contract"]
resource_scope: []
purpose: "年・期・月・週の目標を、売上から行動まで同じ規則で書けるようにする"
goal: "提出用と管理用の項目が一致し、検査が書式のずれを失敗にする"
scope_in: ["共通部品への書式集約", "提出用と管理用の一致", "1回3問までの対話", "売上2値の層間照合"]
scope_out: ["既存月報本文の書き換え", "他プラグインの改修", "公開APIと認証"]
acceptance: ["対象テスト479件の成功", "グラフの5文書が検証を通る", "content-review未再取得を残作業として記録する"]
architecture_refs: ["arch-ubm-goal-contract"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/ubm-goal-contract.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T13:06:58.651561Z", "missing_sections": [], "status": "complete"}
---

# 目的

年・期・月・週の目標を、売上から行動まで同じ規則で書けるようにする

## 到達状態

提出用と管理用の項目が一致し、検査が書式のずれを失敗にする

## スコープ

- スコープ内: 共通部品への書式集約
- スコープ内: 提出用と管理用の一致
- スコープ内: 1回3問までの対話
- スコープ内: 売上2値の層間照合
- スコープ外: 既存月報本文の書き換え
- スコープ外: 他プラグインの改修
- スコープ外: 公開APIと認証

## 受入

- [ ] 対象テスト479件の成功
- [ ] グラフの5文書が検証を通る
- [ ] content-review未再取得を残作業として記録する

## アーキテクチャ参照

- `arch-ubm-goal-contract`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

既存MVPの変更記録。新しい機能分解や13段の実装計画へ自動昇格しない。残作業は harness-3skp と content-review の取り直し。

