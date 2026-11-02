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
updated_at: "2026-11-02T05:20:06.808023Z"
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
implementation_readiness: {"checked_at": "2026-11-02T05:20:06.808023Z", "missing_sections": [], "status": "complete"}
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

最新main26cc8692はローカルmain経由で統合済みで、6競合を解消したmerge commit9d981850を両branchへ公開し、GitHubのMERGEABLEを確認した。上流cache/historyの原bytesと今回runtime対応を両方保持している。

現行業務sourceに対する初期化・描画・構想分解・状態照会の4試行はfresh独立goalと共通verdictでPASS。C01/C05/C14/C18のcanonical受入testも計4件PASS。描画の判定CLIが4番目の証拠指定を漏らした記録は旧DEGRADEDのまま保持し、同じ実行の全原bytes/SID/token/clock/sourceを残した別judgmentで回収指定だけ訂正した。追加actor起動0であり、新実走を装わない。

source照合は、controllerのstate SHAに束縛した対応表の正確なprovider正本pathとproject aliasを、同namespace・現repo本文SHA・実Readと突合する。private元実体が残る場合の本文改変も拒否し、suffix一致では受理しない。native58件と現物C05受入を確認した。harness-creatorは1.4.60へ正規採番した。

scheduleの既存read-only契約に反してlistがlockをwrite-openしていた不具合を修復した。既存lockをread-onlyで開き共有lockで2ledgerを取得し、context/listでディレクトリや空ファイルを作らない。mutation側の排他lockは維持し、部分store/破損/読取中変更を拒否する。18製品検査と、旧fixtureを同native sandboxで参照する非LLM smokeが成功、旧109entryは全状態不変。変更される被験閉包はschedule/syncだけで、他7対象と既存成功は不変。dev-graphは0.1.31へ正規採番した。

残る再試行はC19の成果物全件提示、nodeの元5Mtoken予算内でのfresh独立監査、requirementsの準備担当所有lockの正規release後入力、scheduleの修復済み参照処理である。元観測・引数・予算を省略/拡張せず、新run/newFXで実施し旧FAIL/BLOCKED/DEGRADEDと原freezeは保持する。C03は同じfixtureと2hookへの信頼許可が質問済み・未回答で、勝手に信頼を有効化しない。最大同時2、原source/goal-seek/実transcript/独立goalを維持し、全CI成功はまだ未確認。

