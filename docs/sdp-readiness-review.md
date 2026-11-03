---
graph_node_id: "doc-sdp-readiness-review"
artifact_kind: "document"
artifact_subtypes: []
title: "初期化前の操作停止を直す機能と残存証跡の案内"
project_id: "system-dev-planner"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["system-dev-planner", "mvp", "publication-review"]
file_path: "docs/sdp-readiness-review.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T14:22:42.460658Z"
updated_at: "2026-11-03T14:26:24.611844Z"
depends_on: []
related_nodes: ["feature-sdp-readiness-review", "spec-sdp-readiness-review", "arch-sdp-readiness-review", "task-sdp-readiness-review"]
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
classification_reason: "初期化前の操作停止の修復と残存証跡の公開に対応するdocument。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/sdp-readiness-review.md", "confidence": 0.97}, {"artifact_kind": "task", "candidate_path": "tasks/sdp-readiness-review.md", "confidence": 0.03}]
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

# 目的

今回の修復と残存証跡の公開範囲を、利用者と保守担当が理解できるようにする。

## 対象読者

このリポジトリで開発する人と、プラグインの保守担当。

## 要約

計画用の設定がまだ無いだけで、通常の操作まで止めないようにする。計画を実行中なら、必要な設定と仕様がそろうまで止める。

## 本文

中学生向け：新しい実験の準備がまだなのに、教室の普段の勉強まで全部止まる状態を直した。普段の作業は続けられ、実験を始めるときには準備を確認する。壊れた設定を見逃したり、実行中の目印を隠したりはできない。

専門説明：C07でC09のrequire_plan_roots=Falseによる最小contextを解決し、C13.LOCK_ROOT_RELを探索する。有効lockがあれば既定Trueの完全contextを再解決してC08を実行する。plan_rootsの欠落以外の不正値とidentity/containment違反は常に拒否する。履歴eval-logは原bytes/SHAを保存し、現行criteria受領書と区別する。

## 決定事項

originにdevが無いのでbaseはmain。PR88は取り込み済み。本公開はdevgraph に本 task の node ID を続けたブランチ。Beadsは既存の全残存公開課題harness-86khを更新する。ローカルdeny削除・署名トークン・一時入力は製品へ含めない。

## 運用・更新方法

仕様変更はC02 build-graph-node.pyのpreview→revision指定applyで反映する。gateとSHAをsystem-spec/sdp-readiness-reviewへ記録し、公開後のPR URLをBeadsへ追記する。

## 関連資料

[仕様](../specs/sdp-readiness-review.md)、[設計](../architecture/sdp-readiness-review.md)、[タスク](../tasks/sdp-readiness-review.md)、[受領書索引](../system-spec/sdp-readiness-review/README.md)。B-C07/B-C09が実装の受入条件。

## 変更履歴

2026-11-03: 初期化前ガード修復、未提出証跡の保存と最終レビューを追加。

## 最終レビュー結果と残課題

最終レビュー時の再検査では、SDPの回帰50件と43サブテスト、UBMの既存タスクゲート479件が成功した。既存dev-graph実走受領書の照合はx86環境で6件成功・3件失敗。C02/node、C04/requirements、C14/decomposeの3件は今回のC07/C09変更により挙動閉包のdigestが古くなったためで、現在コードの実走PASSとは認定しない。元receiptとFAILログは保持し、digestを手で付け替えない。MVP範囲では新actor実走を行わず、harness-86khの残課題としてdraft PRへ記載する。初回arm64環境のrpds読込エラーも原ログとして保持し、x86で再実行した結果と区別する。

