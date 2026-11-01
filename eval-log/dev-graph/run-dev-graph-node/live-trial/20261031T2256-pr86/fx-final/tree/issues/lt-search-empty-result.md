---
graph_node_id: "issue-lt-search-empty-result"
artifact_kind: "issue"
artifact_subtypes: []
title: "メモ検索で一致があるのに 0 件と表示される"
project_id: "lt-notes"
domain: "notes-search"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: []
tags: []
file_path: "issues/lt-search-empty-result.md"
template_id: "issue"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T13:56:37.038570Z"
updated_at: "2026-10-31T13:58:46.060807Z"
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
classification_confidence: 0.93
classification_reason: "利用者が観測した不具合 (期待と現在の挙動の差) の報告で、作業手順や仕様ではない"
classification_candidates: [{"artifact_kind": "issue", "candidate_path": "issues/lt-search-empty-result.md", "confidence": 0.93}, {"artifact_kind": "task", "candidate_path": "tasks/lt-search-empty-result.md", "confidence": 0.05}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T13:58:46.060807Z", "missing_sections": ["背景と問題", "再現手順またはユースケース", "影響と優先度", "スコープ", "関連グラフ", "受入条件", "検証証跡"], "status": "incomplete"}
---

# 概要

タイトルに含まれる語で検索しても結果が 0 件と表示される。

## 背景と問題

<誰が、どの状況で、何に困っているか>

## 現在の挙動

「議事録」で検索すると、タイトルが「週次議事録」のメモがあっても 0 件と表示される。

## 期待する挙動

タイトルまたは本文に検索語を含むメモがすべて結果に出る。

## 再現手順またはユースケース

1. <step>

## 影響と優先度

- 影響範囲: <users/data/system>
- 深刻度: <critical|high|medium|low>
- 緊急度: <理由>

## スコープ

- In: <対象>
- Out: <非対象>

## 関連グラフ

- 原因/親ノード: <graph_node_id>
- 関連仕様: <graph_node_id>
- 関連アーキテクチャ: <graph_node_id>
- 解決タスク: <graph_node_id>

## 受入条件

- [ ] <観測可能な結果>

## 検証証跡

- コマンド/テスト: <how-to-verify>
- 証跡 path: <path-or-url>

## 調査メモ

検索処理が完全一致で照合しており、部分一致の語を取りこぼしていることを確認した。

