---
id: IDX0
title: system-dev-planner 開発計画 index (main)
shape_marker: task-graph-derived
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: false
    policy:
      installation: NOT_AVAILABLE
      authentication: ON_USE
      category: Internal Tooling
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
    mode: multi-repository-symlink
  pkg_contract:
    applicable: false
    reason: "plugin-dev-planner 同型の内部ハーネスであり配布対象外 (NEVER_DISTRIBUTE 相当) のため PKG-001..015 の配布契約検査は非該当"
  governance:
    applicable: false
    reason: "harness-creator 側の評価 rubric Runbook (run-skill-rubric-governance) を所有/変更しないため非該当"
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    deploy: run-skill-feedback
    enabled: true
    notion_sink:
      config_key: improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: repo-bundled
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
  portability:
    caller_repository_authority: true
    config_path: .dev-graph/config.json
    stored_paths: repository-relative-only
    realpath_containment: required
    cross_repository_reads: forbidden
---

# system-dev-planner 開発計画 index (main)

> plugin-dev-planner と同型のゴールシーク型計画フロー (goal-spec 確定 → workstream/component 分解 → task-spec 生成 → 独立評価 → task-graph 射影 → build handoff) を、プラグイン構築ではなくシステム開発向けに写像した独立ハーネス system-dev-planner を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

> **本 inventory の `component_kind` と、system-dev-planner が生成する `workstream-inventory.json` の `workstream_kind`/`build_target_kind` は別スキーマである**。前者は system-dev-planner 自身の build 軸 (skill/sub-agent/slash-command/hook/script の標準 5 種)、後者は system-dev-planner が実行時に生成するタスク仕様書の分類軸 (workstream_kind) とビルド対象語彙の保持分 (build_target_kind) であり、詳細は `references/workstream-inventory-schema-design.md` を正本とする (P02)。

