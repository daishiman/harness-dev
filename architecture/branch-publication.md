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
updated_at: "2026-11-02T04:02:36.456667Z"
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
implementation_readiness: {"checked_at": "2026-11-02T04:02:36.456667Z", "missing_sections": [], "status": "complete"}
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

SGAが確認・署名・exact argv実行、HCがnative user turnとtyped外部gate接続を所有する。文書とgraphはC02単一writerでrevision10→11へ同期し、旧receiptを保持する。

利用者の「codexで進めて」に基づき、明示 `--runtime codex` の実受入を進める。省略時のClaude経路を保持し、runtime間のPASS再利用や原JSONLのClaude形式への変換はしない。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md)、[Codex native契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、[外部変更guard契約](../plugins/skill-governance-adapters/references/external-mutation-guard-contract.md)。今回の影響と検証は [Codex native受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) に追記する。

製品契約への追加影響あり。SGAの `hook-confirm` / `pretool` は信頼済みhook commandの `--runtime claude|codex` を受け、既定Claudeを保持する。確認・intent receiptのproducerを署名前にruntimeから選び、Codexは `codex-user-prompt-submit`、Claudeは既存値とする。payloadの自己申告をruntimeに使わず、生成後のreceipt・署名を書き換えない。Codexが実際に渡すcanonical `Bash` / `tool_input.command` と既存deny形式を利用し、架空のBash/UserPromptSubmitを注入しない。HCのtyped外部gate接続は実装・独立確認中で、深度選択とは別の契約として扱う。

正規 `build-artifact-delivery` writerによる23 pluginのprojection更新は共有runnerのSHA同期だけであり、他plugin全体への新機能・権限追加とは区別する。SGAの動作検査33件成功・projection検査1件成功は親担当の報告で、この文書担当が再実行した結果やnative hook実走の成功ではない。最終版番号・release整合・source SHAは採番とfreeze待ちとし、途中の値を確定値へ付け替えない。

共有SGA実装は全9対象のruntime閉包に含まれるため、今回の変更で旧init PASSも現行sourceの合格根拠ではなくなる。必要な新受入はinitを含む全9対象へ更新する。C01のCodex scenarioは旧args・required observations・時間/token予算を逐語保持し、native IDを付けた正本を親が追加済み。旧criteriaの1 passed・8 failedは当時のsourceの実測として保持し、新sourceでも同じ結果だったとは主張しない。canonical criteria receiptは未更新である。

旧source `8c710295` のC05/renderとC19/system-specはnamespace不一致によりnative skill注入0件、正規BLOCKED・goal_fit NOT_EVALUATED・残process 0の履歴を保持する。旧freezeの137ファイル、revision9/10のimmutable receipt、過去のClaude FAIL/DEGRADED/利用上限BLOCKEDと [以前の実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) の原SHAを書き換えない。続く旧 `43a` sourceのBASEci2はC19 fixture準備のみ・actor起動0件で、private原固定を保持する。これらを新sourceの実走やPASSに数えない。

C03/syncは、最終command/sourceをレビュー可能にしてから隔離fixtureの2handlerに限るnative `/hooks` の信頼許可を1回確認する予定で、現在は未提示・未承認。logging wrapperを含む最終定義を固定し、実native UserPromptSubmitと正規guard consumerの到達まで保留する。trust hash・確認receipt・署名を自作せず、generic resumeを外部変更の承認へ読み替えない。fake-ghによるfixture内の変更だけを許し、実GitHub/Beads/Projectsへの接続・一般trust/sandbox bypass・他ユーザー設定の変更を行わない。

新sourceの実受入PASSは0件、CIは未達である。新しい `/private/tmp/harness-codex-ci3-20261102` の試行は最終freeze後に行う。最大同時2と元の反復上限・予算を守り、全scenario、goal-seek実体、原SHA/runtime閉包、fixture-final/freeze、別contextのfresh goalを確認する。成果物の本文提示→実user選択→独立Agentの順と、typed native handoffの回数・順序を記録する。source/private control/raw/公開workdirはactor workspace外とし、書込先はfixtureと完了マーカー用outだけ。Claude固有のSkill/Agent/Stop/権限hookの成立や単一入力での無対話自走と同一視せず、旧PASSのSHA付替え、CI成功・全9対象完了・最終commit/push/PR完了・新promotionの認定を行わない。

