---
graph_node_id: "doc-guide-doc-visual"
artifact_kind: "document"
artifact_subtypes: []
title: "読みやすい図と資料を作る機能の案内"
project_id: "guide-doc-generator"
domain: "documentation"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["visual-expression", "mvp-review"]
file_path: "docs/guide-doc-visual.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-10-31T09:58:26.388836Z"
updated_at: "2026-10-31T09:58:26.388836Z"
depends_on: []
related_nodes: ["feature-guide-doc-visual", "spec-guide-doc-visual", "arch-guide-doc-visual"]
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
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/guide-doc-visual.md", "confidence": 0.99}, {"artifact_kind": "specification", "candidate_path": "specs/guide-doc-visual.md", "confidence": 0.01}]
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

今回の機能と再生成・レビューの入口を、読者向けと開発者向けに説明する。

## 対象読者

資料を作る人、資料を読む人、guide-doc-generatorを保守する人。

## 要約

文章で説明しづらい関係を、その内容に合う図や表へ整理できる。小さい画面でも文字を小さくしすぎず、操作や補足を追える。

## 本文

中学生向け：長い説明を、道順なら矢印、違いなら表、選ぶ条件ならカードに分ける機能。教科書へ見やすい地図を添えるイメージ。

専門説明：構造化された選定記録を正規構成のハッシュと実部品IDへ結び付け、HTML/CSS・SVG・専用描画素材を分担する。CLIの検査と独立した意味レビューを組み合わせ、C19が再現用JSONと証跡を同梱する。

## 決定事項

図の枚数や一覧の網羅性を合否にしない。旧方針を差分置換し、HTMLを手編集しない。実資料は13節・依頼文6本・原画像16点・案内情報を保持した。

## 運用・更新方法

正規構成と素材を保存し、C13→C11で再生成する。選定を変えたらハッシュを更新して検査する。図種追加時はカタログ・描画・検査・例を一緒に確認する。

## 関連資料

spec-guide-doc-visual / arch-guide-doc-visual / feature-guide-doc-visual / task-gdg-review。実装正本はplugins/guide-doc-generator、設計差分はplugin-plans/guide-doc-generator/briefs。受領書はsystem-spec/guide-doc-generator/spec-impact-receipt.json。

## 変更履歴

2026-10-31：4件のBeads変更をMVP最終レビューし、正規文書・仕様影響・検査結果を集約した。

