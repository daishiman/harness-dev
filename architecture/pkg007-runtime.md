---
graph_node_id: "arch-pkg007-runtime"
artifact_kind: "architecture"
artifact_subtypes: ["backend"]
title: "検査正本と自己完結runtimeを分ける設計"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["pkg007", "mvp", "publication-review"]
file_path: "architecture/pkg007-runtime.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T03:37:44.999349Z"
updated_at: "2026-11-16T03:45:51.306227Z"
depends_on: []
related_nodes: ["spec-pkg007-runtime"]
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
classification_reason: "harness-zb7qで承認されたPKG007の対象scope・配布依存・開発lint分離を記録するarchitecture。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/pkg007-runtime.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/pkg007-runtime.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T03:45:51.306227Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

宣言・機械検査・配布runtime・開発lintの4境界を分離し、それぞれ既存の正本へ委譲する。

## Context and drivers

旧PKG007の人手判定は注釈・候補順・集約単位に曖昧さがあり、feedbackにはrepo配置前提の依存があった。簡単実行・短時間・低トークン条件で今回範囲だけを修復する。

## Goals and non-goals

実行参照の決定論検査とfeedbackの配布内解決を実現する。今回共通部品を含む23pluginだけをpatch採番しmetadata整合を確認する。全参照の網羅化、API/DB/認証変更、全体coverage達成、新exact13、live再走、installは行わない。

## System context and boundaries

開発時はrepoのvalidator/lintが実行される。利用時はhostが示すSKILL_ROOTとowner plugin manifest、明示設定、登録済みguard pluginだけを使う。

## Container and component view

check_pkg_007→YAML宣言/候補解決/属性検査。skill/scripts→submit・notion_config・tenant_runtime・extract-plugin-root・anchor。skill/schemas→既存2schema。manifest build_validation→repo lint。

## Cross-cutting contracts

scopeはcatalogと36章で統一し、手順本文に007の規則を複製しない。runtime資産はbyte一致、helperも明示script_refsなら属性要求を維持する。secretと旧判定の手動書換は禁止する。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: N/A: subtype 非選択
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Backend architecture

#### Runtime and architecture pattern

ローカルPythonの開発時validatorと、配布skill内の同期feedback runtimeを分離する。通常の起動で開発lintやLLM評価を増やさない。

#### Domain and module boundaries

catalogは対象scope、check_pkg_007は実行規則、SKILL/R1は呼出しと残る意味判断。feedbackのsubmit/config/tenant/root resolver/anchorはskill内へ置き、repo lintはbuild_validationに残す。

#### API and service contracts

外部APIは変更しない。repo submitは従来plugin loaderへのfallbackを保持し、配布版は同階層loaderを使う。config resolverの公開関数契約を保つ。

#### Data and transaction behavior

validatorは対象を読み取りfindingsを出す。vendorはcanonical bytecopyで同期しSSOT lintで差分を検出する。C02は5文書→graph→immutable receiptを単一transactionで登録する。

#### Async processing

新規の非同期処理はない。既存guard receipt flowのみが外部mutationを許可する。

#### Security and resilience

realpath containment、先勝ち候補、不正第一候補の救済禁止、明示configのfail-closedを維持する。隔離テストでsocketと外部processを遮断しKeychain/Notion通信を防ぐ。

#### Operations and verification

PKG007と対象回帰、feedbackstrict/vendor、graph新規5nodeと受領書SHA検査を最小確認にする。全system-spec再ヒアリングや新actor実走を追加しない。

## Architecture decisions

ADR1: 明示script_refs＋従来root検査を対象にし、本文・他refsへ拡張しない。
ADR2: runtime closureをskill内へ閉じて既存配布を利用する。
ADR3: repo lintは開発役割へ移し、IN1/IN2と属性要件を保持する。
ADR4: 通常起動には追加検査0とする。

## Delivery, migration and rollback

既存canonical→22コピー同期で展開し、今回共通部品を含む23pluginをbuild-plugin-release.pyでpatch採番・正規metadata生成した（harness-creator 1.4.66、dev-graph 0.1.34等）。release整合を検証しinstallはしない。公開はdevgraph/task-pkg007-runtimeからmain向けdraft PR。rollbackは対象commitのrevertを使い、原workspaceや他者差分を消さない。

## Risks and verification

本文/他refsの実在までPKG007 PASSが保証すると誤解するリスクはscope明記で防ぐ。公開treeでは対象10ファイル521件を確認し、元作業treeの無関係2testを公開へ含めない。Notion/live未実行と既存coverage未達を残課題として明記し、今回23packageの版整合と区別する。

