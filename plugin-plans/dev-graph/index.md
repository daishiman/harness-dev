---
id: IDX0
title: dev-graph 開発計画 index (main)
shape_marker: task-graph-derived
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: NOT_AVAILABLE
      authentication: ON_INSTALL
      category: Developer Tools
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    applicable: false
    reason: "本 plan は L3 計画までに留め実プラグインを生成しない (goal-spec constraint)。PKG 番号割当は配布登録の意思決定時に distribution.distributable=true への変更と併せて確定する"
  governance:
    applicable: false
    reason: "distribution.distributable=false で配布未登録のため governance runbook 配線は配布判断時に確定する"
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    deploy: run-skill-feedback
    enabled: true
    notion_sink:
      config_key: dev-graph-improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: repo-bundled
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# dev-graph 開発計画 index (main)

> タスクグラフで仕様成果物を一元管理し、BeadsまたはGitHubへbinding別に投影しながら要件定義から実装handoff・完了収束までを担う管理ハーネスを、人間可読な13フェーズと機械可読なcomponent目録の2軸で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `dev-graph` (plan_dir=`plugin-plans/dev-graph/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: ローカルtask graph/Markdownを正本に仕様成果物 (issue/task/specification/architecture/feature/document) を一元管理し、機能 (feature) ごとにpurpose/goal/scope_in/scope_out/acceptance/architecture_refsを保持して機能単位の実行をオーケストレーションしつつ、taskごとにBeadsまたはGitHubを単一実行projectionとして、要件定義・推薦・複数worktree実行・PR merge完了収束までを担う。
- **仕様駆動 (大前提)**: 要件の正本は`goal-spec.json` checklist全件 (現行C1-C56)。仕様と実装がずれたら仕様を先に更新する。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、実タスクの実装コード生成 (既存 capability-build / task-graph build へ handoff)、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=25 component・機械 SSOT) を二重に持たない。
- **二層モデル (マクロ/ミクロ棲み分け)**: dev-graph=マクロ層。1つのプロダクト/プロジェクトを複数の「機能 (feature)」へ分け、各featureへpurpose(なぜ)/goal(到達状態)/scope_in/scope_out/acceptance(確実に実行したい二値)/architecture_refs/機能間depends_onを第一級に保持し機能単位の実行をオーケストレーションする。system-dev-planner=ミクロ層。1つのfeatureノードを入力文脈に受け、その機能を達成する13 lifecycleタスク仕様書+機能内依存DAGを生成するper-featureファクトリ。呼び分けは `want → C14 (マクロ分解: feature+architecture+機能間depends_on生成) → ready featureごとにsystem-dev-plannerを自動起動 (人間による手動`/system-dev-plan`もフォールバック) → promoted taskをparent_feature付きでC02へ登録` の一方向。system-dev-plannerはfeatureを生成せず消費するだけで、program全体のgoal/scopeは扱わない (dev-graph goal-specの責務のまま)。正本は`references/execution-tracker-contract.md` §8 (二層モデル・feature 完了カスケード)。既存のプランナー選定軸 (§0: plugin構築=plugin-dev-planner / システム構築=本ハーネス経路) とは直交する軸として併記する。feature.statusは配下task (parent_feature参照) が全てdoneになったときdoneへロールアップする機械導出projectionで (writerはC26導出→C02単一writer、rollupはC26が§3完了transaction内で評価)、手動done昇格とactive子taskを残したままのfeature closeはfail-closed、feature→task方向の逆流close (featureをcloseしたら配下taskを一括close) はしない (§8.2)。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component (現行 skill×9)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=25 は buildable 実体数で独立に決まる。C24がcaller/worktree context、C25がClaude hook、C26がGitHub lifecycle収束、C27がworktree lease、C28がbeads (bd) bridge、C29がexact-13 packageのatomic登録engineを担う。system development task planハーネスはexternal plugin system-dev-plannerへ一本化し、dev-graph内にbuildable componentを持たない。
- **表記規約**: 要件 id は「要件C43」「goal-spec C44」のように接頭辞付きで表記し、component id (C09/C28 等の 0 埋め 2 桁) と区別する (両者は別名前空間で同形トークンが併存する)。
- **consumer/verb/hoist 記述の SSOT**: どの component が誰に消費されるか (consumer 一覧)・verb→component 対応・plugin-root hoist 対象の列挙は `component-inventory.json` の `depends_on`/`derivation` を唯一の SSOT とし、index/phase の散文では重複記述せず参照のみに留める (drift 防止)。
- **handoff criteria解決**: handoff routeの`id`はinventory component idと1:1であり、`route.id → component-inventory.components[id].quality_gates / harness_coverage / feedback_contract.criteria`をcriteria参照規則とする。criteria本文をhandoffへ複製しない。
- **task graph gateの読み方**: `P01..P13` nodeは非dispatchのphase完了集約markerで、自phaseleafへdepends_onする。実際のdispatch順序はD01→D02→…とD04→全B-Cxx→D06…の明示depends_onが担う。従ってmarker自体を次taskのprerequisiteにせず、各Dxx/B-Cxx acceptanceがgate ownerとなる。
- **単一グラフ構造とタスク実行時の要件導出 (要件 C3)**: タスクグラフは issue/task/specification/architecture/document の各情報を単一のグラフ構造 (ノード+リンク) で保持する。分散した専用ストアを持たず、`run-dev-graph-node` (C02) が唯一の書込み経路としてスキーマ整合性を維持する (例外: C26 の restricted lifecycle projection のみ)。タスク実行時は `run-dev-graph-requirements` (C04) が横断情報から要件定義を導出する。
- **実行トラッカーと公開投影**: C14は1 featureのP01..P13 exact 13 taskをC02へall-or-none登録する。Beadsではfeature=epic、13 task=child issue、機能内edge=blocks。GitHubではfeature=Milestone/Project item、13 task=Issue。外部表示は完了authorityではない。

- **入口と完了authority早見表**: Plugin実体の開発計画はplugin-dev-planner→`task-state.json`→`project-task-beads.py`（実装issue `harness-c1h`完了までfail-closed）。アプリ/システム開発はsystem-dev-planner→dev-graph atomic registration→C28/C12。完了事実はremote default branchのancestorと確認できるlinked PR mergeであり、graph/task Markdownをlocal transactionで確定後、外部Beads closeを最後に冪等実行する。
- **ゼロ依存の静的可視化 (要件 C5)**: `run-dev-graph-render` (C05) が生成する成果物は追加ランタイム依存なしにブラウザで開ける SVG + インライン JS を含む静的 HTML/CSS 1 ファイル。外部 CDN・追加 npm 依存を持たず、リポジトリへコミットまたは CI 生成 (`render-graph-html.py` を CI step で実行) のいずれでも成立する。beads 束縛タスクの live 実行看板には別途 doublej/beads-kanban を採用し (§9)、C05=6 種 artifact 全体の俯瞰スナップショット / beads-kanban=beads task の live 操作、と役割分担する (どちらも完了 authority ではない・authority は PR merged=true)。正本=`references/execution-tracker-contract.md` §9。
- **capability-build への handoff 境界 (要件 C6)**: 本ハーネスの責務は管理 (グラフ保持・同期・可視化) と要件定義導出までであり、実タスクの実装コード生成は行わない。`run-dev-graph-requirements` (C04) が要件定義書を確定した時点で既存の capability-build / task-graph build へ handoff し、本ハーネス側のスキルはそれ以降の実装コード生成を担わない (責務境界は `component-inventory.json` C04 の `boundary` フィールドと `output_contract` に明記)。
- **id+updated_at 競合の同時競合 (open_question 2 の解決)**: 上記タイブレーク規則 (「GitHub 双方向同期と競合解決」節) が正本。C03 の `feedback_contract.criteria` OUT2 が受入テストとして固定する。
- **自然文/task specificationからIssue・Project publication (要件 C7/C27)**: C14は自然文の want をfeature+architecture+機能間depends_onへマクロ分解し (13タスク仕様書への細分解はsystem-dev-planner委譲・C50)、system-dev-planner/`/system-dev-plan`が返すpromoted typed task specsをparent_feature付きでC02 local commit→Issue起票→Project item-add→initial field editの順に実行する。`issue_linkage`と`github_project_linkages`を冪等キーとして再実行時の重複を防ぎ、外部部分失敗はpending retryへ送る。`--dry-run`ではIssue/Project外部write 0件で全publication previewを返す。
- **ready-set 算出と並列実行支援 (要件 C8/C9/C41)**: C15/C16はdepends_onと完了状態に加え、C27のactive worktree leaseを入力にする。resource_scopeまたはleaseが重なるtaskを除外し、独立taskへ`suggested_branch=devgraph/<graph_node_id>`とclaim commandを返す。C09の`worktree claim|heartbeat|park|release|list`がC27を呼び、誰がleaseを更新するかを一意にする。
- **作業コンフリクト最小化 (要件 C10)**: 各タスクノードは `resource_scope` (touches: 触るファイル/ディレクトリ配列) をグラフに保持する (`validate-graph-schema.py` (C11) がスキーマ検証)。`resource_scope` の粒度 (ファイル単位/ディレクトリ単位) と粒度不一致時のフォールバック規則 (open_question 4 の解決) は、ディレクトリ単位を既定としつつノードがファイル単位を明示した場合はファイル単位を優先し、双方混在時は広い方 (ディレクトリ単位) を採用してフォールバックする規則を C11/C16 の設計で固定する。`schedule-graph.py` (C16) は `resource_scope` が重複するノードを同一並列バッチへ入れず conflict-aware にバッチングすることで、同期コンフリクト (id+updated_at) とは別レイヤの「作業」コンフリクトを最小化する。並列バッチの安全性は独立 sub-agent `dev-graph-parallel-safety-verifier` (C17) が proposer≠approver で再検証する。
- **hybrid directory policy (要件 C15)**: 管理ルート直下は `issues/` / `tasks/` / `specs/` / `architecture/` / `features/` / `docs/` の6独立ディレクトリを固定する。物理rootは `artifact_kind`、横断分類は `project_id` / `domain` / `status` / `tags` / `graph_node_id` のfrontmatter metadataが担う。なお feature root はマクロ層 (C14) が want のマクロ分解から生成する機能ノード専用で、C02 のコンテンツ自動分類対象 (issue/task/specification/architecture/document の 5 kind) には含めない (free content からは feature へ分類しない・A3-06 の誤分類回避)。この 5 (自動分類) と 6 (物理root/artifact_kind) の差は意図的で、component_kind の 5 種とも別軸。
- **自動分類routing (要件 C16)**: ユーザーへ保存先を質問しない。C02が内容と任意hintから `artifact_kind/domain/project_id` を推定し、候補path・`classification_confidence`・`classification_reason` を常時previewする。confidence>=0.80かつ第2候補との差>=0.15なら自動確定し、それ未満だけ確認する。
- **段階分割とmigration (要件 C17)**: 各kind rootはflat-first。1 leafが200件を超えた場合のみ `domain`、再超過時は `project_id`、なお超過する場合のみ `YYYY/MM` を加える。自動collapseは禁止し、再配置はdry-run migration manifest、旧→新path、link検証、rollbackを伴う。`graph_node_id` は不変、`file_path` は派生値とする。
- **グラフノード⇄実ファイルの橋渡し**: 全artifactは `file_path` で正規root配下の人間可読Markdownを参照する。本文と分類frontmatterは実ファイル正本、edge/GitHub linkage/tombstoneはグラフ正本、`graph_node_id` は双方で不変、`file_path` はrouting policyから再計算可能なprojectionとする。
- **読取り専用の検索/状態確認 (要件 C11)**: `run-dev-graph-status` (C18) が `graph_node_id/artifact_kind/project_id/domain/status/tags` で全6種を検索し、`file_path`/依存関係をread-only表示する。
- **close/delete の tombstone 双方向伝播 (要件 C12)**: GitHub Issue が close/delete されたとき、`run-dev-graph-sync` (C03) は C02 の『物理削除はしない』境界に従い、ローカルノードを `status: closed|tombstoned` へ遷移させ `closed_at` を記録するソフトデリートとして双方向伝播する (要件 C4 の id+updated_at 競合解決とは別レイヤ)。
- **dry-run/preview と暴発防止 (要件 C13/C30)**: C03/C14は`--dry-run`時にIssue create/update/closeとProject item-add/item-editを全抑止し、alias/field別差分だけをpreviewする。C10は大量Issue/Project mutation、未解決field mapping、permission不足をfail-closedで阻む。
- **修正改善容易性 (要件 C14)**: 全6種の人間可読Markdownを差分編集できる。分類frontmatter編集後はC11がschema/path parityを即時検証し、分類変更はC02のpreview付きmigration経路へ送り、C03/C05が不変 `graph_node_id` を使って追従する。全書換・物理削除・検証なしmoveは禁止する。
- **artifact template正本 (要件 C18-C20)**: `templates/template-contract.json` と共通frontmatter、issue/task/document/specification/API/architecture基底+frontend/backend/infrastructure/data/security subtypeを正本にする。C01が`.dev-graph/templates/`へ冪等scaffold、C02がkind/subtypeを自動合成、C11が空/TODO/条件template欠落をfail-closed検出し`implementation_readiness`と不足sectionを算出する。
- **system-spec-harness引用 (要件 C21)**: 仕様書・architectureの作成/更新はC19が`plugins/system-spec-harness/`の`run-system-spec-elicit`→必要時doc-fetch→`run-system-spec-compile`→独立completeness evaluatorを引用する。dev-graphは同等ロジックを複製せず、source plugin/path/versionと確定状態を保持してC02経由でグラフ登録する。
- **system development task plan (要件 C22/C23・外部依存)**: system-dev-plannerは1 featureをP01..P13 exact 13 executable task specs/13-node intra-feature DAGへ変換する。別の13 phase docsや可変N taskは作らない。正本=`plugin-plans/system-dev-planner/references/feature-execution-package-contract.md`。
- **symlink multi-repo context (要件 C24-C26)**: harness code/assetsは共有sourceからsymlink参照するが、content/config/state authorityは毎回caller repository内に限定する。C24が`--repo-root > trusted project env > git rev-parse --show-toplevel > cwd marker`で候補rootを解決し、host宣言`$CLAUDE_PROJECT_DIR`とのrealpath一致と`.dev-graph/config.json`のrepo相対root containmentを検証する。symlink source/別repo/root外へのcontent read/write、共有cache/lock、broken content linkはfail-closed。harness自身のbroken symlinkは起動前host launcher/installer preflightで扱う。C01は各repoへ冪等initし既存docsを上書きしない。
- **Projects設定とidentity (要件 C28/C29)**: `.dev-graph/config.json`はissue repositoryと複数Projectのalias/owner type/login/project number/default/auto-add/field mappingだけを正本化し、GitHub有効時は`default=true`をexactly oneにする。duplicate aliasはC12がpreflight拒否する。tokenとGitHub node IDは保存せず、C12が実行時解決しrepo-local cacheへ保持する。
- **PR merge完了とProjects収束 (要件 C31-C34)**: 完了authorityはlinked PRがdefault branchへ`merged=true`となった事実であり、closed未mergeは完了にしない。GitHub Issue auto-closeとProjects built-in Doneをremote fast path、C03+C26をrepair/reconciliation経路とする。複数PR all/any、Issue reopen、revert、offline/hook未実行を状態機械で扱う。
- **Claude Code hooks (要件 C35-C38)**: C25はplugin `hooks/hooks.json`を共有既定とし、`.claude/settings.json`は明示fallbackだけに使う。SessionStartは期限到来reconcile、成功済みBashのPostToolUseはasync reconcile、TaskCompletedは`[DG:<graph_node_id>]` leaseをpending_reviewへparkするだけでPR merge前も正常終了し、GitHub doneとは分離する。C01は既存settingsをpreview付きdeep-mergeし、managed/local override、disable、rollbackを診断する。
- **複数worktree/branch (要件 C39-C42)**: C24がworktree root/git common dir/branch/HEAD/default branchを識別し、C27が検証済みcommon dir配下でephemeral lease/event ledgerを共有する。task/spec/graphは各worktree内に留め、feature branchではpending eventだけを記録する。C26はcleanなdefault-branch worktreeだけでdurable lifecycle projectionを更新し、不在/dirty/diverged時はpendingのまま停止する。
- **実行トラッカー抽象化 (要件 C43-C47)**: AIエージェント実行=beads / 人間向け=GitHubのハイブリッド。repo単位選択=`execution_tracker`、ノード単位=`tracker_binding`単一publication authority、PR merged→bd close→task仕様書反映カスケード、C28単一チョークポイント+version window。live 看板は doublej/beads-kanban を採用し (repo-config `execution_tracker.beads.board`、`beads-kanban` 選択時は `server_mode=true` を機械強制・§9)、静的俯瞰は C05、と役割分担する。プランナー選定 (§0: plugin構築=plugin-dev-planner / システム構築=本ハーネス経路) は route-dev-planner router が構想文から機械 dispatch する (`plugin-plans/route-dev-planner/route-dev-planner-contract.md`)。正本=`references/execution-tracker-contract.md`。

### 正規ディレクトリとrouting例

```text
<management-root>/
├── issues/
├── tasks/
├── specs/
├── architecture/
├── features/
└── docs/
```

`dev-graph node "認証方式の変更をADRとして残す"` は保存先入力を求めず、例として `architecture/adr-auth-change.md`、confidence、根拠をpreviewする。低信頼時だけ候補から確認し、確定後にfrontmatterとグラフを同時更新する。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。GitHub 連携は追加トークン管理をせず gh CLI の既存認証のみを利用する。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 10 検査) / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す (詳細手順は焼かない)。
- **コンポーネント目録の所在**: buildable な実体 (skill×9 / sub-agent×4 / slash-command×1 / hook×2 / script×9 = 計 25) は `component-inventory.json` が唯一の SSOT。
- **コンポーネント役割ロスター** (全 25 component。詳細は `component-inventory.json` を正本としこの表は概観のみ):

  | id | kind | 一行役割 | 対応要件 |
  |---|---|---|---|
  | C01 | skill | 6正規root + routing policy + 実ファイル雛形生成、グラフストア初期化 | C15, C17 |
  | C02 | skill | 自動分類preview、低信頼確認、正規pathへのノード/Markdown差分書込み | C3, C14-C17 |
  | C03 | skill | binding別Issue/Beads edge parity + Projects field 3-way同期・conflict/retry・dry-run | C4, C12, C13, C29, C30 |
  | C04 | skill | グラフ情報から要件定義を導出し capability-build へ handoff | C3, C6 |
  | C05 | skill | ゼロ依存の静的 HTML/CSS + SVG 可視化生成 | C5 |
  | C06 | sub-agent | グラフ非循環性/orphan/スキーマ整合性、および decompose 生成ノードの循環/粒度を独立検査 | C3, C7 |
  | C07 | sub-agent | id+updated_at 競合解決、および C14 起票 Issue の冪等性を独立再検証 | C4, C7 |
  | C08 | sub-agent | 要件定義導出の網羅性を独立検証 | C3, C6 |
  | C09 | slash-command | init/node/status/sync/requirements/render/decompose/next/worktree のディスパッチ主要導線 | 全要件 |
  | C10 | hook | 破壊的グラフスキーマ操作 + gh write 暴発を fail-closed で阻むガード | C13 |
  | C11 | script | frontmatter/schema/path parity・routing/migration manifestの決定論検証 | C3, C10, C12, C15-C17 |
  | C12 | script | gh issue/project/api GraphQL bridge、Project ID解決/item find-add-edit/pagination、--dry-run | C4, C13, C27-C30 |
  | C13 | script | 静的 HTML/CSS + SVG 決定論レンダラ | C5 |
  | C14 | skill | 自然文→feature+architecture+機能間depends_on生成 (マクロ分解) + per-feature system-dev-planner起動 + promoted task登録 + Issue起票 + 複数Project publication + dry-run | C7, C13, C27-C30 |
  | C15 | skill | ready-set 算出 + 並列実行可能バッチ提示 (読み取り専用) | C8, C9 |
  | C16 | script | ready-set 算出 + resource_scope 非重複な並列バッチ決定論グルーピング | C8, C9, C10 |
  | C17 | sub-agent | 並列バッチのリソース非重複性を独立再検証 | C9, C10 |
  | C18 | skill | 全6種をmetadataで検索・状態確認 (read-only, 副作用なし) | C11, C15 |
  | C19 | skill | system-spec-harnessを引用し仕様/architectureをlineage付きでグラフ登録 | C21 |
  | C24 | script | symlink source、caller worktree content、git common coordinationを分離しcontextを解決 | C24-C26, C39 |
  | C25 | hook | Claude Code SessionStart/PostToolUse/TaskCompletedを安全・冪等にlifecycle/leaseへ配線 | C35-C38 |
  | C26 | script | linked PR/Issue/Projectとworktree pending eventをdefault branchのtask状態へ収束 | C31-C34, C42 |
  | C27 | script | 複数worktreeのidentity、task lease、heartbeat、TTL reclaim、event ledgerを原子的管理 | C39-C42 |
  | C28 | script | bd (beads) CLI決定論bridge。create/update/dep add/close/ready --jsonを冪等ラップし、external_ref=graph_node_id冪等キーでtracker_binding=beadsノードのbeads_linkage/状態還流を仲介、bd version受容window preflight | C43-C47 |
  | C29 | script | promoted exact-13 packageを検証し、C02へall-or-none登録してimmutable receiptを残す | C22-C23, C27, C52, C56 |

  要件 C22/C23 (system development task plan) はexternal plugin system-dev-plannerのrun-system-dev-planをSkill呼出しで引用して充足する (external_contract_ref: `plugin-plans/system-dev-planner/handoff-run-plugin-dev-plan.json`。ドメイン知識「system development task plan (要件 C22/C23・外部依存)」節が正本)。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required | `plugin_meta.ssot_dedup` |
  | artifact templates | required | `templates/template-contract.json` + `templates/system-plan-contract.json` + Markdown templates |
  | schemas (graph-node) | required | inventory `plugin_level_surfaces.schemas` (`graph_node_id/artifact_kind/project_id/domain/status/tags/file_path/classification_*` + resource/sync fields、C11が検証) |
  | vendor | omitted | component inventory の omitted_reason (plugin-root 共有 script hoist で携帯性を満たす) |
  | MCP/app connector | omitted | component inventory の omitted_reason (gh CLI ベース・MCP 新設なし) |
  | notion_config | omitted | component inventory の omitted_reason (ドメイン DB は GitHub。feedback 受け皿のみ `plugin_meta.feedback_deploy.notion_sink`) |

## 環境ポリシー
- **3状態面を混同しない**: `plan_validation`=L3成果物の構造/4条件検証、`lifecycle_execution`=P01-P13/task nodeの実行状態、`build_execution`=L4 component build状態。`plan_validation=PASS`は他2面を自動で完了へ変更せず、goal checklistの`done:false`・phase未実施・task pendingと両立する。
- **状態遷移owner**: P10が同一plan digestの最終`plan_validation`を承認し、P13はその記録を消費するだけ。L4 buildはhandoffの`build_readiness=blocked`を解消後に別実行され、その証跡だけが`build_execution`を更新する。評価JSONの手編集による昇格は禁止する。
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- **単一 skill 退化の防止**: GitHub 同期 (C03) と要件定義導出 (C04) を意図的に別 skill へ分離し、`couples_with` で同一 phase 直列化を宣言する (単一 skill へ責務を畳み込まない)。同様に、タスク分解/Issue起票 (C14) と ready-set/並列バッチ提示 (C15) も入口機能と推薦機能として責務が異なるため別 skill へ分離し、過剰結合を避けるため `couples_with` は宣言しない (依存 (`depends_on`) のみで疎に連携する)。

## フェーズ一覧

1. P01 — requirements (要件定義) / 未実施
2. P02 — design (設計) / 未実施
3. P03 — design-review (設計レビューゲート) / 未実施
4. P04 — test-design (テスト設計) / 未実施
5. P05 — implementation (実装) / 未実施
6. P06 — test-run (テスト実行) / 未実施
7. P07 — acceptance-criteria (受入基準判定) / 未実施
8. P08 — refactoring (リファクタリング) / 未実施
9. P09 — quality-assurance (品質保証) / 未実施
10. P10 — final-review (最終レビューゲート) / 未実施
11. P11 — evidence (手動テスト検証) / 未実施
12. P12 — documentation (ドキュメント) / 未実施
13. P13 — release (完了/PR・リリース) / 未実施

## 完了チェックリスト
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (2軸直交 / component_kind 5種 / 単一グラフ / binding別authority / 用語集) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 単一skill退化防止) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: `component-inventory.json` がtask graph、directory/routing、Beads/GitHub binding別投影、UI、system-spec引用、multi-repo/worktree contextを記録し、全25 componentがcore規律を携帯する。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。
- [ ] 要件 C2: `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。
- [ ] 要件 C3: タスクグラフが issue/task/specification/architecture/document 情報を単一グラフ構造で保持し、タスク実行時にその情報から要件定義を導出する設計が記載されている。
- [ ] 要件 C4: GitHub Issueはupdated_at、Beadsはstatus/depends_on edge parity、Projects fieldsはupdatedAt hint+snapshot baseで同期し、Statusはlocal_to_projectである。
- [ ] 要件 C5: 追加ランタイム依存なしにブラウザで開ける SVG+インライン JS 可視化済み静的 HTML/CSS がタスクグラフ情報から生成され、リポジトリへコミットまたは CI 生成可能な仕様が index/phase 仕様書に記載されている。
- [ ] 要件 C6: タスク実装が必要になったとき、本ハーネスは既存 capability-build / task-graph build へ handoff し自身は実装コードを生成しない責務境界が index/phase 仕様書に記載されている。
- [ ] 要件 C7: 自然文の want をfeature+architecture+機能間depends_onへマクロ分解し (細タスク化はsystem-dev-planner委譲・C50)、promoted taskをparent_feature付きでatomic local登録後にbinding別Beads/GitHub/noneへpublishするC14が設計されている。
- [ ] 要件 C8: グラフの依存関係と完了状態から「次に着手すべきおすすめタスク」を ready-set として算出・提示する機能 (`run-dev-graph-schedule` C15 + `schedule-graph.py` C16) が設計記載されている。
- [ ] 要件 C9: 依存のない独立タスクを並列/並行実行可能なバッチとして識別し並列実行を支援する機能 (`schedule-graph.py` C16 の conflict-aware バッチング) が設計記載されている。
- [ ] 要件 C10: 各タスクノードが touch するリソース (ファイル/ディレクトリ) スコープ (`resource_scope`) をグラフに保持し、スケジューラがリソース重複する並列タスクを避けることで作業コンフリクトを最小化する設計 (同期コンフリクトの id+updated_at 解決とは別レイヤ) が記載されている。
- [ ] 要件 C11: 全6種をgraph_node_id/artifact_kind/project_id/domain/status/tagsで検索・状態確認する読取り専用経路 (`run-dev-graph-status` C18) が設計されている。
- [ ] 要件 C12: GitHub Issue の close/delete をローカルグラフへ tombstone/status 遷移で双方向伝播する設計 (`run-dev-graph-sync` C03) が index/phase 仕様書に記載されている。
- [ ] 要件 C13: Issue/Project mutationへのdry-run/preview経路と暴発防止guardが設計されている。
- [ ] 要件 C14: 全6種の人間可読Markdownが、差分更新 + frontmatter/path即時検証 + preview付き分類変更により安全に修正改善できる。
- [ ] 要件 C15: `issues/tasks/specs/architecture/features/docs` の6独立rootと、artifact_kindを物理配置・project_id/domain/status/tags/graph_node_idをmetadataとするhybrid directory policyが設計されている。
- [ ] 要件 C16: 保存先指定なしで自動分類し、confidence/reason/候補pathをpreviewして低信頼時だけ確認するroutingが設計されている。
- [ ] 要件 C17: flat-first、leaf 200件超でdomain→project_id→YYYY/MMへ段階分割し、graph_node_id不変のdry-run migration/rollbackが設計されている。
- [ ] 要件 C18: 5 artifact kindの共通frontmatter+本文必須section template正本、init scaffold、node適用、C11 fail-closed検証が設計されている。
- [ ] 要件 C19: architecture 5 subtypeとspecification API/data/error/auth/実装条件の固有templateが設計されている。
- [ ] 要件 C20: implementation-readinessとmissing sectionsを機械判定してhandoffを制御する設計がある。
- [ ] 要件 C21: 仕様書/architecture作成はsystem-spec-harnessを引用し、成果物をlineage付きで取り込む。
- [ ] 要件 C22: external system-dev-planner 引用で充足 — plugin-dev-planner同型の13 phase+workstream inventory+task DAG+handoff+独立評価をsystem開発語彙へ置換した専用harnessは独立plugin system-dev-plannerが所有し、dev-graphはrun-system-dev-planをSkill呼出しで引用する。
- [ ] 要件 C23: external system-dev-planner 引用で充足 — system-spec確定/readiness completeのfail-closed前提はsystem-dev-planner所有のvalidate-system-plan.py/implementation_readiness判定が担い、dev-graph側はC04がreadiness未達handoffを保留する。
- [ ] 要件 C24: symlink code sourceとcaller repository content authorityを分離し、各repo固有docs/config/stateを読むroot resolutionが設計されている。
- [ ] 要件 C25: host project-root一致、containment/cross-read禁止/broken content symlink/host link preflight/multi-repo isolationがfail-closedである。
- [ ] 要件 C26: repo-local config/templates/stateの冪等init、既存docs非上書き、repo相対path、multi-repo fixtureが設計されている。
- [ ] 要件 C27: promoted exact 13 phase taskがexpected/applied=13、phase/node exact-set、共通parent/package receipt後にbinding別trackerへ接続される。
- [ ] 要件 C28: repo-local configがIssue repo、複数Project target、field mapping、auto-add policyを構造化管理しtoken/node IDを正本保存しない。
- [ ] 要件 C29: issue_linkage/github_project_linkagesでIssue/Project itemが冪等1:1追跡される。
- [ ] 要件 C30: Projects field value updatedAtをhint、snapshotをcanonical baseとした3-way conflict、pagination、permission/rate-limit/field drift、partial failure retry、dry-run外部write 0件が設計されている。
- [ ] 要件 C31-C34: linked PRのdefault branch mergeを完了authorityとし、closed未merge/multi-PR/reopen/revertを扱い、native Issue/Projects automationとlocal reconciliationがeventual consistencyを作る。
- [ ] 要件 C32: closed未merge、複数PR all/any、Issue reopen、revertの状態遷移をC26が決定論判定する。
- [ ] 要件 C33: GitHub native Issue close/Project DoneとC03/C26 repair経路が同じcompletion evidenceへ収束する。
- [ ] 要件 C35-C38: plugin/project hook sourceが一意で、SessionStart/PostToolUse/TaskCompletedのevent/security/idempotency契約と非破壊settings導入/rollbackが設計されている。
- [ ] 要件 C36: SessionStartは期限到来reconcile、PostToolUseは成功Bashのasync観測、TaskCompletedは対象leaseをpending_reviewへparkし、identity/owner不整合だけをblockする。
- [ ] 要件 C37: stdin検証、containment、redaction、lock/event ledgerによりinjection・重複・再入を防ぐ。
- [ ] 要件 C39-C42: worktree identity、git-common-dir lease、lease-aware parallel scheduling、default-branch-only completion projectionが設計されている。
- [ ] 要件 C40: graph_node_id leaseのclaim/heartbeat/release/TTL監査reclaimが原子的である。
- [ ] 要件 C41: schedulerがdepends_on/resource_scope/active leaseを合わせて別worktree向けbatchを作る。
- [ ] 要件 C43: `repo-config.schema.json` の `execution_tracker` (mode: beads|github|both + beads: issue_prefix/server_mode/github_mirror) がrepo単位で宣言できる。
- [ ] 要件 C44: beads|noneはlocal_only、githubはissue|issue_and_projectsかつbeads_linkage=nullとし、github+local_only/mode=both+autoをfail-closedにする。
- [ ] 要件 C45: remote default ancestor確認済みPR merge→local graph/task Markdown→completion event→最後にbd closeの再開可能step ledgerが契約化されている。
- [ ] 要件 C46: C28のbd claimをauthority、C27をcontext reservation/saga coordinatorとし部分失敗repairとexecution_contextsを設計している。
- [ ] 要件 C47: bd呼び出しがroute別bridge (systemルート=C28 / pluginルート=project-task-beads.py) に集約され、preflightでbd version受容window (>=1.1.0 <2.0.0) をfail-closedで検査する upstream変動耐性が `references/execution-tracker-contract.md` §7 に記載されている。
- [ ] 要件 C48: pluginルートのbeads直接投影契約 (`references/execution-tracker-contract.md` §6) が実装owner (harness-creator TG-C09並置の`project-task-beads.py`) へのhandoffとして追跡されている。
- [ ] 要件 C56: feature由来taskが`feature_package_id`/`phase_ref`を持ち、P01..P13 exact 13、同一package内前方DAG、exact 13全done+acceptance evidenceだけでfeature rollupとなる。
- [ ] 要件 C49: `graph-node.schema.json` でartifact_kind=featureのノードがpurpose/goal/scope_in/scope_out/acceptance/architecture_refsを条件付きrequiredとして保持する設計が記載されている。
- [ ] 要件 C50: C14 (`run-dev-graph-decompose`) のマクロ分解が自然文の「やりたいこと(大)」からfeatureノード群+architectureノード+機能間depends_onを生成し、13タスク仕様書への細分解は行わない責務境界が記載されている。
- [ ] 要件 C51: ready feature (機能間depends_on充足) ごとにsystem-dev-planner (run-system-dev-plan) を自動起動でき、人間による手動`/system-dev-plan`実行結果も同じ登録経路として受理するフォールバックが設計されている。
- [ ] 要件 C52: system-dev-plannerが生成したpromoted taskがparent_feature (feature ノードのgraph_node_id) を持って当該feature配下のtaskノードとしてC02経由でatomic登録される設計が記載されている。
- [ ] 要件 C53: feature ノード間の機能間依存が既存depends_onフィールドを流用して表現され、C11 (`validate-graph-schema.py`) が非循環性をfail-closedで検査する設計が記載されている。
- [ ] 要件 C54: feature 完了が配下task (parent_feature参照) 全doneからの機械導出 (feature.status=done) としてC26導出→C02単一writerで確定し、feature.statusの手動done昇格とactive子taskを残したままのfeature close/tombstoneがfail-closedになる完了カスケードが `references/execution-tracker-contract.md` §8.2 に記載されC11/C26へ配線されている。
- [ ] 要件 C55: C05が13件中X/Yを表示し、Beadsではfeature epic→13 child issues、GitHubではfeature item/Milestone→13 Issuesへ投影し、task edgeは同一parent/package内に閉じる。

## 受入確認

> 計画は受入基準を契約として焼き、実行は後段buildが担う。purposeの正本は`goal-spec.json`。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| issue/task/specification/architecture/document が単一グラフに一元管理される | 混在入力を連続追加・更新してもschema/frontmatter/path整合性が維持される | node skill (C02) の OUT criterion |
| 初期化が冪等 | 同一リポジトリへ二回 init しても構造が変化しない | init skill (C01) の OUT criterion |
| binding別trackerへ重複なく投影される | Beadsはissue/edge parity、GitHubはIssue/Project、noneはlocal-onlyを各1組維持し、矛盾bindingはwrite 0件で拒否 | C14 + C03 + C11/C12/C28 |
| task specificationをBeads/GitHub/Projectsで管理できる | exact 13 receipt、Beads epic+13 child、GitHub feature+13 Issues、edge parity、partial retry、dry-run write 0件 | C02 + C14 + C03 + C12/C28 |
| PR mergeでlocal task/Beads/Issue/Projectが収束する | remote default ancestor確認済みmergeだけでlocal stepsを確定し、外部close失敗はstep ledgerから再開する | C03 OUT9 + C26/C28 |
| Claude Code hookが安全に自動発火する (要件 C35-C38) | event fixtureで対象操作だけ発火、async判定0件、TaskCompleted後はpending_reviewかつGitHub done 0件、settings二重登録/全書換0件 | C25 + C01 |
| 複数worktreeで衝突なく並列開発できる (要件 C39-C42) | 同一task二重claim 0件、touches重複batch 0件、crash後TTL回復、feature branchの先行done 0件 | C24 + C27 + C15/C16 + C26 |
| グラフ情報から要件定義が導出され capability-build へ委譲される | 要件定義書が生成され本ハーネス自身が実装コードを生成しない | requirements skill (C04) の OUT criterion + 独立 sub-agent (C08) の再検証 |
| ゼロ依存の静的可視化が生成される | 生成 HTML をブラウザで開いた際に追加ランタイム依存なく SVG グラフが表示される | render skill (C05) の OUT criterion |
| 破壊的操作で壊れない | guard hook (C10) がスキーマ破壊的操作を fail-closed で阻む | guard hook (C10) |
| グラフの非循環性/orphan/スキーマ整合性が保たれる | 独立 sub-agent (C06) がグラフ整合性を再検査する | integrity auditor (C06) |
| 自然文/task specificationから最適分解しgraph+Issue+Project化される (要件 C7/C27) | 分解DAGが非循環で、同一入力再実行後もIssue 1件・target Project item各1件 | C14 OUT1/OUT2/OUT4 |
| 依存×完了状態から次のおすすめタスクが提示される (要件 C8) | 推薦タスクが全依存充足済み (ready) である | schedule skill (C15) の OUT1 criterion |
| 独立タスクが並列実行可能バッチとして識別される (要件 C9) | 並列バッチが `schedule-graph.py` (C16) の conflict-aware バッチングで算出される | schedule skill (C15) + `schedule-graph.py` (C16) |
| リソーススコープ重複を避け作業コンフリクトを最小化する (要件 C10) | 並列バッチ内で resource_scope (touches) が重複するノードペアが 0 件 | schedule skill (C15) の OUT2 criterion + 独立 sub-agent (C17) の再検証 |
| 特定ノードを検索し状態確認できる (要件 C11) | 検索/状態表示結果がグラフストアの実状態と一致し、実行後も副作用が生じない | status skill (C18) の OUT1/OUT2 criterion |
| GitHub Issue の close/delete がローカルへ tombstone として伝播する (要件 C12) | close/delete 後の次回同期でローカルノードが物理削除されず status 遷移する | sync skill (C03) の OUT3 criterion |
| 破壊的 gh 操作に dry-run/preview と暴発防止 guard がある (要件 C13) | --dry-run 指定時に GitHub 側書込みが 0 件のままプレビューされる、guard hook (C10) が gh write 暴発を阻む | sync skill (C03) の OUT4 criterion + decompose skill (C14) の OUT3 criterion + guard hook (C10) |
| 管理成果物を直接編集で安全に修正改善できる (要件 C14) | frontmatter編集後にC11がpath parityを検証し、分類変更はpreview付きmigrationへ送られる | C01/C02/C11/C10 |
| 6種を独立directoryとmetadataで分類できる (要件 C15) | init二回後も6 root (issues/tasks/specs/architecture/features/docs) が冪等で、各Markdownに必須frontmatterがある | C01 OUT1 + C11 |
| 保存先を指定せず自動routingできる (要件 C16) | issue/task/spec/architecture/documentの5 kind混在fixtureで高信頼は自動確定、低信頼だけ確認、全件でconfidence/reason/path previewが残る (featureはC14マクロ分解由来で自動分類対象外) | C02 OUT1 |
| 規模増加時だけ段階分割できる (要件 C17) | 199/200/201件境界fixtureで201件時のみdomain partition、移動後もgraph_node_id不変、rollbackでlinkが復元する | C01 routing policy + C02/C03 migration + C11 gate |
| artifact templateが完全適用される (要件 C18-C20) | kind/subtype/API条件別fixtureで必須section欠落0、placeholderのみはincompleteとなりmissing sectionsが表示される | C01/C02/C11/C04 |
| system-spec-harnessを正本として仕様/architectureを構築する (要件 C21) | C19出力にsystem-spec source lineageとconfirmed状態があり、dev-graph内に同等compiler複製がない | C19 OUT1 |
| system development task specsを生成する (要件 C22/C56) | P01..P13 exact 13 task、共通parent/package、13-node DAG、handoff、4条件PASSが揃い12/14件を拒否する | external system-dev-planner package contract + validate-system-plan.py |
| 未完成仕様から実装へ進まない (要件 C23) | readiness未達でtask/Issue/handoff生成0、完成時はtasksノード登録後にC14/C15へ接続する | external system-dev-planner (readiness fail-closed) + C04 OUT2 |
| symlink配布先ごとに固有文書を読む (要件 C24-C26) | 同一symlinkをrepo A/Bから実行し各repoのconfig/docs/stateだけを読み書き、cross-read/writeと絶対path保存0件、project-root不一致/broken content link/outside pathはfail-closed、harness linkはhost preflight | C24 resolver + C01 OUT3 + multi-repo fixture |
| beads束縛タスクがPR mergeでbdまで収束する (要件 C43-C47) | PR merged→C26完了確定→C28 bd close冪等発行→task仕様書frontmatter反映 (C02経由) のカスケードが再実行しても差分0件で、tracker_binding排他 (C44) がfail-closedに検査される | C26 + C28 + C25 + C11 (`references/execution-tracker-contract.md` §3-§4) |
| featureノードが機能単位のマクロ管理・実行オーケストレーションを担う (要件 C49-C53) | featureノードがpurpose/goal/scope_in/scope_out/acceptance/architecture_refsを保持し、C14はfeature+architecture+機能間depends_onまでしか生成せず、ready featureごとの自動system-dev-planner起動と手動`/system-dev-plan`双方の結果がpromoted taskのparent_feature一致で登録され、feature間depends_onの非循環がC11で検査される | C11 (`validate-graph-schema.py`) OUT + C14 (`run-dev-graph-decompose`) OUT6/OUT7 |
| feature完了が忘れられず機械導出で収束する (要件 C54) | 配下task全doneでfeature.status=doneが機械導出され、手動done昇格・active子残しfeature closeがfail-closed、task→feature一方向でwriterはC02単一writer (§8.2) | C26 rollup + C02 + C11 |
| feature進捗が可視化され層分離が保たれる (要件 C55-C56) | 13件中X/Y、Beads epic+13 child、GitHub feature+13 Issues、same-package forward DAG、exact 13 rollupを確認 | C05 + C11 + C26/C28 (§8.2/§8.3/§8.5) |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
