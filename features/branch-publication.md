---
graph_node_id: "feature-branch-publication"
artifact_kind: "feature"
artifact_subtypes: []
title: "元ブランチの全残存を新版を保持してPRへまとめる"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "features/branch-publication.md"
template_id: "feature"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "generated", "source_digest": null, "source_path": null, "source_plugin": "dev-graph", "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T05:20:06.808023Z"
depends_on: []
related_nodes: []
resource_scope: []
purpose: "元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。"
goal: "元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。"
scope_in: ["元1440差分の元ブランチ上commitと元HEAD先行11変更の統合", "最新mainと既存PRの元rootへの統合および競合解消", "raw eval-log1063件の元path保持と旧flyer165件のraw保存", "元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認"]
scope_out: ["新規HTTP・DB・認証基盤の追加", "新しい13フェーズ計画の生成・feature/taskの承認やpromotion", "現行flyer1.3.2を元1.3.1で上書きする変更"]
acceptance: ["元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる", "mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない", "元rootの未commit/未追跡0件を最終commit後に確認する", "元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する", "文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する"]
architecture_refs: ["arch-branch-publication"]
parent_feature: null
feature_package_id: null
phase_ref: null
classification_confidence: 1.0
classification_reason: "declared by the C14 macro contract (run-dev-graph-decompose)"
classification_candidates: [{"artifact_kind": "feature", "candidate_path": "features/branch-publication.md", "confidence": 1.0}]
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

元rootの全1440差分そのものをcommit・統合し、mainの新版を保持した同一履歴をPRへ公開できるようにする。

## 到達状態

元1440件をsource commitと統合先で説明でき、元rootがclean、元/PRブランチが同一HEADで両push・同名追跡先を確認できる。

## スコープ

- スコープ内: 元1440差分の元ブランチ上commitと元HEAD先行11変更の統合
- スコープ内: 最新mainと既存PRの元rootへの統合および競合解消
- スコープ内: raw eval-log1063件の元path保持と旧flyer165件のraw保存
- スコープ内: 元rootのclean化・元/PR同一HEAD・両push・同名追跡先の確認
- スコープ外: 新規HTTP・DB・認証基盤の追加
- スコープ外: 新しい13フェーズ計画の生成・feature/taskの承認やpromotion
- スコープ外: 現行flyer1.3.2を元1.3.1で上書きする変更

## 受入

- [ ] 元1440差分の元bytesがsource commitから辿れ、各統合先またはraw保存先を説明できる
- [ ] mainの先行修正を保ち旧flyer entrypointを現行1.3.2へ混在させない
- [ ] 元rootの未commit/未追跡0件を最終commit後に確認する
- [ ] 元ブランチとPRブランチの同一HEAD・両push・元の同名origin追跡先を確認する
- [ ] 文書・feature・taskはdraft/pending・trackerなしで既存harness-86khの追跡を維持する

## アーキテクチャ参照

- `arch-branch-publication`

## 機能間依存

- 先行 feature なし (`depends_on` は空)

## Handoff

元rootでの全1440差分のcommitとmain/PR統合を、親のworktree-integration.jsonへ接続する。親が最終commit・root clean・元/PR同一HEAD・両push・同名追跡先を実測しPR #87へ渡す。本featureは整理用draft、実行追跡は既存harness-86khとし、新13計画・promotion・未取得承認・CI PASSを生成しない。

## 2026年11月2日のCI実走と再開条件

最新main26cc8692はローカルmain経由で統合済みで、6競合を解消したmerge commit9d981850を両branchへ公開し、GitHubのMERGEABLEを確認した。上流cache/historyの原bytesと今回runtime対応を両方保持している。

現行業務sourceに対する初期化・描画・構想分解・状態照会の4試行はfresh独立goalと共通verdictでPASS。C01/C05/C14/C18のcanonical受入testも計4件PASS。描画の判定CLIが4番目の証拠指定を漏らした記録は旧DEGRADEDのまま保持し、同じ実行の全原bytes/SID/token/clock/sourceを残した別judgmentで回収指定だけ訂正した。追加actor起動0であり、新実走を装わない。

source照合は、controllerのstate SHAに束縛した対応表の正確なprovider正本pathとproject aliasを、同namespace・現repo本文SHA・実Readと突合する。private元実体が残る場合の本文改変も拒否し、suffix一致では受理しない。native58件と現物C05受入を確認した。harness-creatorは1.4.60へ正規採番した。

scheduleの既存read-only契約に反してlistがlockをwrite-openしていた不具合を修復した。既存lockをread-onlyで開き共有lockで2ledgerを取得し、context/listでディレクトリや空ファイルを作らない。mutation側の排他lockは維持し、部分store/破損/読取中変更を拒否する。18製品検査と、旧fixtureを同native sandboxで参照する非LLM smokeが成功、旧109entryは全状態不変。変更される被験閉包はschedule/syncだけで、他7対象と既存成功は不変。dev-graphは0.1.31へ正規採番した。

残る再試行はC19の成果物全件提示、nodeの元5Mtoken予算内でのfresh独立監査、requirementsの準備担当所有lockの正規release後入力、scheduleの修復済み参照処理である。元観測・引数・予算を省略/拡張せず、新run/newFXで実施し旧FAIL/BLOCKED/DEGRADEDと原freezeは保持する。C03は同じfixtureと2hookへの信頼許可が質問済み・未回答で、勝手に信頼を有効化しない。最大同時2、原source/goal-seek/実transcript/独立goalを維持し、全CI成功はまだ未確認。

