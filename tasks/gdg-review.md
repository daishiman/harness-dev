---
graph_node_id: "task-gdg-review"
artifact_kind: "task"
artifact_subtypes: []
title: "資料生成の変更を最終レビューしてdraft PRにする"
project_id: "guide-doc-generator"
domain: "documentation"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["visual-expression", "mvp-review"]
file_path: "tasks/gdg-review.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T09:58:26.388836Z"
updated_at: "2026-10-31T09:58:26.388836Z"
depends_on: ["spec-guide-doc-visual", "arch-guide-doc-visual"]
related_nodes: ["feature-guide-doc-visual"]
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
classification_confidence: 0.99
classification_reason: "既存資料生成プラグインの差分を目的別の正規成果物として記録する。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/gdg-review.md", "confidence": 0.99}, {"artifact_kind": "document", "candidate_path": "docs/gdg-review.md", "confidence": 0.01}]
tracker_binding: "none"
beads_linkage: null
github_publication: {"labels": [], "milestone": null, "mode": "local_only", "project_aliases": []}
issue_linkage: null
github_project_linkages: []
pull_request_linkages: []
execution_contexts: []
completion_evidence: {"completed_at": null, "evidence_refs": [], "policy": "manual", "reconciled_at": null, "source": null, "status": "not_applicable"}
implementation_readiness: {"checked_at": "2026-10-31T09:58:26.388836Z", "missing_sections": [], "status": "complete"}
---

# 目的

対応4件の差分だけをレビューし、仕様反映・最小ゲート・対象限定コミット・main向けdraft PRまでを完了する。

## 背景

harness-lw6u、harness-ubcg、harness-lp5j、harness-86khの変更が未コミットで残っていた。他機能の既存差分と先行コミットがあるため隔離する。

## 入力と前提条件

入力：今回の52ファイルのallowlist、既存task-specとcomponent quality_gates。remote originの既定はmainでdevはない。作業開始前のハッシュと差分を保存する。

## 出力と成果物

プラグイン、3件の既存brief、docs/features/specs/architecture/tasksの正規文書、system-specの影響索引と受領書、検査報告、draft PR。

## 依存関係

spec-guide-doc-visual、arch-guide-doc-visualを参照。別機能の作業やharness-ws7jの修正へ依存させない。

## 実装対象

既存guide-doc-generatorの表現選定・描画・読みやすさ・証跡配置。外部サービス、DB、HTTP API、他プラグインは追加変更しない。

## Write scope と競合制約

plugins/guide-doc-generator/**、対象plugin-plansのbrief、今回生成した正規文書と受領書、対象プラグインの採番と生成メタデータ。元の作業ツリーは保存する。branch: devgraph/task-gdg-review。

## GitHub publication

origin/mainをローカルmainへ取り込み、そのmainを作業ブランチへmergeしてからpushする。draft PRのbaseはmain。dev-graph: task-gdg-review。既存Beads4件を本文へ明示し、PRを自動マージしない。

## 実行手順

1. 差分をallowlistで隔離。
2. 仕様影響をC02単一writerで文書化。
3. 変更routeの既存テスト・正規化・描画・4ゲート・再生成を実行。
4. 差分と秘密情報を確認して対象だけコミット。
5. push・draft PR作成・Beads更新。

## 受入条件

対象以外の既存差分がPRへ入らない。仕様反映の実在パスとハッシュが受領書にある。静的ゲート・対象テストが通る。再生成のバイト一致を確認し、残課題と未実施を区別する。

## 検証方法

既存P05-C11/C14/C19/C20等のテストディレクトリを再実行する。変更したSKILL/agent/commandの契約、図の負例、選定・配置・逆抽出を確認する。MVPとして全社的な完全監査・新規30思考法走行は繰り返さない。

## リスクとロールバック

他機能の混入を防ぐためclean worktreeと明示ファイル指定を使う。問題があれば公開前はコミットを追加修正、公開後はrevertする。force pushは使わない。

## Handoff

draft PRを人が確認し、マージ後に通常の追跡同期へ渡す。featureは本変更の整理用draftであり、新しい13段の実装計画を捏造しない。残課題はharness-ws7j。

