---
id: IDX0
title: harness-creator task-graph consumer 拡張計画 index (main)
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
  pkg_contract:
    applicable: false
    reason: "harness-creator は distributable:false かつ NEVER_DISTRIBUTE denylist (改名前の旧名由来) 対象で PKG-001..015 の配布契約検査は非該当。本サイクルは既存スクリプト追加 (plugin-root 配置) + 既存 command (capability-build) への Edit のみで配布境界自体を変更しない"
  governance:
    applicable: false
    reason: "run-skill-rubric-governance が所有する評価 rubric 正本 (plan-rubric.json 等) は本サイクルで変更しない。本 plan は capability-build の dispatch 経路拡張 (task-graph consumer 化) であり rubric governance の対象外"
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
---

# harness-creator task-graph consumer 拡張計画 index (main)

> 本計画は新規プラグイン構想ではなく、既存プラグイン `harness-creator` の `/capability-build` (L4 一括 build 実行系) へ、plugin-dev-planner 側が producer として提供する task-graph (schema/導出器/validator/ready-set 計算器) を consumer として消費する 7 責務 (並列 dispatch・state 単一 writer write-back・produces/consumes 成果物注入・discovered-task (E4) emit・進捗集計・未処理 discovered-task 完了ブロック・task-graph 実行知見の knowledge 化) を追加する `existing-plugin-update` 計画である。producer 側計画 (`plugin-plans/plugin-dev-planner/`) が新設した task-graph を harness-creator が読まない限り、タスク粒度の並列機会が使われず、build 成果物が graph の produces として登録されず consumes 解決が断裂し、build 中の発見タスクが plan へ還流せず、実行中に得た依存判断・詰まり・解決知見が次回 build に再利用されない。本計画はこの断裂を、checklist C1-C13 (C10=冪等再開・実行排他 [build lease/孤児 lease 回収/graph_hash pin 検証]・C11=実行イベントログ・C12=実行時停滞検出・C13=未処理 discovered-task 完了ブロック + knowledge 化を含む) として解消する。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。両軸は互いの内容を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `harness-creator` (plan_dir=`plugin-plans/harness-creator/`・build 対象は `plugins/harness-creator/`)。
- **最上位目的 (purpose)**: plugin-dev-planner が plan へ追加する型付き task-graph は、L4 実 build を担う harness-creator が消費しなければ無意味である。`/capability-build` 系の一括 build を task-graph 駆動へ拡張し、依存充足タスクのみの正順/並列 dispatch・route-build-report を介した進捗 (state) write-back・produces 成果物の依存先タスク入力への注入・build 中に発見した新タスクの discovered-task 還流を機械保証して、plan→build パイプライン全体の品質精度を上げる。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C13)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら仕様を先に更新してから build へ戻す (spec-first)。
- **producer/consumer 境界の分離**: task-graph の schema/導出/検証/ready-set 計算器の所有は producer 側 (plugin-plans/plugin-dev-planner/ plan) であり、本 plan (consumer 側) は消費のみで再実装・複製しない (goal-spec constraints #1)。境界の正本は `references/pipeline-boundary-contract.md` (本 plan checklist C7 で追記)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `envelope-draft/plugin.json` + `handoff-run-plugin-dev-plan.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実 `plugins/harness-creator/` への script/command 実装反映 (L4・後段 run-skill-create/run-build-skill/capability-build の新規ファイル追加/Edit build へ委譲)。境界契約と harness-creator 自身の knowledge 正本は、計画と実 harness knowledge を接続するため本改善で同期する。

## ドメイン知識
- **2 軸直交 + 第 3 の射影の消費**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=7 component・機械 SSOT) を二重に持たない設計へ、producer 側が追加する task-graph (第 3 の射影) を読み取り専用で消費する。task-graph は component-inventory.json の component 粒度 depends_on を再記述せず包含参照する。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。本計画は 5 種を全検討したうえで script 7 件 (C01-C05, C07, C08, いずれも plugin-root 配置) + slash-command 1 件 (C06=capability-build の UPDATE) の計 8 件へ収束した (derivation 参照・skill/sub-agent/hook いずれも新規の独立能力面/文脈判断面/強制面を必要としないと判断した根拠を明示)。C07=manage-build-lease.py は追加差分指示 C10(b/c/d) (孤児 lease 回収判断・build lock 排他・graph_hash pin 検証) を「build 開始前に一度だけ実行される安全性検査」という共通タイミング・共通不変条件で束ねた新設 component であり、C08=record-task-graph-knowledge.py は C13 (未処理 discovered-task 完了ブロック + Loop A/B knowledge 化) を独立検証可能な完了判定/知見化 component として持つ。C10(a) は C01 の既存アルゴリズムへの折込み、C11/C12 は C02/C05 それぞれの拡張として新規 component 化を見送った (根拠は component-inventory.json `derivation` および phase-02 参照)。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=7 は buildable 実体数で独立に決まる。**entities_covered 付与規則**: component の build_target の生成/検証を primary deliverable とする phase のみが `entities_covered` に id を持つ。P01 (要件定義)・P03/P07/P10 (判定ゲート系)・P08 (component 非依存の横断観点)・P11/P12/P13 (完了プロセス系) は `entities_covered=[]` が正常である (空は orphan ではなく非依存の明示)。
- **task-graph.json (producer SSOT・読み取り専用) と task-state.json (consumer SSOT・単一 writer) の分離**: 前者は宣言的構造 (node/edge)、後者は runtime state (pending/running/done/blocked の永続 4 値)。`ready` は compute-ready-set.py が算出する一時ビューであり task-state.json へ永続化しない。C01 は両者をマージした一時ビューを producer 側 compute-ready-set.py へ subprocess 経由で渡す。C02 のみが task-state.json を書く (単一 writer・goal-spec constraints #2)。実行イベントログ (C11・task-events.jsonl) も同一 writer=C02 が state 遷移と同一呼び出しタイミングで append-only 追記する (別 writer に分離すると state 更新とイベント記録がトランザクション不整合を起こすリスクがあるため)。
- **discovered-task の E4 境界**: build 進行中 (in-flight) の単一 route から生じる plan 未網羅タスクの発見 (C04) は、build 完了後の全体的改善還流 (E3=emit-improvement-handoff.py) とは時間軸・スキーマ (discovered-task.schema.json vs improvement-handoff.schema.json)・受理機構 (producer 側二段受理 vs evaluator 後の findings 集約) のいずれも異なる新設境界であり、相乗りは SRP 違反と判断し独立境界 (E4) とする。
- **依存方向と knowledge 化**: 日々の build で新しい課題が出た場合、harness は discovered-task proposal を inbox に emit し、planner が次の `--mode update` で task-graph/plan を更新する。harness は task-graph 本体を直接 mutate しない。代わりに C08 が task-events/stall/discovered-task/handoff_notes から蒸留済み knowledge entry を生成し、生成対象 harness の `knowledge/` (Loop A) と harness-creator 自身の `plugins/harness-creator/knowledge/` (Loop B) に add_entry.py 経由で記録する。未処理 discovered-task が残る場合は completed にせず、全 accepted/rejected/superseded になってから完了扱いにする。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提。C01-C05, C07, C08 は `plugins/harness-creator/scripts/` 直下 (placement_scope=plugin-root)、C06 は既存 `plugins/harness-creator/commands/capability-build.md` への Edit 差分のみ (allowed-tools へ Task 追加・C07 を build 開始時に先行呼出・C08 を completed 宣言前に呼出)。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§9 section 床+phase 完全性+DAG) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート 5 本 = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability (この 5 本が本 plan の成果物に対して走る per-plan ゲート・計 11 invocations)。**dogfood ゲートの扱い**: `specfm.GATE_SCRIPTS.extended` は SSOT 上 6 本目に `check-plugin-surface-audit` (`--expect-plan-ready plugin-dev-planner`) を持つが、これは planner ツール (plugin-dev-planner) 自身の現物 surface を監査する dogfood ゲート (`GATE_SCOPE=dogfood`・PLAN_DIR 非スコープ) であり本 plan の成果物を対象としないため、本 plan の per-plan ゲート台帳 (拡張 5 本) からは除外する (計数の単一正本は本節・goal-spec C9・progress.json が一致する)。
- **task-graph 参照契約 (消費)**: `handoff-run-plugin-dev-plan.json` は producer 側の `task_graph_ref: {"path": "task-graph.json", "schema_version": "1.0"}` を検出したとき C01 (dispatch-ready-set.py) 経路へ分岐する。task_graph_ref 不在の既存 handoff は従来 top-sort 直列モードを維持する (C6・後方互換)。
- **task state ファイル**: 既定 `eval-log/<slug>/build/task-state.json` (route-build-report と同居)。単一 writer は C02 (sync-task-state.py) のみ。planner 側は初期 state (全 pending) の生成までを担う。**周回衝突排除 (契約整合修正済み)**: C02 内 `resolve_build_dir(target_plugin_slug: str, cycle_id: str | None) -> str` が、handoff top-level の `cycle_id` フィールド (producer 側追加・additive・null=flat) の値に応じて build 出力先を導出する (`cycle_id` が非 null なら `eval-log/<slug>/build/<cycle_id>/`、null なら既存 flat `eval-log/<slug>/build/` のまま)。当初 `plan_dir` のパス末尾文字列を `target_plugin_slug` と比較する heuristic で cycle-id を推測する設計としたが、対向契約 (「handoff.cycle_id から読む・plan_dir パス解析は禁止」) との衝突および `--out-dir` 上書き plan での誤判定の脆弱性から破棄し、handoff.cycle_id フィールドの値のみを消費する設計へ修正した。C05 (summarize-task-progress.py)・C07 (manage-build-lease.py) は同一関数を import し再実装しない。**実行時契約 3 点の所有区分**: task-state.json の schema (state 遷移値域・schema_version・graph_hash・lease フィールド) は producer 側 C16 (`task-state.schema.json`) が SSOT であり、本 plan は schema を再実装せず consumer 側の実行責務 (冪等 resume=C01・孤児回収/build lock 排他/graph_hash pin 検証=C07・実行イベントログ=C02・停滞検出=C05) のみを component 化する。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を消費する。C01-C05, C07, C08 (script) は `plugin-scaffold` builder が新規ファイルとして配置し、C06 (slash-command) は `run-build-skill` builder が既存 `capability-build.md` へ Edit 差分を適用する。
- **GAP-SCRIPT-BUILDER の機械経路解消順 (ユーザー承認済・PR#70 build-script-route.py 委譲と同型)**: 7 script route (C01-C05, C07, C08) は `builder_status=contract-only` (plugin-scaffold は run-build-skill の正式 kind ではなく contract-only builder 語彙) のため、機械経路をそのまま流すと最小 scaffold 生成 → route status=skipped となり後続依存 (C06) が unreachable になる。これを避けるため build 実行順を次に固定する: (1) executor が本 plan の P05 実装設計 (関数シグネチャ・アルゴリズムが確定済み) から 7 script の**実体を先に生成**する、(2) 各 route は `plugins/harness-creator/scripts/build-script-route.py` へ委譲し、生成済み実体の**存在確認経路で green 化** (route-build-report を残し skipped にしない)、(3) C01-C05, C07, C08 が done になったのち依存充足した C06 (capability-build UPDATE) へ進む。この順序により contract-only builder のまま C06 到達性を確保する (実体生成は L4 build の責務であり本 plan は生成順の宣言までを担う)。
- **コンポーネント目録の所在**: buildable な実体 (script×7 + slash-command×1 = 計 8) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required (description のみ更新・entry_points/hooks 変更なし) | `plugin_meta.manifest` |
  | plugin-composition | omitted (commands/capability-build は既に登録済み・Edit 差分のみ) | inventory `plugin_level_surfaces.composition.omitted_reason` |
  | harness/eval | required (現状維持・C01-C08 の対象追加を build 後に反映) | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required (`pipeline-boundary-contract.md` へ C7 追記) | `plugin_meta.ssot_dedup` |
  | schemas | omitted (producer 5 schema 中 4 schema [task-graph/discovered-task/handoff-notes/task-state] を消費・複製しない・plan-ledger schema は対象外) | inventory `plugin_level_surfaces.schemas.omitted_reason` |
  | vendor | omitted | inventory `plugin_level_surfaces.vendor.omitted_reason` |
  | mcp_app_connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |
  | notion_config | omitted | inventory `plugin_level_surfaces.notion_config.omitted_reason` |

## 環境ポリシー
- **品質基準**: C01-C08 各々が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。全 component が非 skill kind (script/slash-command) のため feedback_contract/goal_seek/prompt_layer の要求対象外 (specfm の対象判定通り)。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (goal-spec constraints #8・Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 5 周 (max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- **単一 writer の構造的保証**: SubAgent 並列 dispatch 時も task-state.json への書き込みは親 (dispatcher=capability-build) が C02 を直列呼び出しすることでのみ行い、並列 SubAgent 自身には書かせない (write_scope 衝突タスクは ready_batch から除外し直列化・非決定的タイブレーク禁止)。
- **discovered-task の還流規約**: emit (C04) は追補提案のみで、受理判断は producer 側の二段受理 (追加ノードのみ自動反映・構造変更級はユーザー承認) に従う。emit 側で plan を直接編集しない (constraints #5)。
- **完了ブロック規約**: C08 が discovered-task inbox を確認し、未処理 proposal が 1 件でも残る場合は build を completed にしない。accepted/rejected/superseded のいずれかに分類済みになって初めて completion gate を PASS させる。
- **既存契約の非破壊**: 既存 route-build-report 契約 (PR#70・validator fail-closed) はフィールド追加のみの additive 拡張とし、既存フィールドの意味/型を変更しない (constraints #7)。

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
- [ ] 基本定義 (plugin slug / purpose / producer-consumer境界 / スコープ) が宣言されている。
- [ ] ドメイン知識 (2軸直交+第3射影の消費 / component_kind 5種検討証跡 / task-graph-task-state分離 / E4境界) が宣言されている。
- [ ] インフラ (実行環境 / core+拡張ゲート / task-graph参照契約 / state単一writer / 目録所在 / surface採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / 単一writer構造保証 / discovered-task還流規約) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: /capability-build が task_graph_ref 検出時に ready-set 計算器を呼び出し、直列チェーン/ダイヤモンド依存/write_scope衝突の3ケースで dispatch 順序・並列度が期待値と一致する受入例が定義されている。
- [ ] 要件 C2: route build 完了時の state 遷移 + handoff notes write-back 契約が component 化され、report欠落/state不整合/notes上限超過のfail-closed検出が定義されている。build 成果物 (`eval-log/<slug>/build/` 配下) の周回衝突排除 (`resolve_build_dir(target_plugin_slug, cycle_id)` が handoff.cycle_id フィールドのみを消費し plan_dir のパス解析を行わない) が定義されている。失敗時の blocked 遷移 (reason=origin-failure 必須) と `--propagate-blocked` による下流連鎖伝播、および route:task=1:N で route-build-report の additive `covered_task_ids[]` を照合して done 遷移させる規則が定義されている。
- [ ] 要件 C3: produces/consumes 成果物注入契約が仕様化され、producer未完了/成果物不在のfail-closed拒否とnotes注入の有界性検証が定義されている。
- [ ] 要件 C4: discovered-task emit機構が component化され、provenance携帯・schema検証可能な形式であることが確認できる。
- [ ] 要件 C5: task-graph state集計 (進捗サマリ) がroute-build-report群から決定論導出される仕様化がされ、集計値がstateファイルと一致する検査が定義されている。
- [ ] 要件 C6: task_graph_ref不在の既存handoffが従来top-sort直列実行のまま全既存ゲートexit0を維持する後方互換がテストで固定されている。
- [ ] 要件 C7: pipeline-boundary-contract.mdへtask-graph境界が追記され、planner側plan の handoff契約と語彙・パス・schema_versionが1:1で一致している。
- [ ] 要件 C8: fork evaluatorがconsumer側componentの契約消費過不足・エッジ意味論の誤用有無をplan-findings.jsonでgenuine判定している。
- [ ] 要件 C9: plan一式がelegant-review 4条件を全PASSする設計記述を持ち、同梱決定論ゲートcore5/6invocations+拡張5本が全exit0で通過している。
- [ ] 要件 C10: 冪等再開・実行排他の契約 ((a) 中断/クラッシュ後の done タスク再実行防止・冪等 resume、(b) lease 期限超過の孤児 running タスクの pending 機械回収、(c) 同一 plan/cycle への並行 capability-build 二重起動の build lease 排他、(d) build 開始時に pin した graph_hash と現 task-graph の不一致 fail-closed 検出) が component 化 (C01 拡張・C07 新設) され、各ケースの受入例が定義されている。堅牢化として lease/lock heartbeat (renewal・正当な長時間 build を偽孤児回収しない=F1)・孤児 lock steal と force-release (残留 lock の恒久 lockout 防止=F2)・dispatch 周回ごとの graph_hash 再検証 (実行中混入拒否の検証点強化=F10) が定義されている。
- [ ] 要件 C11: append-only の実行イベントログ (task-events.jsonl・全 state 遷移/ready-set スナップショット/write_scope 衝突判断を時系列追記) が C02 拡張として component 化され、writer が state と同一単一 writer に限定され、イベントログ replay の終端 state が task-state.json と一致する整合検査が定義されている。
- [ ] 要件 C12: 実行時停滞 (deadlock/starvation) の機械検出 (ready-set 空 ∧ 未完了 > 0 ∧ running=0) が C05 拡張として component 化され、原因診断 (依存/成果物不在・blocked 伝播起点) を人間可読で出力し、DAG 妥当でも実行時停滞しうるケースの受入例が定義されている。
- [ ] 要件 C13: 未処理 discovered-task が残る限り completed 化を拒否し、解決済み/停滞/再試行/依存判断を Loop A/Loop B の knowledge へ有界に記録し、次回 build/設計時に検索利用できる。
- [ ] C01-C08 がそれぞれ build_target 非空・builder/build_kind 整合・依存 DAG 非循環 (C06 は depends_on:[C01..C05,C07,C08] のみで循環なし・C07 は depends_on:[C02]・C08 は depends_on:[C02,C04,C05]・C05 は depends_on:[C02] (resolve_build_dir を import する build 時コード再利用依存)) で core 規律 (quality_gates + harness_coverage) を携帯する。
- [ ] C01-C08 それぞれが >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が C01-C08 を builder/build_kind/build_args/build_target/depends_on 込みで後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「C01-C08 が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった改修が当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を契約として焼くだけで、実行は後段 build (run-skill-create/run-build-skill/capability-build のテスト実行・fork evaluator の genuine 判定)。purpose の正本 = `goal-spec.purpose`「/capability-build 系の一括 build を task-graph 駆動へ拡張し、依存駆動の正順/並列実行・成果物連結・discovered-task 還流を機械保証する」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 並列 dispatch が3ケースで期待値通り動く (C1) | phase-04 の T1-T5 fixture (直列チェーン/ダイヤモンド/write_scope衝突) で `test_dispatch_ready_set.py` を実行し期待 ready_batch/conflicts と一致することを確認 | C01 の harness_coverage.kind_pass |
| state write-back が fail-closed で機能する (C2)・build 成果物が周回衝突しない | phase-04 の 4+3 ケース (正常遷移2種/後退拒否/route-report欠落/handoff.cycle_id有無2種/--out-dir上書きplan負例) で `test_sync_task_state.py` を実行し期待 exit code と `resolve_build_dir(target_plugin_slug, cycle_id)` の期待 build_dir に一致することを確認 | C02 の harness_coverage.kind_pass |
| produces/consumes 注入が有界かつ fail-closed である (C3) | phase-04 の 3 ケース (正常注入/producer未完了/notes有界性違反) で `test_inject_task_inputs.py` を実行し期待挙動と一致することを確認 | C03 の harness_coverage.kind_pass |
| discovered-task が E4 境界として schema 準拠 emit される (C4) | phase-04 の 3 ケース (正常emit/source不在/E3スキーマ非互換) で `test_emit_discovered_task.py` を実行し discovered-task.schema.json で検証可能なことを確認 | C04 の harness_coverage.kind_pass |
| 進捗集計が決定論導出される (C5) | phase-04 の 3 ケース (混在state集計/additive読取/周回衝突排除の`resolve_build_dir()`再利用) で `test_summarize_task_progress.py` を実行し期待集計値と一致することを確認 | C05 の harness_coverage.kind_pass |
| 既存 handoff の後方互換が維持される (C6) | phase-04 の 2 ケース (task_graph_ref有無) で `test_task_graph_ref_dispatch.py` を実行し、無し側で既存 core ゲートが全 exit0 のまま変化しないことを確認 | C06 の harness_coverage.kind_pass |
| pipeline-boundary-contract.md の追記が producer 側と 1:1 で一致する (C7) | 追記後の「task-graph 境界」節の producer/consumer/state file path/schema_version が `plugin-plans/plugin-dev-planner/handoff-run-plugin-dev-plan.json` の `task_graph_ref`/`open_issues[0]` と一致することを目視+grep で確認 | `plugins/harness-creator/references/pipeline-boundary-contract.md` |
| consumer 側の契約消費・エッジ意味論が genuine 判定される (C8) | fork evaluator を実行し、判定結果が plan-findings.json の findings[] へ task-graph-consumer bucket として記録されることを確認 | R4-evaluate 相当の C8 判定ステップ + plan-findings.json |
| plan一式が全ゲートexit0でPASSする (C9) | 11 本の決定論ゲート (check-plugin-goal-spec/verify-index-topsort/detect-unassigned/check-spec-frontmatter/check-spec-gates/check-spec-matrix-coverage ×2/check-surface-inventory/check-build-handoff/check-runtime-portability/check-requirements-coverage) を実行し全 exit0 を確認 | run-plugin-dev-plan-progress.json |
| 冪等再開・実行排他が期待通り動く (C10) | phase-04 の冪等 resume 1 ケース (C01) + lock 取得/二重起動検出/孤児 lease 回収/graph_hash pin 一致・不一致の 6 ケース (C07) で `test_dispatch_ready_set.py`/`test_manage_build_lease.py` を実行し期待 exit code/出力と一致することを確認 | C01・C07 の harness_coverage.kind_pass |
| 実行イベントログが単一 writer で整合する (C11) | phase-04 の 3 ケース (state 遷移イベント追記/dispatch 判断イベント追記/replay 整合検査) で `test_sync_task_state.py` を実行し、task-events.jsonl の replay 終端 state が task-state.json と一致することを確認 | C02 の harness_coverage.kind_pass |
| 実行時停滞が診断付きで検出される (C12) | phase-04 の 3 ケース (deadlock/producer 失敗による下流全 blocked/停滞なし) で `test_summarize_task_progress.py` を実行し `stall` 出力の診断内容が期待と一致することを確認 | C05 の harness_coverage.kind_pass |
| 未処理 discovered-task と knowledge 化が完了判定へ反映される (C13) | phase-04 の 4 ケース (未処理 inbox ありで completed 拒否/accepted・rejected・superseded のみなら PASS/Loop A・Loop B へ必須6フィールド entry 追記/巨大 task-events を丸写しせず source_ref 要約のみ) で `test_record_task_graph_knowledge.py` を実行し期待挙動と一致することを確認 | C08 の harness_coverage.kind_pass |

build 後、C01-C08 の harness_coverage が pytest 実行で実測され、fork evaluator の C8 判定が plan-findings.json へ記録され、上表の受入が PASS して初めて「purpose を満たす拡張が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
