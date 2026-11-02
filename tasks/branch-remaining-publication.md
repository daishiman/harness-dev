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
updated_at: "2026-11-02T07:05:48.789253Z"
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
implementation_readiness: {"checked_at": "2026-11-02T07:05:48.789253Z", "missing_sections": [], "status": "complete"}
---

# 目的

元rootの全1440差分そのものを元ブランチ上でcommitし、最新mainと既存PRの修正を統合した同一HEADを元ブランチとPR #87のブランチへ公開して、元rootをcleanにする。

## 背景

利用者がgsで確定したscopeは、保存用コピーをPRへ載せるだけでなく、元の作業場所の全残存をcommitして公開することまで含む。以前の「PR作業ツリーだけ」「元worktreeを変更しない」という制約は、この確定scopeに置き換える。

## 入力と前提条件

元HEAD 8c1eb6c8の全1440差分を記録したsource commit d71ac0a6、最新main 76abc53d、既存PRの86adf784、統合時HEAD a4bc8d14を入力にする。67件と10件の競合解消およびsource bytesの照合は [統合記録](../docs/branch-publication/worktree-integration.json) に接続する。古い元版でmainの修正を戻さない。

## 出力と成果物

全元差分を保持するsource commitと統合履歴、元path/統合先の全件対応表、raw eval-logの元path保持、flyer旧追加165件のraw保存、C02正規文書と追記の影響受領書、元rootのclean確認、同一HEADの2ブランチと各push/追跡先の記録。

## 依存関係

[guideタスク](gdg-review.md) と関連するが、他者のBeadsを無断で完了にしない。通常taskのpromotion writer不在により本taskはdraftを維持し、実行追跡は既存harness-86khの拡張scopeに集約する。過去テスト写し188件のdiscovery lint対応は別担当の変更を待ち、ここで編集しない。

## 実装対象

dev-graph、UBM、harness-creator、governance lint、release writer、flyer、SBB、guide関連と過去証跡を含む全残存。raw eval-log1063件は元pathを保持し、flyer旧追加165件はdocs/branch-publication/source-files/plugins/flyer-studio/へraw保存する。元path全体の正確な版はsource commitにも保持する。

## Write scope と競合制約

元root /Users/dm/dev/dev/個人開発/harness を統合・commit・clean化の対象にする。元ブランチへ最新mainとレビュー済みPRを統合し、最後にPRブランチを同じHEADへ揃える。他の実行担当と所有を分担し、mainの新版と他者の変更を戻さない。C02文書/graph/receiptは単一writerで更新する。

## GitHub publication

PR #87はhead devgraph/task-gdg-review、base mainを維持する。元ブランチ devgraph/package-artifacts-and-feature-promotion とPRブランチを同一HEADへ揃え、両方をpushする。元ブランチの追跡先は同名のoriginブランチへ設定する。完了は実際のHEAD・remote到達・追跡先・元rootのgit statusで確認し、CI PASSやmergeは未確認なら主張しない。

## 実行手順

1. 元の1440差分と先行11変更を棚卸しする。2. 元ブランチで1440件をsource commitとして記録する。3. 最新remote mainと既存PRを元ブランチへ取り込み、mainの新修正を保って競合を解消する。4. raw証跡とflyer旧版の保存先を照合する。5. C02で確定scopeへ文書を更新し、最小検証と別担当のlint対応を集約する。6. 最終変更をcommitしてrootをcleanにする。7. PRブランチを同一HEADへ進めて両方pushし、元ブランチの追跡先と公開結果を記録する。既に実施済みの段階は統合記録を参照し、未実施を成功扱いにしない。

## 受入条件

元1440差分全件の元bytesがsource commitに保存され、各項目の現行統合先またはraw保存先を説明できる。mainの新修正を保持し、元rootの未commit/未追跡が0件となる。元ブランチとPRブランチが同一HEADで、両remote branchへのpushと元ブランチの同名追跡先を確認できる。文書/feature/taskはdraft・trackerなしを維持し、既存harness-86khで追跡する。

## 検証方法

[全件台帳](../docs/branch-publication/manifest.json) と [元worktree統合記録](../docs/branch-publication/worktree-integration.json) のsource SHA・元path・統合先を照合する。対象別の最小回帰、C02 preview/apply/C11、ファイルSHA、最終のroot statusとlocal/remote HEAD・追跡先を別々に記録する。旧sourceでのinit PASSと残8対象の履歴は保持する。共有SGA実装変更後はinitを含む全9対象の新受入が必要であり、現行PASSやCI成功へ読み替えず、全30思考法は再走しない。

## リスクとロールバック

旧flyerのentrypointを現行1.3.2へ混在させず、旧版はraw保存とsource commitで辿れるようにする。他者の変更を撤回しない。公開後の修正は追加commit/revertで履歴を残す。古いreceiptや過去テストのSHAを現在版のPASSへ書き換えない。

## Handoff

親へC02 revision/immutable receipt/artifact SHAを渡す。最終commit・両branchのHEAD一致・両push・同名追跡先・root cleanの実測は親が統合記録へ追記する。本taskのdraft保持と既存harness-86khの追跡、未取得承認・promotion・CI PASSを作らない条件を維持する。

## 2026年11月2日のCI実走と再開条件

完了済みはmain統合・競合6件解消と、現行sourceの5件の独立実走/canonical受入である。残りは、requirementsの矛盾のない新入力での実走、nodeの元5Mtoken/1200秒内での実走、C19のCodex監査経路での実走、C03の信頼許可後の実走である。最大同時2を維持する。

修復後の独立design review4判定はPASS。HC1.4.61/SSH0.1.26へ正規採番し、業務閉包の変更はC19だけ、他8対象は一致した。新しいrequirements入力は初回promotion前から要件・13工程・参照・証跡scopeを整合させた準備データであり、live PASSではない。C03の試行フォルダと2hookへの信頼許可は質問済み・未回答である。許可と無関係な修復は継続する。全受入/CIを確認し、対象ファイルのcommit/push・両branch同一HEAD・全remote treeを実測する。旧FAIL/BLOCKED/DEGRADEDと原freezeは履歴として保持する。未実走、未回収、未取得の許可をPASSへ置き換えない。

