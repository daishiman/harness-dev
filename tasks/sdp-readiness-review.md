---
graph_node_id: "task-sdp-readiness-review"
artifact_kind: "task"
artifact_subtypes: []
title: "初期化前ガード修復と残存証跡を最終レビューして公開する"
project_id: "system-dev-planner"
domain: "development-workflow"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["system-dev-planner", "mvp", "publication-review"]
file_path: "tasks/sdp-readiness-review.md"
template_id: "task"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-03T14:22:42.460658Z"
updated_at: "2026-11-03T14:26:24.611844Z"
depends_on: ["spec-sdp-readiness-review", "arch-sdp-readiness-review"]
related_nodes: ["feature-sdp-readiness-review", "doc-sdp-readiness-review"]
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
classification_reason: "初期化前の操作停止の修復と残存証跡の公開に対応するtask。"
classification_candidates: [{"artifact_kind": "task", "candidate_path": "tasks/sdp-readiness-review.md", "confidence": 0.97}, {"artifact_kind": "document", "candidate_path": "docs/sdp-readiness-review.md", "confidence": 0.03}]
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

B-C07/B-C09の変更と未提出の関連検証証跡を最終レビューし、仕様反映・最小ゲート・対象限定commit・push・main向けdraft PRまで進める。

## 背景

PR88はmainへ統合済み。SDPの未コミット修正とdev-graph/UBMの原検証ログが手元に残っていた。今回の公開作業はharness-86khで追跡する。

## 入力と前提条件

開始時のgit statusとdiff、C07/C09、B-C07/B-C09、未追跡eval-log。originにdevが無いのでmainをbaseとする。権限制約削除と署名付き承認ファイルはローカルに保持する。

## 出力と成果物

修復コード、正規5文書、system-specの影響受領書と品質ゲート、原証跡台帳、対象限定コミットとdraft PR。

## 依存関係

spec-sdp-readiness-reviewとarch-sdp-readiness-reviewに依存する。以前の目標設定実装はPR88でbaseへ取り込み済み。

## 実装対象

C07、C09、既存テスト、README、C07/C09のcomponentとtask契約、SDP採番と生成メタデータ。過去のeval-logは内容を変更せず追加保存する。

## Write scope と競合制約

plugins/system-dev-planner、plugin-plans/system-dev-plannerのC07/C09契約、正規5文書、system-spec/sdp-readiness-review、docs/sdp-readiness-review、.dev-graph/configとgraph/今回receipt、当該版の生成メタデータと未提出eval-logのみ。stageは記録したallowlistで限定する。

## GitHub publication

branch devgraph に本 task の node ID を続けたブランチ、base main、draft。PRに目的・変更・検証・仕様反映・Beads ID・node ID・残課題を記載する。mainへ直接pushせず、自動マージしない。

## 実行手順

1. remote mainをlocal mainへ取り込み、本branchへmergeする。
2. 変更をレビューし、C02で5文書を登録する。
3. B-C07/B-C09のverify、graph strict、script lint、release整合を実行する。
4. SHA付き影響受領書と原証跡台帳を保存する。
5. 対象限定commit/push、draft PRを作りBeadsへ記録する。

## 受入条件

- B-C07/B-C09のverifyが成功する。
- 新規5文書のreadinessがcomplete、strict graphの違反が0。
- releaseとlintが成功する。
- 原ログのSHAが保存台帳と一致する。
- ローカルdeny削除と署名付き承認ファイルをstageせずdraft PRへ提出する。

## 検証方法

python3 -m pytest plugins/system-dev-planner/tests/test_coverage.py plugins/system-dev-planner/tests/test_runtime.py plugins/system-dev-planner/tests/test_system_plan_lock.py -q。C09は同コマンドの先頭2ファイル。graphは--require-canonical-envelope --strict-artifact-readiness。追加で既存dev-graph criteria受領書を再検査し、原actorを再走しない。全体網羅や30思考法の再走は行わない。

## リスクとロールバック

過去FAILが新しい成功と誤解されるリスクは台帳の履歴分類で防ぐ。復旧案内の!入力依存を別ターミナルに変更した。rollbackは公開commitのrevertで行い、既存差分を消さない。

## Handoff

実装の受入はB-C07/B-C09と本タスクの最小ゲート。全残存公開の上位Beads harness-86khにはPRとゲート結果を追記し、上位の未完了項目があれば開いたままにする。新しい13フェーズ計画へ昇格しない。

## 最終レビュー結果と残課題

最終レビュー時の再検査では、SDPの回帰50件と43サブテスト、UBMの既存タスクゲート479件が成功した。既存dev-graph実走受領書の照合はx86環境で6件成功・3件失敗。C02/node、C04/requirements、C14/decomposeの3件は今回のC07/C09変更により挙動閉包のdigestが古くなったためで、現在コードの実走PASSとは認定しない。元receiptとFAILログは保持し、digestを手で付け替えない。MVP範囲では新actor実走を行わず、harness-86khの残課題としてdraft PRへ記載する。初回arm64環境のrpds読込エラーも原ログとして保持し、x86で再実行した結果と区別する。

