---
graph_node_id: "feature-sdp-readiness-review"
artifact_kind: "feature"
artifact_subtypes: []
title: "初期化前も通常操作を続けられる実装準備ガード"
project_id: "system-dev-planner"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["system-dev-planner", "mvp", "publication-review"]
file_path: "features/sdp-readiness-review.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T14:22:42.460658Z"
updated_at: "2026-11-03T14:26:24.611844Z"
depends_on: []
related_nodes: ["spec-sdp-readiness-review", "doc-sdp-readiness-review"]
resource_scope: []
purpose: "計画機能の初期化前に通常操作が止まる不具合を直し、計画実行中の安全な検査を保持する"
goal: "有効lockが無くplan_rootsだけが欠けたrepoでは操作でき、不正設定と有効lock下の未準備は拒否される"
scope_in: ["C07の段階的検査", "C09の最小context内部引数", "正規lock root固定", "復旧案内", "未提出の検証証跡保存"]
scope_out: ["ローカル権限制約の削除", "署名付き承認ファイルの公開", "新規有料actor実走", "認証とHTTP API"]
acceptance: ["B-C07/B-C09のverifyが成功する", "C02で登録した5文書のreadinessがcompleteになる", "strict graphと版整合が成功する", "原証跡のFAILを保持し対象allowlistだけをdraft PRへ出す"]
architecture_refs: ["arch-sdp-readiness-review"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/sdp-readiness-review.md", "confidence": 1.0}]
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

計画機能の初期化前に通常操作が止まる不具合を直し、計画実行中の安全な検査を保持する

## 到達状態

有効lockが無くplan_rootsだけが欠けたrepoでは操作でき、不正設定と有効lock下の未準備は拒否される

## スコープ

- スコープ内: C07の段階的検査
- スコープ内: C09の最小context内部引数
- スコープ内: 正規lock root固定
- スコープ内: 復旧案内
- スコープ内: 未提出の検証証跡保存
- スコープ外: ローカル権限制約の削除
- スコープ外: 署名付き承認ファイルの公開
- スコープ外: 新規有料actor実走
- スコープ外: 認証とHTTP API

## 受入

- [ ] B-C07/B-C09のverifyが成功する
- [ ] C02で登録した5文書のreadinessがcompleteになる
- [ ] strict graphと版整合が成功する
- [ ] 原証跡のFAILを保持し対象allowlistだけをdraft PRへ出す

## アーキテクチャ参照

- `arch-sdp-readiness-review`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

今回の既存C07/C09修復の最終レビューと公開はtasks/sdp-readiness-review.mdおよびB-C07/B-C09に従う。5文書はdraftとして登録した。新しい13フェーズ計画の作成や自動昇格は今回行わず、将来の機能拡張時はconfirmed featureと正規package経路を使う。

## 最終レビュー結果と残課題

最終レビュー時の再検査では、SDPの回帰50件と43サブテスト、UBMの既存タスクゲート479件が成功した。既存dev-graph実走受領書の照合はx86環境で6件成功・3件失敗。C02/node、C04/requirements、C14/decomposeの3件は今回のC07/C09変更により挙動閉包のdigestが古くなったためで、現在コードの実走PASSとは認定しない。元receiptとFAILログは保持し、digestを手で付け替えない。MVP範囲では新actor実走を行わず、harness-86khの残課題としてdraft PRへ記載する。初回arm64環境のrpds読込エラーも原ログとして保持し、x86で再実行した結果と区別する。

