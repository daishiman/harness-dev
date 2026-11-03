---
graph_node_id: "task-ubm-goal-contract"
artifact_kind: "task"
artifact_subtypes: []
title: "目標設定0.9.3を最終レビューしてdraft PRにする"
project_id: "ubm-goal-setting"
domain: "goal-setting"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["ubm-goal-setting", "mvp"]
file_path: "tasks/ubm-goal-contract.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T13:06:15.890619Z"
updated_at: "2026-11-03T13:06:15.890619Z"
depends_on: ["spec-ubm-goal-contract", "arch-ubm-goal-contract"]
related_nodes: ["feature-ubm-goal-contract", "doc-ubm-goal-contract"]
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
classification_reason: "今回の差分をレビューして draft PR にする作業なのでタスクである。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/ubm-goal-contract.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/ubm-goal-contract.md", "confidence": 0.03}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-11-03T13:06:15.890619Z", "missing_sections": [], "status": "complete"}
---

# 目的

ubm-goal-setting 0.9.3 の差分だけをレビューし、仕様反映、最小検査、対象限定コミット、main 向け draft PR まで完了する。

## 背景

作業ツリーに目標設定の契約変更と、無関係なシステム開発プランナーの差分が混在していた。Beads の進行中7件は今回の差分と対応しない。関連する開いた課題は harness-3skp。

## 入力と前提条件

入力は plugins/ubm-goal-setting の未コミット差分、marketplace の版 0.9.3、知識の追加分。前提は origin に dev が無く、base は main。開始時点の main は origin/main と同一。

## 出力と成果物

プラグイン 0.9.3、docs/features/specs/architecture/tasks の正規文書、system-spec の索引と受領書、draft PR。

## 依存関係

depends_on は spec-ubm-goal-contract と arch-ubm-goal-contract。他機能の作業ツリーや system-dev-planner の plan_roots 修正には依存しない。

## 実装対象

対象は目標文書の書式、検査、対話の問い数、知識の原則の当てはめ。フロントエンド、公開API、データベース、インフラ、認証は変更しない。文書は本タスクで追加する。

## Write scope と競合制約

touches は plugins/ubm-goal-setting、marketplaces/local の当該版と指紋、正規5文書、system-spec/ubm-goal-setting、.dev-graph のグラフと受領書。branch は devgraph にこのタスクの graph node id を続けた名前。無関係差分は stage しない。

## GitHub publication

mode は local_only のグラフのまま、PR は draft で base main。自動マージしない。本文に Beads ID、dev-graph node ID、残作業を書く。dev ブランチは存在しない。

## 実行手順

1. 対象テストを実行する。
2. C02 で5文書を登録し、グラフを検証する。
3. 仕様影響の受領書を書く。
4. 対象ファイルだけを commit し、origin/main を取り込んでから draft PR を作る。

## 受入条件

- 対象 pytest が成功する。
- 新規5文書の readiness が complete で、グラフ検証の指摘が0件。
- PR の差分に system-dev-planner、設定の deny 削除、外部変更の承認記録が含まれない。

## 検証方法

自動検証は pytest の対象8ファイルと validate-graph-schema.py。手動検証は git diff の allowlist 確認。証跡は受領書と PR 本文。

## リスクとロールバック

リスクは content-review の判定が古い SKILL.md を指すこと。ロールバックは PR をマージせず閉じるか、マージ後に revert する。既存月報は変更していないので文書復旧は不要。

## Handoff

実装 route は今回のプラグイン差分そのもの。次のノードは作らない。残作業は harness-3skp と content-review の取り直し。13フェーズの実装計画へは昇格しない。

