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
updated_at: "2026-11-02T07:05:48.789253Z"
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
implementation_readiness: {"checked_at": "2026-11-02T07:05:48.789253Z", "missing_sections": [], "status": "complete"}
---

# 目的

元rootの全残存を実際にcommitし、最新main・既存PRを統合した同一履歴を公開してrootをcleanにする作業の参照先をまとめる。

## 対象読者

統合を担当するmaintainer、PR reviewer、元版や素材の保存先を確かめる利用者。

## 要約

元の1440差分はsource commit d71ac0a6へ記録し、mainとレビュー済みPRを元ブランチで統合する。raw eval-log1063件を元pathで保持し、flyer旧追加165件はdocs/branch-publication/source-files/plugins/flyer-studio/にraw保存して現行1.3.2を戻さない。最後に元ブランチとPRブランチを同一HEADへ揃えて両方をpushし、元rootのcleanを確認する。

## 本文

[全件台帳](branch-publication/manifest.json) と [worktree統合記録](branch-publication/worktree-integration.json) が、元rootの1440 status entries・元HEADの先行11変更・source commitのbytes・現行の統合先を対応付ける。source commitは元pathの正確な版を保持する。raw eval-logは元path、旧flyer165ファイルは [raw保存先](branch-publication/source-files/plugins/flyer-studio/) に置く。従来の元版362ファイルのZIP保存と [復元script](branch-publication/restore-source.py) も過去の保存証拠として残す。

正規の説明は [仕様](../specs/branch-publication.md)、[責務設計](../architecture/branch-publication.md)、[macro feature](../features/branch-publication.md) を参照する。既存製品のCLI・描画・文書契約は各pluginの正本に残し、今回のscope修正で新しいHTTP/DB/製品仕様は追加しない。

## 決定事項

「PR作業ツリーだけ」「元worktreeを変更しない」という旧条件を、元rootで全残存をcommit・統合・clean化する確定scopeへ置き換える。文書/feature/taskはdraft/pending・tracker_binding noneを維持し、新しい13計画へ昇格しない。[draft task](../tasks/branch-remaining-publication.md) は既存harness-86khの拡張scopeで追跡する。未取得の承認、promotion、CI PASSは作らない。

## 運用・更新方法

親が最終commit後に元ブランチ devgraph/package-artifacts-and-feature-promotion とPRブランチ devgraph/task-gdg-reviewを同一HEADへ揃え、両remote branchへpushし、元ブランチの同名origin追跡先とroot cleanを実測する。対応先不明0件と、commit/push/CI/mergeの達成は別々に記録する。C02文書を直接編集せずpreview/applyを通し、古いreceiptの当時SHAは書き換えずfollowupを追記する。

## 関連資料

- [確定scopeの統合タスク](../tasks/branch-remaining-publication.md)
- [元worktree統合記録](branch-publication/worktree-integration.json)
- [全残存の案内](branch-publication/README.md)
- [当時のtask契約評価](branch-publication/task-contract-review.json)：当時SHAの評価であり、今回修正したscopeへ自動流用しない。
- [system-spec影響索引](../system-spec/branch-publication/README.md)
- [仕様影響受領書と追記](../system-spec/branch-publication/spec-impact-receipt.json)
- [既存guide資料](../system-spec/guide-doc-generator/README.md)

## 変更履歴

2026-11-02: C02で4資料を初回draft登録。その後、利用者のgs明示により元1440差分そのもののcommit、元rootの統合・clean化、2ブランチの同一HEADと両pushを受入へ追加。過去receiptの当時SHAは保持し、新しいC02 updateの証拠をfollowupへ追記する。

## 2026年11月2日のCI実走と再開条件

最新main 26cc8692はlocal main経由で統合済み。PR #87はMERGEABLEで、競合6件は解消した。CI全体はまだ成功していない。初期化・描画・構想分解・状態照会・スケジュールの5件はfresh独立goal・共通verdict・canonical再受入までPASS。スケジュールの原DEGRADEDは評価JSON形式エラーの履歴として残し、同じ独立判断の厳密5キー版を別judgmentへ渡して訂正した。新actor・時計reset・予算延長は0。

残る作業は[タスク](../tasks/branch-remaining-publication.md)、検証の条件は[仕様](../specs/branch-publication.md)、記録の経路は[設計](../architecture/branch-publication.md)を参照する。旧FAIL/BLOCKED/DEGRADEDと原freezeは履歴として保持する。未実走、未回収、未取得の許可をPASSへ置き換えない。

