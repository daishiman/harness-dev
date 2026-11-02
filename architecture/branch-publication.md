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
updated_at: "2026-11-02T02:21:20.724109Z"
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
implementation_readiness: {"checked_at": "2026-11-02T02:21:20.724109Z", "missing_sections": [], "status": "complete"}
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

既存 live-trial の planner / verdict / schema に runtime 分岐を接続し、Codex runner と原 rollout parser を専用経路として加える。文書と graph は C02 単一 writer と C11 を利用し、revision8 の immutable receipt を保持して revision9 に更新する。

利用者の「codexで進めて」に基づき、承認済みの残8対象を明示的な `--runtime codex` で検証するため、harness-creator の live-trial 契約を追加している。省略時は既存の Claude 経路を維持し、runtime をまたいだ PASS 再利用は禁止する。旧 runtime 未記録の証跡は Claude として保持する。正本は [live-trial Skill](../plugins/harness-creator/skills/run-skill-live-trial/SKILL.md) と [Codex native 契約](../plugins/harness-creator/skills/run-skill-live-trial/references/codex-live-trial.md)、今回の受領書は [Codex native 受入受領書](../system-spec/branch-publication/codex-native-acceptance-receipt.json) とする。

今回の仕様影響は製品契約への影響あり。native `exec` / 同一 session の `exec resume`、原 rollout parser、runtime 別の schema・挙動閉包・再利用・CLI 引数を追加する。native の実際の skill 注入と成功した全文 Read を source bytes に束縛し、実 model・親子 session・終了・累積 token・実 user turn を原ログから検査する。Claude の `Skill` / `Agent` / Stop / 権限 hook と同一のイベントや同一能力とは主張しない。

複数 operation は、宣言済みの順序付き native handoff と checkpoint を controller が照合し、各操作を実 user turn で渡す。入力回数・順序を記録し、単一入力による自走や救済 nudge と区別する。最小成果物の実 path・bytes SHA・開き方・深度四択を assistant 本文で提示し、実 user turn の standard 応答前に選択記録や Agent 評価へ進めない。native hook や正規 guard consumer の未到達を、generic resume や自作 receipt で承認済みに置き換えない。

書込み権限は fresh fixture と完了マーカー用の `workdir/out` に限定する。source provider・private control/raw・公開 workdir を actor workspace の外へ分離し、workspace・tmp・source・private の境界と書込み先の交差を検査する。HOME・CODEX_HOME・auth・利用者設定を転用せず、sandbox を無効化しない。既存 Claude の schema・digest・受入規則は維持する。

現時点の Codex 実走は残8対象すべて0件。C03/sync は必要な native hook が未確認・未発火のため保留で、他7対象は準備済みである。準備・unit test・文書登録を実走 PASS に数えない。source の最終隔離修正・独立 review、最終 source SHA・試験結果・版採番は親の追記待ち。harness-creator 1.4.56 / dev-graph 0.1.29 は採番予定であり、本受領書は採番完了を認定しない。

再開時も同時上限2、scenario 全観測、時間/token 予算、goal-seek 実体、原 SHA と runtime 閉包、fixture-final/freeze、別 context の fresh goal 評価を維持する。作者・runner は goal PASS を作らない。過去の C14/decompose と C02/node の fresh FAIL・最終 DEGRADED、C19/system-spec と C05/render の利用上限 BLOCKED、未起動4対象、および private relocation の照合は [以前の CI 実走受領書](../system-spec/branch-publication/ci-exhaustive-attempt-receipt.json) に不変の履歴として残す。Codex への切替で上書きしない。

現行 criteria は親の前回確認で1 passed・8 failed、CI の残8対象は未達のまま。canonical criteria receipt は今回更新せず、古い PASS を現行の合格証拠に流用しない。CI 成功・全8対象完了・commit/push・PR 完了・feature/task の承認や promotion は主張しない。

