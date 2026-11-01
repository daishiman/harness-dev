---
graph_node_id: "feature-branch-publication"
artifact_kind: "feature"
artifact_subtypes: []
title: "元ブランチの全残存を新版を保持してPRへまとめる"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "features/branch-publication.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "generated", "source_digest": null, "source_path": null, "source_plugin": "dev-graph", "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-01T21:51:01.228579Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: "元ブランチの意味差分と元版の保存先を、mainの修正を戻さず全件説明できるようにする。"
goal: "全元差分に統合先または保存先・検証根拠を持たせ、未対応0件を確認してPR #87へ渡せる。"
scope_in: ["元HEAD先行11変更と元root1440 status entriesの対応付け", "dev-graph・UBM・composition・SBBの既存契約への統合", "flyer旧版と素材・検証・計画を含む元版362ファイルの保存"]
scope_out: ["新規HTTP・DB・認証基盤の追加", "新しい13フェーズ計画の生成・feature/taskの承認やpromotion", "現行flyer1.3.2を元1.3.1で上書きする変更"]
acceptance: ["全元差分の実装または保存先をmanifestで説明できる", "mainの先行修正と元worktreeを保持する", "対象別の必須ゲートと保存SHAを確認する", "本資料とfeatureはdraft・trackerなしのまま保持する"]
architecture_refs: ["arch-branch-publication"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/branch-publication.md", "confidence": 1.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-01T21:51:01.228579Z", "missing_sections": [], "status": "complete"}
---

# 目的

元ブランチの意味差分と元版の保存先を、mainの修正を戻さず全件説明できるようにする。

## 到達状態

全元差分に統合先または保存先・検証根拠を持たせ、未対応0件を確認してPR #87へ渡せる。

## スコープ

- スコープ内: 元HEAD先行11変更と元root1440 status entriesの対応付け
- スコープ内: dev-graph・UBM・composition・SBBの既存契約への統合
- スコープ内: flyer旧版と素材・検証・計画を含む元版362ファイルの保存
- スコープ外: 新規HTTP・DB・認証基盤の追加
- スコープ外: 新しい13フェーズ計画の生成・feature/taskの承認やpromotion
- スコープ外: 現行flyer1.3.2を元1.3.1で上書きする変更

## 受入

- [ ] 全元差分の実装または保存先をmanifestで説明できる
- [ ] mainの先行修正と元worktreeを保持する
- [ ] 対象別の必須ゲートと保存SHAを確認する
- [ ] 本資料とfeatureはdraft・trackerなしのまま保持する

## アーキテクチャ参照

- `arch-branch-publication`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

本featureは全残存統合の整理用draftであり、plannerを起動せず新たなexact13 packageへ昇格しない。実行追跡は既存harness-86kh、元差分の分類はdocs/branch-publication/manifest.json、公開は親のPR #87の実行証跡へ渡す。

