---
graph_node_id: "arch-branch-publication"
artifact_kind: "architecture"
artifact_subtypes: ["frontend", "backend"]
title: "全残存統合の単一writerと保存の責務設計"
project_id: "harness"
domain: "delivery"
status: "draft"
priority: null
start_date: null
target_date: null
iteration: null
owners: ["harness-maintainers"]
tags: ["branch-publication", "source-preservation", "existing-contracts"]
file_path: "architecture/branch-publication.md"
template_id: "architecture"
template_version: "1.0.0"
confirmation_status: "draft"
evaluation_status: "pending"
confirmation_evidence: {"evaluated_digest": null, "evaluator": null, "evidence_ref": null}
source_lineage: {"imported_at": null, "origin_kind": "manual", "source_digest": null, "source_path": null, "source_plugin": null, "source_version": null}
created_at: "2026-11-01T21:51:01.228579Z"
updated_at: "2026-11-02T05:20:06.808023Z"
depends_on: ["spec-branch-publication"]
related_nodes: []
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
classification_reason: "C14 macro featureが参照する、既存CLI処理と静的HTMLナビゲーションの責務設計。"
classification_candidates: [{"artifact_kind": "architecture", "candidate_path": "architecture/branch-publication.md", "confidence": 1.0}]
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

# Architecture overview

既存プラグインのCLI・validator・静的HTML生成を維持する。元rootの全1440差分をsource commitとして保存し、mainと既存PRを同じ元ブランチへ統合する。scope修正は作業履歴・公開先・受入条件に限定し、新しいHTTP/DB/製品仕様は作らない。

## Context and drivers

全残存の意味差分をPRへ載せるだけでは、元の作業場所に1440差分が残る。利用者のgs明示により、元rootの実commitとclean化、元/PRの同一履歴と両pushまでを受入へ含める。main先行修正は保持する。

## Goals and non-goals

目標は全件の実装/保存先対応と単一authorityの保持。公開HTTP、DB、新しいmacro→13 task計画、追加tracker起票の基盤は作らない。

## System context and boundaries

元rootをsource commit・main/PR統合・最終commit/clean化の作業場所とする。元ブランチとPRブランチを同一HEADへ揃え、両remote branchと元の同名追跡先を確認する。C02は正規文書/graph、親はGit操作・全件台帳・統合記録、別担当は過去テスト写し188件のdiscovery lintを所有する。

## Container and component view

dev-graphは既存writerとreadiness/parityをつなぎ、UBMはcontext生成→composer→保存前validator、compositionはlint/release、SBBは座標取得→book生成を使う。flyer旧版はruntimeの依存元にせず保存物として隔離する。

## Cross-cutting contracts

[execution-tracker](../plugins/dev-graph/references/execution-tracker-contract.md)、[lifecycle](../plugins/dev-graph/references/github-lifecycle-contract.md)、[C02](../plugins/dev-graph/skills/run-dev-graph-node/SKILL.md) を参照する。parityの正準build()と永続CLIを別の生成authorityに分岐させない。schema・引数の一覧はownerの正本に残す。

## Subtype architecture

合成対象の subtype と該当テンプレート:

- Frontend: 合成済み (`architecture-frontend.md`)
- Backend: 合成済み (`architecture-backend.md`)
- Infrastructure: N/A: subtype 非選択
- Data: N/A: subtype 非選択
- Security: N/A: subtype 非選択

### Frontend architecture

#### Rendering and application pattern

SBBが既存テンプレートから自己完結のまとめHTMLを生成する。新SPA・API client・UI frameworkは追加しない。

#### Routes, screens and navigation

文中とボード画像上の番号から、book生成器が決めた画面・説明の節IDへ移動する。画像全体の拡大と番号リンクを区別する。

#### Component and design-system boundaries

既存bookテンプレートと番号の透明リンク枠を使い、共通配色・表示密度・リンクの意味を別pluginへ複製しない。リンク先を持たない番号の扱いは既存生成器を参照する。

#### State and data flow

render-board-pngが番号の枠と対象情報をboards.jsonへ渡し、build-briefing-bookが有効な行き先を解決する。検査後にボードが変わった場合の古い枠は再利用しない。

#### Backend integration

N/A: HTTP backend・認証session・CSRF/CORSの接続はない。入力は既存ローカル文書・ボード・検査JSONで完結する。

#### Performance and observability

追加の常駐処理やremote取得を増やさない。リンク対象と検査入力の鮮度、生成HTMLと元ボードの対応を既存check/reportで確認する。

#### Frontend verification

[番号ナビゲーション回帰](../plugins/system-briefing-book/tests/test_book_navigation.py) と [book生成回帰](../plugins/system-briefing-book/tests/test_build_briefing_book.py) に接続する。既存guideの表示検査を本変更で再実施したと主張しない。

### Backend architecture

#### Runtime and architecture pattern

Python/Nodeの既存ローカルCLIと静的生成。機能を新serviceへ分割せず、既存ownerの単一writerとvalidatorを再利用する。

