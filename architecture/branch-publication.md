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
updated_at: "2026-11-02T01:37:06.780592Z"
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
implementation_readiness: {"checked_at": "2026-11-02T01:37:06.780592Z", "missing_sections": [], "status": "complete"}
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

元1440件のsource SHAと統合先、raw eval-log1063件の元path、旧flyer165件のraw保存、C02 revision/artifact SHAを確認する。最終root status、両branch/remote HEAD、元の追跡先は親が実測し、initの有効PASSと、承認済み残り8対象の未達（fresh FAIL/DEGRADEDが2、利用上限で停止2、未起動4）、CI失敗とは分けて報告する。

## Architecture decisions

CLI/transactionとSBB静的ナビゲーションの既存subtypeは維持する。正規5文書のscope修正はC02 updateの同一transactionで行い、status/confirmation/evaluationはdraft/draft/pending、trackerはnoneのまま保つ。featureはmacro_patchで更新し、新planner・13計画・promotionを起動しない。

## Delivery, migration and rollback

source commit d71ac0a6は元path全体の正確な版を保持する。main 76abc53dと既存PR 86adf784を元rootへ統合し、旧flyer165件は [raw保存先](../docs/branch-publication/source-files/plugins/flyer-studio/) へ置いて現行entrypointと分離する。[統合記録](../docs/branch-publication/worktree-integration.json) から最終commit・同一HEAD・両push・追跡先・cleanの証拠へ接続する。過去receiptの当時SHAを改変せずfollowupを追記し、公開後の修正は追加commit/revertで履歴を保つ。

## Risks and verification

元rootを放置したまま保存コピーだけで完了すること、旧flyerを現行runtimeへ混在させること、他者の変更の撤回、過去テストを現CIのPASSへ転用することを防ぐ。source/統合先のSHA、C02 finding、最終status/branch/remote/追跡先を別々に確認する。

## 2026年11月2日のCI実走と再開条件

C02の単一writerとC11の既存責務境界を利用し、新しいwriter・controller・検査authorityを作らない。新実走のFAILと外部利用上限による未実走を分離し、凍結後の証跡を改変せず次回候補へ渡す。revision6のimmutable receiptを保持し、[今回の受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json)へrevision7とartifact SHAを記録する。

利用者のokにより、initの有効PASSを維持し、残り8対象のexhaustive実走が承認された。同時実行上限は2。今回のsource基準は848a2b2fで、実装・正本Skill・版の追加変更はない。CI結果は974 passed・8 failed・69 subtests passed、governanceはPASS。CI成功や8対象の全件完了、今回のcommit/push完了を示すものではない。

C14/decomposeとC02/nodeの新実走は主要観測を満たしたが、fresh独立評価はtask手順未達でFAIL、最終verdictはDEGRADED。decomposeはassistantによる実pathとbytes digestの提示順序および必要責務promptの事前読込、nodeは同じSkillによるupdate/feature-add再呼出しと提示順序が未達。自己申告PASSを受入へ流用しない。

C19/system-specとC05/renderはClaude週次利用上限（2026年11月6日17時、Asia/Tokyo解除予定）で停止し、Skill/tool呼出しは0件。C19/system-specとC05/renderは--blockedの正規finalizerとscoped reapで終了し、overall BLOCKED・goal_fit NOT_EVALUATEDとなった。全8runの残sessionは0。private全体は/private/tmp/harness-ci-full-20261102T010423-ci-fullへ非破壊moveし、10801file・9symlink・3365dirのtreeSHAは移動前後とも5dffd9e176643f20f547be5917aff95b8bce113db8c994ce19666430d805e0eeで一致した。4起動run（decompose・node・render・system-spec）のprivate-evidence-relocation.jsonに照合証跡を保持する。requirements・schedule・status・syncの4対象は未起動・未実走。追加課金、account/model切替や権限制約の回避は行わず、上限解除後も最大2の既存条件と予算を維持して再開する。

詳細な結果・証跡digest・C02/C11検証は受領書に記録する。全体の公開作業の成功条件と過去の履歴は維持する。

親が現行criteria9本を再検査し1 passed・8 failedを確認した（この文書担当による再実行ではない）。canonical criteria receiptは今回更新せず、古いPASSを現行の合格証拠として使わない。

