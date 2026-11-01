---
graph_node_id: "task-branch-remaining-publication"
artifact_kind: "task"
artifact_subtypes: []
title: "元ブランチの残存全変更を最新mainへ統合してPR化する"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: []
file_path: "tasks/branch-remaining-publication.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:31:31.563501Z"
updated_at: "2026-11-01T21:31:31.563501Z"
depends_on: []
related_nodes: ["task-gdg-review"]
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
classification_confidence: 1.0
classification_reason: "既存機能の残存差分全体の公開統合を追跡する通常task"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/branch-remaining-publication.md", "confidence": 1.0}, {"artifact_kind": "document", "candidate_path": "docs/branch-remaining-publication.md", "confidence": 0.0}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-01T21:31:31.563501Z", "missing_sections": [], "status": "complete"}
---

# 目的

元ブランチに残る全変更を、最新リモートを取り込んだPRへ漏れなく統合する。

## 背景

利用者はguide関連だけでなく、このブランチの残存変更全体をPR対象と指定した。

## 入力と前提条件

元worktree HEAD 8c1eb6c8と未commit差分、PR #87、origin/main 76abc53d。古い元ファイルでmainの修正を戻さない。

## 出力と成果物

全残存変更の対応表・統合コード・仕様影響受領書・最小検証・PR。

## 依存関係

既存task-gdg-reviewと関連するが、他の作業者のBeadsを無断で完了にしない。

## 実装対象

dev-graph、UBM、harness-creator、governance lint、release writer、flyer、system-briefingの未公開分。

## Write scope と競合制約

PR作業ツリーだけに3-way統合。元worktreeは保持。他の実行担当と所有ファイルを分担し、main側変更を保存。

## GitHub publication

PR #87、head devgraph/task-gdg-review、base main。全対象の対応表と残存0件を記録。

## 実行手順

1. 全件棚卸し。2. remote→local main→PRへmerge。3. 3-way統合と競合解消。4. 最小ゲート。5. commit/push/CI。

## 受入条件

全元差分について、反映済み/統合/元版保存/一時状態の扱いを実パスで説明できる。新旧履歴とmainの修正を保持。

## 検証方法

対象ごとの既存回帰とpackage/release/意味評価の必須ゲート。MVPとして全30思考法を再走しない。

## リスクとロールバック

旧版の丸ごと上書きや他人の変更の撤回を避ける。公開後の修正は追加commit/revert。

## Handoff

利用者の全件指示に基づく統合タスク。残存差分一覧をPRへ載せる。