#### Domain and module boundaries

graph/contentはC02、parity規則はbuild-parity-manifest.py、tracker突合はC28、鮮度/推薦はC16。UBM・composition・SBBは各plugin内の既存moduleを正本にする。

#### API and service contracts

公開HTTP serviceはない。内部CLI・JSON構成・receiptの変更は [仕様の機能要件](../specs/branch-publication.md) の正本へ参照し、この資料で別versionの契約を定義しない。

#### Data and transaction behavior

C02のpreview→expected_graph_revision→atomic applyとimmutable receiptを利用する。materializeは既存の本文とgraphの所有境界を保ち、link-beadsやconfirm-featureはそれぞれの専用verbに限定する。

#### Async processing

新規queueなし。PR lifecycleは既存C26/C02 consumer、外部の部分失敗は既存pending_retryへ渡す。今回の資料登録では発火させない。

#### Security and resilience

UBM guardは.codex/skills/だけを追加許可し、他の.codex領域を保護する。scope指示を未取得の承認receiptに変換せず、既存外部mutation guardを維持する。

#### Operations and verification

元1440件のsource SHAと統合先、raw eval-log1063件の元path、旧flyer165件のraw保存、C02 revision/artifact SHAを確認する。最終root status、両branch/remote HEAD、元の追跡先は親が実測し、旧sourceのinit PASS・残8対象の履歴と、共有SGA変更後の全9対象の新受入を分けて報告する。現行sourceの新PASS0件・CI未達を維持する。

## Architecture decisions

CLI/transactionとSBB静的ナビゲーションの既存subtypeは維持する。正規5文書のscope修正はC02 updateの同一transactionで行い、status/confirmation/evaluationはdraft/draft/pending、trackerはnoneのまま保つ。featureはmacro_patchで更新し、新planner・13計画・promotionを起動しない。

## Delivery, migration and rollback

source commit d71ac0a6は元path全体の正確な版を保持する。main 76abc53dと既存PR 86adf784を元rootへ統合し、旧flyer165件は [raw保存先](../docs/branch-publication/source-files/plugins/flyer-studio/) へ置いて現行entrypointと分離する。[統合記録](../docs/branch-publication/worktree-integration.json) から最終commit・同一HEAD・両push・追跡先・cleanの証拠へ接続する。過去receiptの当時SHAを改変せずfollowupを追記し、公開後の修正は追加commit/revertで履歴を保つ。

## Risks and verification

元rootを放置したまま保存コピーだけで完了すること、旧flyerを現行runtimeへ混在させること、他者の変更の撤回、過去テストを現CIのPASSへ転用することを防ぐ。source/統合先のSHA、C02 finding、最終status/branch/remote/追跡先を別々に確認する。

## 2026年11月2日のCI実走と再開条件

最新main26cc8692はローカルmain経由で統合済みで、6競合を解消したmerge commit9d981850を両branchへ公開し、GitHubのMERGEABLEを確認した。上流cache/historyの原bytesと今回runtime対応を両方保持している。

現行業務sourceに対する初期化・描画・構想分解・状態照会の4試行はfresh独立goalと共通verdictでPASS。C01/C05/C14/C18のcanonical受入testも計4件PASS。描画の判定CLIが4番目の証拠指定を漏らした記録は旧DEGRADEDのまま保持し、同じ実行の全原bytes/SID/token/clock/sourceを残した別judgmentで回収指定だけ訂正した。追加actor起動0であり、新実走を装わない。

source照合は、controllerのstate SHAに束縛した対応表の正確なprovider正本pathとproject aliasを、同namespace・現repo本文SHA・実Readと突合する。private元実体が残る場合の本文改変も拒否し、suffix一致では受理しない。native58件と現物C05受入を確認した。harness-creatorは1.4.60へ正規採番した。

scheduleの既存read-only契約に反してlistがlockをwrite-openしていた不具合を修復した。既存lockをread-onlyで開き共有lockで2ledgerを取得し、context/listでディレクトリや空ファイルを作らない。mutation側の排他lockは維持し、部分store/破損/読取中変更を拒否する。18製品検査と、旧fixtureを同native sandboxで参照する非LLM smokeが成功、旧109entryは全状態不変。変更される被験閉包はschedule/syncだけで、他7対象と既存成功は不変。dev-graphは0.1.31へ正規採番した。

残る再試行はC19の成果物全件提示、nodeの元5Mtoken予算内でのfresh独立監査、requirementsの準備担当所有lockの正規release後入力、scheduleの修復済み参照処理である。元観測・引数・予算を省略/拡張せず、新run/newFXで実施し旧FAIL/BLOCKED/DEGRADEDと原freezeは保持する。C03は同じfixtureと2hookへの信頼許可が質問済み・未回答で、勝手に信頼を有効化しない。最大同時2、原source/goal-seek/実transcript/独立goalを維持し、全CI成功はまだ未確認。

