---
graph_node_id: "feature-guide-doc-visual"
artifact_kind: "feature"
artifact_subtypes: []
title: "内容に合う図と読める資料を生成する"
project_id: "guide-doc-generator"
domain: "documentation"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["visual-expression", "mvp-review"]
file_path: "features/guide-doc-visual.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "generated", "source_digest": null, "source_path": null, "source_plugin": "dev-graph", "source_version": null}
created_at: "2026-10-31T09:58:26.388836Z"
updated_at: "2026-10-31T09:58:26.388836Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: "長い説明を関係に合う図・表・手順へ整理する"
goal: "文字・接続・色・開閉・再現性を保つ資料を生成できる"
scope_in: ["表現選定", "HTML/CSSとSVGの分担", "選定と表示の証跡"]
scope_out: ["他プラグインの改修", "HTMLだけのメタデータ完全復元"]
acceptance: ["対象テストと4ゲートの成功", "選定ハッシュと部品参照の検査", "3幅の主要表示と再生成一致"]
architecture_refs: ["arch-guide-doc-visual"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/guide-doc-visual.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T09:58:26.388836Z", "missing_sections": [], "status": "complete"}
---

# 目的

長い説明を関係に合う図・表・手順へ整理する

## 到達状態

文字・接続・色・開閉・再現性を保つ資料を生成できる

## スコープ

- スコープ内: 表現選定
- スコープ内: HTML/CSSとSVGの分担
- スコープ内: 選定と表示の証跡
- スコープ外: 他プラグインの改修
- スコープ外: HTMLだけのメタデータ完全復元

## 受入

- [ ] 対象テストと4ゲートの成功
- [ ] 選定ハッシュと部品参照の検査
- [ ] 3幅の主要表示と再生成一致

## アーキテクチャ参照

- `arch-guide-doc-visual`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

既存MVPの変更記録。新しい機能分解や13段の実装計画へ自動昇格しない。

