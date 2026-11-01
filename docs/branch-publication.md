---
graph_node_id: "doc-branch-publication"
artifact_kind: "document"
artifact_subtypes: []
title: "元ブランチ全残存の統合・保存先の案内"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "docs/branch-publication.md"
template_id: "document"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-01T21:51:01.228579Z"
depends_on: []
related_nodes: ["spec-branch-publication", "arch-branch-publication", "feature-branch-publication", "task-branch-remaining-publication"]
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
classification_reason: "元ブランチ全残存の統合を、既存責務契約への参照と実パスの対応で記録する正規document。"
classification_candidates: [{"artifact_kind": "document", "candidate_path": "docs/branch-publication.md", "confidence": 0.99}, {"artifact_kind": "specification", "candidate_path": "specs/branch-publication.md", "confidence": 0.01}]
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

元ブランチの全残存をPR #87へ統合する際の実装・保存・検証の参照先をまとめる。

## 対象読者

統合を担当するmaintainer、PR reviewer、元版や素材の保存先を確かめる利用者。

## 要約

mainの修正を保持し、dev-graph・UBM・composition・SBBの差分は既存ownerの契約へ接続する。flyerは現行1.3.2を維持し、元1.3.1と素材42・検証85・計画25をsource snapshotとして保存する。

## 本文

[全件台帳](branch-publication/manifest.json) が元rootの1440 status entriesと元HEADの先行11変更を分類する。元版362ファイルは台帳のSHA付きsource-evidenceから [restore-source.py](branch-publication/restore-source.py) で復元する。現行pluginのファイルへ旧版を丸ごと戻さない。

正規の説明は [仕様](../specs/branch-publication.md)、[責務設計](../architecture/branch-publication.md)、[macro feature](../features/branch-publication.md) を参照する。dev-graphのmaterialize/confirm-feature/link-beads/planned_features、parity単一builder、UBM3シート・Codex guard、JSON composition、SBB番号クリックの実行契約は各pluginの正本に残す。

## 決定事項

新しいHTTP/DB/認証基盤は作らない。本資料4件はdraft/pending・tracker_binding noneで保持し、新しい13計画へ昇格しない。通常taskのpromotion writer不在を回避せず [draft task](../tasks/branch-remaining-publication.md) を保持し、既存harness-86khの拡張scopeで追跡する。未取得の承認は作らない。

## 運用・更新方法

manifestの各元差分に反映/統合/元版保存/一時状態の扱いと実パスを記録し、未対応0件を別途検証する。版採番・push・CI・PR状態は親の実行証跡で確認する。C02文書の変更は直接編集せず同writerのpreview/applyを通す。

## 関連資料

- [統合タスク](../tasks/branch-remaining-publication.md)
- [task契約の独立評価](branch-publication/task-contract-review.json)
- [system-spec影響索引](../system-spec/branch-publication/README.md)
- [仕様影響受領書](../system-spec/branch-publication/spec-impact-receipt.json)
- [既存guide資料](../system-spec/guide-doc-generator/README.md)

## 変更履歴

2026-11-02: 全残存統合の参照資料をC02単一writerで初回draft登録する。本文とreadinessが揃っても、公開・merge・タスクpromotionの完了を意味しない。

