---
graph_node_id: "feature-remaining-publication"
artifact_kind: "feature"
artifact_subtypes: []
title: "元ブランチ全残存を追跡可能な追加PRへ公開する"
project_id: "harness-creator"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["remaining-publication", "mvp", "source-integration"]
file_path: "features/remaining-publication.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-16T05:00:55.517262Z"
updated_at: "2026-11-16T05:00:55.517262Z"
depends_on: []
related_nodes: ["spec-remaining-publication", "doc-remaining-publication"]
resource_scope: []
purpose: "未公開の改善・仕様・検証成果を失わず公開し、元rootも公開履歴へ揃える"
goal: "初期2284statusすべての行き先と理由が台帳で追え、main公開済み修復を保った7機能群が追加draft PRへ提出され、元rootに正常commitの履歴が残って公開branchと整合する"
scope_in: ["7機能群の未公開hunkと必要履歴の3way統合", "main公開済み/新規統合/履歴保存/秘密匿名化/非公開tempの全件分類", "privacy3派生物と旧verdict SHAの由来保全", "正規5文書・writer receipt・親quality台帳による最小ゲート", "対象限定commit/push/draft PRと元rootの履歴収束"]
scope_out: ["secret/鍵/実行時承認記録/private raw locatorの公開", "PR91 PKG007と既存25nodeの退行", "新exact13・全system-spec再ヒアリング", "全LLM評価/実API/live再走", "既存全体coverage達成やmanual completionの自動done認定"]
acceptance: ["初期2284statusが理由と対応先付きでmanifestへ全件対応する", "mainの公開済み修復と既存25nodeを保持する", "親quality-gatesの今回最小ゲートが成功する", "privacy3派生物と旧SHAを検証でき秘密/非公開tempを公開しない", "今回5nodeがdraft/pending/readiness completeで登録される", "元rootに正常commitの履歴を残した後に公開branchの履歴へ揃える"]
architecture_refs: ["arch-remaining-publication"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/remaining-publication.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-16T05:00:55.517262Z", "missing_sections": [], "status": "complete"}
---

# 目的

未公開の改善・仕様・検証成果を失わず公開し、元rootも公開履歴へ揃える

## 到達状態

初期2284statusすべての行き先と理由が台帳で追え、main公開済み修復を保った7機能群が追加draft PRへ提出され、元rootに正常commitの履歴が残って公開branchと整合する

## スコープ

- スコープ内: 7機能群の未公開hunkと必要履歴の3way統合
- スコープ内: main公開済み/新規統合/履歴保存/秘密匿名化/非公開tempの全件分類
- スコープ内: privacy3派生物と旧verdict SHAの由来保全
- スコープ内: 正規5文書・writer receipt・親quality台帳による最小ゲート
- スコープ内: 対象限定commit/push/draft PRと元rootの履歴収束
- スコープ外: secret/鍵/実行時承認記録/private raw locatorの公開
- スコープ外: PR91 PKG007と既存25nodeの退行
- スコープ外: 新exact13・全system-spec再ヒアリング
- スコープ外: 全LLM評価/実API/live再走
- スコープ外: 既存全体coverage達成やmanual completionの自動done認定

## 受入

- [ ] 初期2284statusが理由と対応先付きでmanifestへ全件対応する
- [ ] mainの公開済み修復と既存25nodeを保持する
- [ ] 親quality-gatesの今回最小ゲートが成功する
- [ ] privacy3派生物と旧SHAを検証でき秘密/非公開tempを公開しない
- [ ] 今回5nodeがdraft/pending/readiness completeで登録される
- [ ] 元rootに正常commitの履歴を残した後に公開branchの履歴へ揃える

## アーキテクチャ参照

- `arch-remaining-publication`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

Beads harness-esj6 / tasks/remaining-publication.md の frontmatter.graph_node_idで追跡する。公開担当がquality/impact/manifestと公開操作、文書担当が今回5nodeとC02 receiptを担当する。completion policyはmanual。draft PR作成やmanifest登録だけでdoneに昇格せず、既存未達・host担当保留を明記する。

