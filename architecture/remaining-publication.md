---
graph_node_id: "arch-remaining-publication"
artifact_kind: "architecture"
artifact_subtypes: ["backend"]
title: "main保全・全件分類・証拠分離による公開統合設計"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["remaining-publication", "mvp", "source-integration"]
file_path: "architecture/remaining-publication.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T05:00:55.517262Z"
updated_at: "2026-11-16T05:28:08.821327Z"
depends_on: []
related_nodes: ["spec-remaining-publication"]
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
classification_reason: "harness-esj6で承認された元ブランチ残存の公開統合を記録するarchitecture。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/remaining-publication.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/remaining-publication.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T05:28:08.821327Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

sourceの全残存を最新mainへ3way統合し、公開すべき実装・履歴・匿名化派生物と非公開runtimeを台帳で分ける。正本と証拠の由来を保持し、不要な全体再評価を追加しない。

## Context and drivers

実装済みでも元worktreeに未公開のまま残った改善がある。一方、PR91は既にmainへ公開済みであり、元sourceの古い配置/版/参照を丸ごと適用すると公開修復が戻る。安全な履歴収束と利用者に分かる公開成果が必要。

## Goals and non-goals

未公開7機能群の価値を失わず公開し、2284statusを理由付きで全件追跡する。新しい機能要望の拡張、全system-spec再ヒアリング、exact13生成、全LLM評価、実API/live実行、既存未達の隠蔽はしない。

## System context and boundaries

source snapshot、最新main、公開worktree、非公開原本保管、親の公開manifest/quality台帳を別authorityとして扱う。公開側は原snapshotのprivate locatorを必要とせず、opaque IDとSHAで由来を検証する。

## Container and component view

YAML cache: 正規builderがcacheと索引を作り、節・見出しの必要範囲だけをReadする。hash/取得日時の不一致は停止し、ネット取得なしのreindexを提供する。
run model budget: convergence-policyを正本にrun_id全体のAI起動予算を計算し、gate/launcher/plannerが起動前に同じ台帳へ予約する。再試行の重複課金と並行予約の超過を防ぎ、枯渇時はfail-closedで起動しない。
knowledge-loop: 既存schema/lint/engineと参照文書の整合を取り、4資料、consult_at、検索・記録CLIとruntime境界を正しく案内する。新しい外部知能engineを導入する変更とは区別する。
artifact delivery: state-machineの各所の写しをglobal policy参照へ寄せ、現状で試す/診断するの選択を先に、改善深度を診断後の1回へ整理する。通常のplugin追加や起動に全repo走査・LLM評価を要求しない。
runtime profiles: 構築時DAGと実行時DAGを分け、最小十分なinlineを既定にする。独立contextや実依存がある場合だけfork/task-graphを使い、同pluginの正本参照・別pluginへの実体配布・配線なし理由・冗長path宣言を検査する。
system-dev-planner: CLI/in-processで同じrealpath境界を要求し、壊れたsymlink、UTF-8/IO、policy違反、RFC3339、世代markerの扱いを明確化する。既存exact13契約を新しい計画生成なしで維持する。
evidence and host work: hashに束縛した検査再利用、traceとbriefの一致、検証予算、C1-C4レポート、transcript計測、runtime evidence ledgerを整える。install/enable/trust/new-session等のhost担当作業は保留証拠を残し、未実行をPASSへ置き換えない。

## Cross-cutting contracts

最新mainのPR91公開済みPKG007・配布closure・owner-qualified資料・既存25node/receiptを維持する。sourceの古いfileを丸ごと上書きせず、未公開の新機能hunkと必要な履歴だけを統合する。 公開対象3ファイルは秘密/個人情報を匿名化した派生物として保存し、元bytesと元SHAは非公開保管する。公開文書へprivate raw locatorを書かない。旧FAIL/INCOMPLETEと旧verdictのreviewed SHAを保持し、現在の成功へ付け替えない。 正本cache/index・run予算・global policyへの参照を一意にし、通常追加LLM/全repo走査0を維持する。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: N/A: subtype 非選択
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Backend architecture

#### Runtime and architecture pattern

公開統合は独立worktreeで行い、通常runtimeと分離する。正本policy/辞書/validatorへ委譲し、呼出しごとの全repo走査やLLMを増やさない。

#### Domain and module boundaries

YAML抽出、run予算、knowledge参照、artifact global policy、runtime profiles、SDP境界、証拠/host ledgerの7境界を維持する。単一taskへまとめても各正本を新文書へ複製しない。

#### API and service contracts

内部CLI/JSONの変更は既存schemaとhelpを正とする。外部HTTP/DBの新規APIはない。host providerでしか実行できない操作をローカルunitの成功と区別する。

#### Data and transaction behavior

status分類manifestは初期2284項目へ対応する。C02はcontent→graph→immutable receiptをatomicに登録する。公開3派生物・非公開原本・旧verdictのSHAは別の由来として保存する。

#### Async processing

追加の常駐監査や全体LLM jobは作らない。host担当の非同期完了は既存receiptへ束縛し、未完了はpending/deferredで扱う。

#### Security and resilience

secret/approval runtimeを公開しない。realpath境界、予算予約、最新FAIL/読取不能のfail-closedを保持する。private raw locatorは公開成果物へ書かない。

#### Operations and verification

最小ゲートのコマンド・実結果・test件数・対象版は親が管理するsystem-spec/remaining-publication/quality-gates.jsonを正とする。全体LLM再評価、live再走、全coverage達成認定は追加しない。 input/status manifest照合、privacy確認、C02新5node/旧25nodeの不変性と元rootのcommit履歴収束を追加で確認する。

## Architecture decisions

ADR1: 原statusの全件台帳対応とmain/source/公開結果の分類を採用する。
ADR2: 公開済みPKG007と既存25nodeを保存し、今回5nodeを別に追加する。
ADR3: privacy3派生物は原本から分離し、旧verdict SHAを付け替えない。
ADR4: host担当操作を保留証拠で渡し、未実行をPASSにしない。
ADR5: テスト件数・版は親quality台帳の実結果へ委譲し、C02の反復更新を避ける。

## Delivery, migration and rollback

公開branch devgraph/ と tasks/remaining-publication.md の frontmatter.graph_node_id を連結したbranchからmain向け追加draft PRへ提出する。正常commitで元rootの成果を履歴へ残した後、公開branchと整合させる。rollbackは今回commitのrevertまたは公開前snapshotからの対象限定復旧とし、他案件を消さない。

## Risks and verification

sourceの古い参照/版によるmain退行、public/private混在、旧PASSの現在版への偽装、unit成功からhost完了の誤推定を防ぐ。分類漏れ・SHA不一致・secret検出は停止し、MVPで見ない既存未達は残課題へ明示する。

CIのplugin-testsは、過去の実走受領commit本文へ証跡を照合するためcommit履歴を必要とする。checkoutはfetch-depth: 0とfilter: blob:noneで履歴を保持し、blob本文は必要時に取得して一括取得を避ける。履歴不足を証跡やvalidatorの不備として扱わず、証跡・判定閾値は変更しない。

