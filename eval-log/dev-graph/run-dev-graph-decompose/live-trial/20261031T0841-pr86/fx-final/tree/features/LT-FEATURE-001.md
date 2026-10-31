---
graph_node_id: "LT-FEATURE-001"
artifact_kind: "feature"
artifact_subtypes: []
title: "graph 実値に基づく静的 render 可視化"
project_id: "gm4b-render"
domain: "delivery-graph"
status: "active"
priority: "medium"
start_date: null
target_date: null
iteration: null
owners: ["harness maintainers"]
tags: ["live-trial", "render"]
file_path: "features/LT-FEATURE-001.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "confirmed"
evaluation_status: "pass"
confirmation_evidence: {"evaluator": "run-dev-graph-node/R4-apply-template", "evidence_ref": ".dev-graph/cache/content-review/LT-FEATURE-001.json", "evaluated_digest": "aac2a99a70959acc3b2bbf02ec494790ab0d7712489a8e5fcbac4742257b7a15"}
source_lineage: {"origin_kind": "manual", "source_plugin": null, "source_path": null, "source_version": null, "source_digest": null, "imported_at": null}
created_at: "2026-09-07T06:10:00Z"
updated_at: "2026-09-07T06:10:00Z"
depends_on: []
related_nodes: []
resource_scope: ["features/", "tasks/LT-FEATURE-001/"]
purpose: "graph 実値だけを根拠に依存構造と進捗を外部依存なしで提示できるようにするため"
goal: "canonical graph から決定論的に生成した単一 HTML が feature/task/edge と実数進捗を表示している状態"
scope_in: ["canonical graph の読取と正規化", "parent_feature 由来の進捗集計", "inline SVG による描画"]
scope_out: ["GitHub Projects 同期", "beads server 運用", "閲覧者ごとの権限制御"]
acceptance: ["出力 HTML の外部 resource 参照が 0 件である", "feature card の進捗が graph 実値の完了 task 数と一致する", "同一 graph に対する二回の render で output digest が一致する"]
architecture_refs: ["ARCH-LT-001"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 0.96
classification_reason: "本文が feature template の必須 section 構成と一致し、第二候補との margin が閾値を超えるため自動確定した"
classification_candidates: [{"artifact_kind": "feature", "confidence": 0.96, "candidate_path": "features/LT-FEATURE-001.md"}, {"artifact_kind": "document", "confidence": 0.21, "candidate_path": "docs/LT-FEATURE-001.md"}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"mode": "local_only", "project_aliases": [], "labels": [], "milestone": null}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"policy": "manual", "status": "not_applicable", "source": null, "completed_at": null, "reconciled_at": null, "evidence_refs": []}
implementation_readiness: {"status": "complete", "missing_sections": [], "checked_at": "2026-09-07T06:10:00Z"}
---

# 目的

graph 実値だけを根拠に、feature と task の依存構造および進捗を、外部 resource へ一切依存しない
静的 HTML として関係者へ提示できるようにする。閲覧者は追加 install や network なしで
現在の実行状態を把握できる。

## 到達状態

canonical graph から生成した単一 HTML が inline SVG で feature/task/edge を描画し、
feature card に parent_feature 由来の実数進捗 (完了数/13) が表示され、同一 graph から
二回 render した出力 digest が一致する状態。

## スコープ

- スコープ内: canonical graph の読取、進捗集計、inline SVG 描画、決定論的な出力確定。
- スコープ外: GitHub Projects 同期、beads server 運用、閲覧者ごとの権限制御。

## 受入

- [ ] 出力 HTML の外部 resource 参照が 0 件である。
- [ ] feature card の進捗が graph 実値の完了 task 数と一致する。
- [ ] 同一 graph に対する二回の render で output digest が一致する。

## アーキテクチャ参照

- `architecture_refs`: ARCH-LT-001 (配信グラフ基盤の backend architecture)。

## 機能間依存

- `depends_on`: 依存する feature ノードは無い (本 fixture 唯一の feature)。
- 依存理由: 先行 feature を必要としない独立した可視化機能であるため。

## Handoff

- per-feature planning: system-dev-planner が P01..P13 の exact 13 task package を生成する。
- 生成物: 13 executable task specs と 13 node の intra-feature DAG。
- 登録先: 全 task を同一 `parent_feature`/`feature_package_id` で C02 経由 atomic 登録する。
- 完了 rollup: exact 13 全 done かつ P07/P10/P11 の evidence が揃う場合だけ feature を done にする。