## 基本定義
- **表記規約**: 要件 id は「要件C9」「goal-spec C10」のように接頭辞付きで表記し、component id (C09/C10 等の 0 埋め 2 桁) と区別する。
- **プラグイン slug**: `system-dev-planner` (plan_dir=`plugin-plans/system-dev-planner/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: dev-graph (マクロ層) が保持する 1 つの feature ノードを入力文脈に受け、system-spec-harness の確定成果物を引用しながら task-spec + task-graph が implementation_readiness を満たして確定した状態を、plugin-dev-planner 同型のゴールシーク型ライフサイクルで機械保証する per-feature ミクロファクトリ。
- **仕様駆動 (大前提)**: 要件の正本は`goal-spec.json` checklist C1-C16。L3 plugin planの13 phaseとruntime exact 13 task packageを別レイヤとして検証する。
- **呼び出し元との境界**: 呼び出し元 `plugin-plans/dev-graph/` からの引用入力・呼出しインターフェースは goal-spec checklist C4 由来。内容構築 (仕様書/アーキテクチャの新規作成) は常に `plugins/system-spec-harness/` へ委譲し複製しない (checklist C3/C8)。
- **プランナー選定 (入口の二者択一)**: 構築対象が `plugins/<slug>/` 配下の Claude Code plugin 実体なら plugin-dev-planner (`/plugin-dev-plan`) の管轄であり、そのタスクは `task-state.json` から beads へ直接投影する (dev-graph 非経由)。導入先リポジトリのアプリケーション/システムコードの構築のみが本 plugin (system-dev-planner) の管轄で、typed task spec → dev-graph atomic 登録 → execution-tracker contract の経路をとる。正本 = dev-graph plan の `references/execution-tracker-contract.md` §0 (二重登録禁止)。
- **二層モデル (マクロ/ミクロ棲み分け、上記選定軸と直交)**: システム構築ルートの内部は want→dev-graph C14 マクロ分解→feature ノード生成→per-feature に本 plugin (system-dev-planner) 起動→13 タスク仕様書+機能内依存 DAG 生成→dev-graph へ parent_feature 登録、という二層構造をとる。dev-graph はマクロ層 (feature/architecture/機能間依存の保持 + 実行オーケストレーション) を担い、system-dev-planner はミクロ層 (1 feature → 13 タスク仕様書) を担う。system-dev-planner は feature 自体を生成せず (dev-graph 側の実体)、feature を消費して細分解するのみ。正本 = dev-graph plan の `references/execution-tracker-contract.md` §8 (二層モデル・feature 完了カスケード。マクロ/ミクロ責務境界・per-feature 起動・parent_feature・feature 完了ロールアップ・architecture_refs 解決境界を集約した durable 正本で、improvement-handoff-macro.json は transient 入力ゆえ正本にしない)。上記のプラグイン構築 vs システム構築の選定軸 (plugin 実体か否か) とは直交する軸である。
- **スコープ (含む)**: system-dev-planner自身のL3 plugin plan (本index/13 phase/component inventory) と、runtime出力である1 feature→P01..P13 exact 13 executable task specs/13-node DAG/feature-package/登録receipt契約。両者の13を混同しない。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、system-spec-harness が担う仕様書内容構築、task-graph build/capability-build が担う実装コード生成、PR/配布登録、feature ノード自体の生成および program 全体の goal/scope の保持 (dev-graph マクロ層の責務)。

## ドメイン知識
- **メタ/実行の分離**: 本pluginをbuildするL3計画は13 phase + 14 components。build後のruntimeは1 featureにつきexact 13 executable tasks。runtimeではphase slotとtaskを1:1にして別phase文書を作らない。
- **component_kind (5 種、全検討済み)**: skill / sub-agent / slash-command / hook / script。skill×2 / sub-agent×3 / slash-command×1 / hook×1 / script×7 = 14 実体へ収束した。
- **workstream_kind / build_target_kind 二重フィールド**: system-dev-planner が生成する `workstream-inventory.json` は、生成対象タスクの分類軸 `workstream_kind` (9 値: frontend/backend/api/data/infrastructure/security/quality/documentation/operations) と、ビルド対象語彙を保持する `build_target_kind` (6 値: `application-code` + component_kind 5 値) の 2 フィールドを持つ。`build_target_kind` ∈ {skill,sub-agent,slash-command,hook,script} のとき plugin-dev-planner 同様の builder routing へ、`application-code` のとき task-graph build/capability-build への汎用 handoff へ分岐する (goal-spec C2 の充足)。
- **implementation-readiness**: system-spec-harness 側の完成度評価 (前提条件/設計知識/成果物/依存/完了チェックリスト等の充足度)。`complete` 未達では実装 handoff を fail-closed で停止する (goal-spec C4/constraints)。判定は C08 (`check-implementation-readiness.py`) が単一 SSOT として担い、C01 (emit 時) と C07 (tool-call 時) の 2 箇所から呼ばれる (第二消費者あり=plugin-root hoist の根拠)。
- **dev-graph 登録契約**: P01..P13 exact 13 taskをall-or-none登録し、共通`parent_feature`/`feature_package_id`、expected/applied=13、phase/node exact-set、graph revision一致後だけhandoffする。詳細は`feature-execution-package-contract.md`と`dev-graph-registration-contract.json`。
- **Tracker publication/completion handoff**: typed task specは`tracker_binding_intent`、条件付きGitHub publication intent、linked-PR policyを宣言する。Beads/GitHub/Projects mutation・完了収束はdev-graphが所有し、system-dev-plannerはintentだけを持つ。`mode=both`のautoは曖昧として禁止する。
- **branch/worktree handoff**: 各taskはone-task-one-branch、repository相対touches、worktree lease条件を持つ。system-dev-plannerは割当を実行せず、dev-graphのlease-aware schedulerとdefault-branch reconcilerが消費する。
- **DRY 委譲とsource pin**: 仕様書・architectureの内容構築は `system-spec-harness` version `0.1.0` の `run-system-spec-compile` + `assign-system-spec-completeness-evaluator` (手動 command `/spec-compile`) へ委譲する。`system-spec-source-pin.json` と不一致なら停止する。
- **repo-local authority**: symlink物理元はcode/assets専用。content/config/state/cache/lock/staging/publishedはC09が解決したcaller repositoryだけを正本とし、`.dev-graph/config.json` の再導出済みrepository_idとrepo相対pathをrealpath containment検査する。
- **root precedence**: `--repo-root` > allowlist済みtrusted project env > `git rev-parse --show-toplevel` > cwd marker。選択候補はhost宣言`$CLAUDE_PROJECT_DIR`のrealpathと一致する場合だけ採用する。不一致・root外・absolute/traversal・broken/moved content symlinkは診断付きfail-closed。harness自身のbroken symlinkはhost launcher/installerが起動前preflightする。
- **atomic promotion**: C01/C04はrepo-local stagingだけに書き、C11はreadiness complete・C12決定論validation PASS・独立4条件PASS・同一digest・repo identity一致後だけsame-filesystem atomic renameで公開する。dev-graphはpromotion receipt後だけ登録する。

## インフラ
- **実行環境**: Python標準ライブラリのみ。cwd=repo-rootを仮定せずC09で毎回caller rootを解決する。`$CLAUDE_PLUGIN_ROOT`はcode/assets位置にのみ使い、保存content pathには使わない。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph (デフォルト成果物 task-graph.json の 10 検査) / check-runtime-portability (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (L4 consumer 契約)**: 後段 builder は handoff routesのDAGを消費する。`C09 → {C12,C08,C10,C03} → {C05,C04,C07} → C02 → C11 → C01 → C06`の依存順でbuildする。これによりC01のruntime sequence `resolve → elicit → decompose/emit → independent evaluate → promote`の全producerが起動前に揃う。L3ではroute契約だけを確定し実buildしない。
- **producer/consumer 境界**: 本 plan (producer=system-dev-planner) の所有範囲は task-spec/workstream-inventory/task-graph の schema・導出・implementation-readiness 判定のみ。仕様書・アーキテクチャの内容構築は system-spec-harness、実装コード生成は task-graph build/capability-build、dev-graph tasks/ ノードへの実登録・Issue 起票・並列実行の起動は dev-graph 側の所有であり、本 plan の component として計上しない。
- **コンポーネント目録の所在**: buildableな14実体は `component-inventory.json` が唯一のSSOT。生成されるsystem workstreamの9分類は別の `workstream-inventory.json` 契約であり混同しない。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required (task/phase template/workstream/repo-local runtime/atomic promotion/default config) | `plugin_meta.ssot_dedup` |
  | schemas | required (workstream-inventory/plan-findings/project-config/dev-graph-registration/atomic-promotion-receipt の 5 schema draft) | inventory `plugin_level_surfaces.schemas` |
  | vendor | omitted | inventory `plugin_level_surfaces.vendor.omitted_reason` |
  | MCP/app connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |
  | notion_config | omitted | inventory `plugin_level_surfaces.notion_config.omitted_reason` |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。C02 (skill_kind=assign) は `feedback_contract` を構造上省略する (FEEDBACK_LOOP_SKILL_KINDS=run/wrap/delegate の対象外)。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。system-dev-planner 自身の生成物 (C01) と評価 (C02/C05) も同一原則で context を分離する。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 5 周 (max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

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
- [ ] 基本定義 (plugin slug / purpose / スコープ / 呼び出し元との境界) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種検討証跡 / workstream_kind・build_target_kind 二重フィールド / implementation-readiness / dev-graph 登録契約 / DRY 委譲) が宣言されている。
- [ ] インフラ (実行環境 / core+拡張ゲート / build の始め方 / producer-consumer 境界 / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / エスカレーション) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: R1(goal-elicit)→R2(decompose)→R3(emit task specs)→R4(独立評価)→task-graph 射影→build handoff のゴールシーク型ライフサイクルが、plugin-dev-planner と同型構造で本 index/phase 仕様書 (P01-P05) に設計記載されている。
- [ ] 要件 C2: workstream-inventory (component-inventory 相当) が、plugin-dev-planner の component_kind をビルド対象語彙 (`build_target_kind`) として保持しつつ、生成対象の分類軸を system workstream 語彙 (`workstream_kind`) へ置換して記録する設計になっている (`references/workstream-inventory-schema-design.md` + P02)。
- [ ] 要件 C3: system-spec-harness が生成した確定仕様書・アーキテクチャ graph node を引用入力とし、ヒアリング/出典取得/compile/完成度評価のロジックを複製しない設計が P01/インフラ (DRY 委譲・producer/consumer 境界) に記載されている。
- [ ] 要件 C4: dev-graph から呼び出される入出力インターフェースが定義され、implementation_readiness=complete 未達では実装 handoff を fail-closed で停止し (C07/C08)、生成したタスク仕様書を dev-graph の tasks/ グラフノードとして登録可能にする契約が記載されている。
- [ ] 要件 C5: 各タスク仕様書が実装着手に必要な内容 (前提条件/設計知識/成果物/依存/完了チェックリスト等) の充足度=implementation-readiness を判定できる構造化テンプレート仕様 (`references/system-task-spec-template.md`) を持つ設計が P08/P12 に記載されている。
- [ ] 要件 C6: system-dev-planner 自身の計画が plugin-dev-planner 同型の決定論ゲート群 (verify-index-topsort/detect-unassigned/check-spec-frontmatter/check-spec-gates/check-spec-matrix-coverage 等) で検証可能であり、生成物側にも quality_conditions 相当の 4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) を C02/C05 が機械/推論検証できる設計が記載されている。
- [ ] 要件 C7: system-dev-planner が独立 plugin (plugin-plan) として `.claude-plugin/plugin.json`・marketplace・cachebuster・validate-plugin-completeness.py の物理契約を後続 R3 の `plugin_meta` (本 frontmatter) へ渡す意図が記載されている。
- [ ] 要件 C8: system-dev-planner は仕様書/アーキテクチャの内容構築 (system-spec-harness へ委譲) と実装コード生成 (task-graph build/capability-build へ handoff) を自身の担当外とし、タスク仕様書 + task-graph 生成までを担う責務境界が「基本定義」「インフラ」節に記載されている。
- [ ] 要件 C9: `system-spec-source-pin.json` が system-spec-harness version 0.1.0 と compile/evaluator entrypointを固定し、repo-local確定成果物だけをcitation-onlyで消費する。
- [ ] 要件 C10: caller repo root precedenceとhost project-root一致、repository_id再導出、repo-local config、relative-only/realpath containment、cross-read禁止、broken/moved content symlink診断、host broken-link preflight、repo別state/cache/lock、idempotent no-overwrite init、multi-repo isolation、same-digest atomic promotionがcomponent/phase/handoff/受入へ配線されている。
- [ ] 要件 C11: typed task specのtracker binding/publication intentがdev-graph registrationへ写像され、binding別authorityへpublication可能である。
- [ ] 要件 C12: exact 13 taskのall-or-none登録receipt (expected/applied=13、P01..P13 exact-set、共通parent/package)を検証し、tracker mutation/reconciliationをdev-graphへ委譲する。
- [ ] 要件 C13: task templateがone-task-one-branch、resource_scope、worktree lease、feature pending/default reconciliation契約を持つ。
- [ ] 要件 C14: system-dev-planner がミクロ層として、自動起動時は dev-graph の feature ノード (purpose/goal/scope_in/scope_out/acceptance/architecture_refs) を構造化入力として受理し goal-spec へ写像する経路を持ち、手動起動時 (`/system-dev-plan`) は自然文構想を受理する経路を持つ。
- [ ] 要件 C15: 生成する typed task specification と dev-graph registration payload が `parent_feature` を持ち、1 run が生む全 promoted task が同一 `parent_feature` を共有して feature 配下へ atomic 登録される。
- [ ] 要件 C16: runtime outputは別の13 lifecycle文書+可変N taskではなくP01..P13 exact 13 executable task specs/13-node DAGで、欠落・重複・14件目・層越え依存をfail-closedする。
- [ ] `task-specs/*.md` が13 phase policyと14 component buildをdispatch可能な単一責務taskへ分解し、`shape_marker=task-graph-derived` のDAGを導出できる。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングし、`task_graph_ref` を携帯する。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった system-dev-planner が当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「system-spec-harness の確定成果物から task-spec + task-graph が implementation_readiness を満たして確定した状態」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| system-spec-harness 確定成果物を引用しロジックを複製していない | C01 の実行ログが system-spec-harness の出力ファイルパスのみを引用しヒアリング/compile ロジックを再実装していないことを確認 | C01 (run-system-dev-plan) の IN1 criterion |
| implementation_readiness 未達を fail-closed で停止する | 未完成な system-spec-harness 成果物を入力に注入し、C07 (hook) が Bash/Task 呼出しを exit2 で阻むことを確認 | C07 (guard-implementation-readiness) + C08 (check-implementation-readiness.py) |
| 1 featureがexact 13小タスクへ変換される | P01..P13各1件、13-node DAG、共通parent/packageとなり、12/14件・phase重複・cross-feature task edgeが拒否される | C01 OUT1/OUT3 + C12 + feature execution package contract |
| 生成物が 4 条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) を満たす | C02 が独立 context で C05 (evaluator) を fork し `plan-findings.json` を出力、4 条件全 PASS を確認 | C02 (assign-system-dev-plan-evaluator) + C05 |
| system-dev-planner 自身が決定論ゲートで検証可能 | core+拡張ゲート (11 本・12 起動) を repo-root cwd で実行し全 exit0 を確認 | `specfm.GATE_SCRIPTS` |
| symlink導入先のcontentがrepo間で隔離される | repo-A/repo-Bが同一plugin sourceをsymlink共有するfixtureを並列実行し、相手repo markerを一度も読まずstate/cache/lock/promotion pathが交差しない | C09 + C01 OUT2 |
| initが既存repository文書を壊さない | 同一repoでinitを2回実行し既存docs/specs/architecture/tasks/issuesのhash不変、2回目はcreated=0またはpreserved/skippedのみ | C10 |
| 部分生成物を公開しない | evaluator digest mismatch/readiness incomplete/path escapeを注入しcurrent pointer不変、全PASS時だけatomic promotion receiptが生成される | C11 |
| promoted taskをdev-graphへ登録できる | receiptがexpected/applied=13、P01..P13 exact-set、全task同一`parent_feature`/`feature_package_id`を証明し、旧payload・生成時done・partial registrationを拒否する | dev-graph-registration.schema.json + contract |
| 複数worktree向け実行契約を引き渡せる | typed taskにone-task-one-branch、touches、lease、feature pending/default reconciliationがあり、dev-graph schedulerへ渡した際に同一task二重割当されない | system-task-spec-template + dev-graph registration contract |

build 後、各 component の `feedback_contract.criteria` (C01) が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たす system-dev-planner が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
