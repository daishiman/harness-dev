---
graph_node_id: "arch-sdp-readiness-review"
artifact_kind: "architecture"
artifact_subtypes: ["backend"]
title: "最小contextと正規lock探索の設計"
project_id: "system-dev-planner"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["system-dev-planner", "mvp", "publication-review"]
file_path: "architecture/sdp-readiness-review.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T14:22:42.460658Z"
updated_at: "2026-11-03T14:26:24.611844Z"
depends_on: []
related_nodes: ["spec-sdp-readiness-review"]
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
classification_confidence: 0.96
classification_reason: "初期化前の操作停止の修復と残存証跡の公開に対応するarchitecture。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/sdp-readiness-review.md", "confidence": 0.96}, {"artifact_kind": "document", "candidate_path": "docs/sdp-readiness-review.md", "confidence": 0.04}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T14:26:24.611844Z", "missing_sections": [], "status": "complete"}
---

# Architecture overview

C07は最小context、C13正規lock root、完全context、C08 readinessの順に検査する。C09の通常呼出とCLIは従来の厳格性を保持する。

## Context and drivers

dev-graph initとSDP initの間で、plan_rootsが無いだけで全Bash/Taskが止まる不具合を修復する。通常操作の継続と実装前のfail-closed境界を両立する。

## Goals and non-goals

目標は初期化順序の違いによる操作停止を防ぐこと。認証方式、公開API、DB、lock形式、readinessの合格条件は追加変更しない。

## System context and boundaries

呼出元repo内のconfigと正規lockだけを読む。pluginの実体はツールの配置場所で、caller repoのデータ保存先ではない。外部サービスは使わない。

## Container and component view

|部品|責務|境界|
|---|---|---|
|C07|段階的な操作前検査|Bash/Taskのexit0/2|
|C09|identityと保存先の解決|通常は完全context|
|C13|正規lock rootとcleanup|LOCK_ROOT_REL|
|C08|仕様の準備検査|既存の合格条件|
|C10|不足キーだけの初期化|既存値を保持|

## Cross-cutting contracts

plan_roots欠落の許容はC07内部に限定する。内容が不正な場合は常に拒否する。コマンドを別ターミナルで実行する案内にし、対話サービス固有の!入力がhookを通らないとは断定しない。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: N/A: subtype 非選択
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Backend architecture

#### Runtime and architecture pattern

Python 3.10以上の同期ローカルフック。C07がC09/C13/C08の既存責務へ委譲する。

#### Domain and module boundaries

C09はcontext解決、C13はlock rootとcleanup、C08はreadiness、C10は初期化。C07にパス正本を複製せずLOCK_ROOT_RELを使う。

#### API and service contracts

build_context/validate_and_resolveのkeyword-only引数require_plan_rootsは既定True。FalseはC07の探索時のみ。外部HTTPは無い。

#### Data and transaction behavior

通常の検査は読取のみ。期限切れlock cleanupは既存C13のatomic/監査境界。C10は既存値を上書きしない。

#### Async processing

非同期処理は無い。PreToolUse内で同期判定し、完全context成功後にだけreadinessをsubprocess実行する。

#### Security and resilience

identity再導出、realpath containment、不正plan_roots、canonical lock identityをfail-closedで検査。復旧は別ターミナル、引数は引用する。

#### Operations and verification

B-C07/B-C09のverifyコマンド、strict graph、PEP723 lint、採番整合、allowlist diffとSHA照合を最小ゲートにする。

## Architecture decisions

|判断|採用|理由|
|---|---|---|
|初期化前|最小contextだけ検査|通常作業を止めない|
|探索先|C13の定数を参照|設定変更で有効lockを隠せない|
|実行中|完全contextを再検査|進行中の設定欠落を黙認しない|

## Delivery, migration and rollback

C10の非破壊初期化で不足キーを補う。C02で仕様・設計・機能・案内・タスクを登録し、採番後に対象だけcommitする。リモートmain→ローカルmain→作業branchの取込を記録する。revertで戻し、証跡の原履歴は消さない。

## Risks and verification

変更点の主要境界は既存50テストと43サブテストに含む。追加修正後に同じゲートを再実行する。過去の失敗ログが現在の未達と混同されるリスクは保存台帳と現行受領書の区別で抑える。

## 最終レビュー結果と残課題

最終レビュー時の再検査では、SDPの回帰50件と43サブテスト、UBMの既存タスクゲート479件が成功した。既存dev-graph実走受領書の照合はx86環境で6件成功・3件失敗。C02/node、C04/requirements、C14/decomposeの3件は今回のC07/C09変更により挙動閉包のdigestが古くなったためで、現在コードの実走PASSとは認定しない。元receiptとFAILログは保持し、digestを手で付け替えない。MVP範囲では新actor実走を行わず、harness-86khの残課題としてdraft PRへ記載する。初回arm64環境のrpds読込エラーも原ログとして保持し、x86で再実行した結果と区別する。

