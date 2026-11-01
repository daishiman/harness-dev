---
graph_node_id: "spec-lt-note-search"
artifact_kind: "specification"
artifact_subtypes: []
title: "メモ検索の仕様"
project_id: "lt-notes"
domain: "notes-search"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "specs/lt-note-search.md"
template_id: "specification"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T13:50:38.508138Z"
updated_at: "2026-10-31T13:50:59.875296Z"
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
classification_confidence: 0.91
classification_reason: "検索機能の成功状態・範囲・要件を定める仕様で、個別の作業や設計構造ではない"
classification_candidates: [{"artifact_kind": "specification", "candidate_path": "specs/lt-note-search.md", "confidence": 0.91}, {"artifact_kind": "architecture", "candidate_path": "architecture/lt-note-search.md", "confidence": 0.07}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T13:50:59.875296Z", "missing_sections": ["用語と主体", "ユースケースとユーザーフロー", "非機能要件", "UI・状態遷移", "ビジネスルールと検証", "API契約", "データモデル", "認証・認可", "エラー・例外・回復", "イベント・非同期処理", "可観測性", "互換性・移行・リリース", "テストと受入条件", "未決事項"], "status": "incomplete"}
---

# 目的と成功状態

利用者が語の一部でメモを探し、目的のメモを 1 回の検索で見つけられる。

## スコープ

対象はメモのタイトルと本文。添付ファイルの中身は対象外。

## 用語と主体

| Term/Actor | Definition/Responsibility |
|---|---|
| <term> | <definition> |

## ユースケースとユーザーフロー

1. <actor/action/result>

## 機能要件

検索語は大文字と小文字を区別せず、部分一致で照合する。

## 非機能要件

- Performance: <metric/target/load>
- Availability/Reliability: <SLO/failure behavior>
- Accessibility/Usability: <standard/target>
- Security/Privacy: <control/data classification>
- Maintainability/Operability: <requirement>

## UI・状態遷移

- 画面/CLI/API状態: <states>
- 遷移条件: <event, guard, resulting state>
- Loading/Empty/Error: <behavior>

## ビジネスルールと検証

- `BR-001`: <rule, boundary, validation message>

## API契約

APIを公開・変更する場合は `api-contract.md` を endpoint ごとに合成する。API非該当時は `N/A: <理由>` を記載する。

## データモデル

- Entity/Value: <name and purpose>
- Fields/Types/Nullability: <contract>
- Relations/Constraints/Indexes: <contract>
- Ownership/Retention/Migration: <contract>

## 認証・認可

- Authentication: <method>
- Authorization: <role/scope/resource rule>
- Tenant/data boundary: <rule>

## エラー・例外・回復

- Error taxonomy: <code/status/message>
- Retry/Timeout/Fallback: <policy>
- Idempotency/Concurrency: <policy>

## イベント・非同期処理

- Producer/Consumer: <contract-or-N/A: reason>
- Delivery/Ordering/Deduplication/DLQ: <policy>

## 可観測性

- Logs/Metrics/Traces/Audit: <signal and redaction>
- Alert/SLO dashboard: <condition>

## 互換性・移行・リリース

- Compatibility/versioning: <policy>
- Migration/backfill: <steps>
- Rollout/rollback: <steps and trigger>

## テストと受入条件

- [ ] `AC-001`: <Given/When/Then>
- Contract/integration/e2e/security/performance: <coverage>

## 未決事項

- <owner, due date, decision needed>

## 参考資料

更新: 2026-10-31

