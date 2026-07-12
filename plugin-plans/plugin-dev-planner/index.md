---
id: IDX0
title: plugin-dev-planner task-graph 追加計画 index (main)
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
    reason: "NEVER_DISTRIBUTE denylist (F3) 対象で PKG-001..015 の配布契約検査は非該当。plugin-scaffold envelope は contract-only builder が既に gap_ref 登録済みで、本 goal (task-graph 追加) はこの境界を変更しない"
  governance:
    applicable: false
    reason: "harness-creator 側の評価 rubric Runbook (run-skill-rubric-governance) は所有/変更しないため非該当。assign-plugin-plan-evaluator 内部の plan-rubric.json は本 plugin 内の意味評価軸 (C8) を加算変更するのみで、harness-creator 側正本の変更には当たらない"
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

# plugin-dev-planner task-graph 追加計画 index (main)

> 本計画は新規プラグイン構想ではなく、既存プラグイン `plugin-dev-planner` の `run-plugin-dev-plan` skill を更新する `existing-plugin-update` 計画である。既存task-graph機構に加え、task execution envelope (C17)・構造/状態/観測の三層分離 (C18)・過去cycle lineage/knowledge再利用 (C19) を明文化する。これにより「13 phaseを各nodeが全部実行するのか」「node titleがpromptなのか」「graphのstatusを直接書き換えるのか」「完了済み仕様と過去知識をどう次の改善へ使うのか」を機械契約で解消する。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。task-graph は第 3 の射影でありこの 2 軸の意味論を置換しない (component 粒度 depends_on は再記述せず包含参照する)。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

> **C 番号の 3 重空間 (凡例)**: 要件 checklist は `C1`-`C19`、buildable component id は `C01`/`C02`、elegant-review条件は `C1`-`C4`。桁数と文脈で区別する。

## 基本定義
- **プラグイン slug**: `plugin-dev-planner` (plan_dir=`plugin-plans/plugin-dev-planner/`・自己参照計画=対象 plugin と計画の生成元 plugin が同一)。
- **最上位目的 (purpose)**: run-plugin-dev-plan が生成する plan の実行が 13 phase 仕様書の直列消化に律速される問題を、タスク単位の型付き依存グラフ (task-graph) の追加で解消し、依存関係駆動の正順/並列実行・成果物→次タスク入力の機械連結・discovered-task の構造化追補を機械保証して plan 実行の品質精度を上げる。
- **仕様駆動 (大前提)**: 要件の正本は `goal-spec.json` の checklist (C1-C19)。本 index + 13 phase は共通ライフサイクル契約、将来生成される `task-specs/<task-id>.md` はnode単位の実行契約であり、実装との乖離が出たら仕様を先に更新してからbuildへ戻す。
- **メタ循環の分離**: 13 ファイル固定の解除 (C10) は build 対象の機能要件であり、本 plan 自体は現行 skill・現行ゲートで生成/検証するため現行 shape (13 phase ファイル) で記述する。C10 は将来の plan が可変 shape を使える機能を指し、本 plan 自身の記述形式ではない。同型の分離が C13 (plan 出力ディレクトリ規約) にも適用され、本 plan 自体は現行 flat 配置 (`plugin-plans/plugin-dev-planner/`) のまま生成し、cycle-id 付きディレクトリ + plan-ledger.json は将来の plan が使う機能である。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `envelope-draft/plugin.json` + `handoff-run-plugin-dev-plan.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実 `plugins/plugin-dev-planner/` への実装反映 (L4・後段 run-skill-create の新規ファイル追加/Edit build へ委譲)、`/capability-build` による並列 dispatch の実行本体。

## ドメイン知識
- **2 軸直交 + 第 3 の射影**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=2 component・機械 SSOT) を二重に持たない従来設計へ、task-graph (タスク粒度の型付き依存グラフ) を第 3 の射影として追加する。task-graph は component-inventory.json の component 粒度 depends_on を再記述せず包含参照し、正規化を維持する。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。本計画は 5 種を全検討したうえで 2 skill component (C01=run-plugin-dev-plan mode=update・C02=assign-plugin-plan-evaluator mode=update) へ収束した (derivation 参照・skill 偏重の既定選択ではなく検討済み帰結)。
- **phase ≠ task ≠ component**: 13 phaseは全nodeが順番に全文実行するpromptではなく、要件・設計・実装・検証等の共通policyである。task nodeは1検証可能成果物の実行単位で、`task_spec_ref`が1件のtask spec、`phase_ref`が適用するphase policyを指す。`execution_kind`がdirect-task/component-build/phase-gateを区別し、component-buildだけが`route_ref`でbuilderを解決する。`entity_ref`は分類・traceability専用である。N=2のcomponentは実体数でありtask数やphase数とは独立する。
- **SubAgentへ渡す単位**: dispatcherはtitleだけを渡さない。node + task spec + 該当phase policy + component route + acceptance criteria + upstream artifacts + bounded handoff notes + knowledge refs + verify方法を`TaskExecutionEnvelope`へ合成し、schema PASS後にのみdispatchする。
- **task-graph の 4 エッジ型**: `parent_of` (階層) / `depends_on` (順序・`blocks` はその逆向き導出で独立宣言禁止) / `produces` (タスク→成果物) / `consumes` (成果物→タスク)。canonical graphの`state`は後方互換用seed=`pending`固定でありruntime更新しない。`task-state.json`だけが`pending/running/done/blocked`の4値を所有する。ready-set 計算は depends_on 完了・consumes 成果物実在に加え write_scope 非重複を並列安全性の条件とする。**`ready` は computed-only**で、どちらのSSOTにも永続化しない。
- **§ 節番号の対応 (io-contract.md 正本)**: 本計画の "§5" は io-contract.md §5 (phase 本文 section 契約=宣言型 8 節・正本 `specfm.PHASE_BODY_SECTIONS`) を、"§9" は io-contract.md §9 (生成スキルの入出力契約全体=13 phase / inventory / handoff の shape・DAG/topsort 規約) を指す。"§5 section 床" (空節を弾く) と "§9 DAG/topsort" (phase 完全性・依存順) は別空間であり、verify-index-topsort は両者を併せて検査する。
- **done の二層 semantics**: `goal-spec.json` checklist の `done` は「build 後検証で満たされる要件の充足」を表す最終判定であり、`run-plugin-dev-plan-progress.json` の `checklist_state[].done` は「plan (L3) の設計記述が当該要件を被覆した=plan 設計完了」を表す中間判定である (両者は別空間: progress.done=true でも goal-spec の受入は build 後に確定する)。
- **canonical serialization と状態更新**: `task-graph.json`は構造SSOTで同一revision内不変、`task-state.json`は可変状態SSOTでconsumer dispatcherのみが書く。`task-graph-status.json`(機械観測) / `task-progress.md`(差分確認) / `task-execution-report.html`(構造化された閲覧・図解・印刷) はplan directoryへ同じ状態から再生成する観測ビューである。HTMLはroute reports/build-summaryを併合し、外部CDN/LLM非依存の自己完結・escape済み・決定論投影とする。done/running/blockedを見せるためにcanonical graphを直接編集してはならない。discovered-taskは外ループ境界でtask specへ反映し、新graph revision/hashを作って旧revisionとlineageで結ぶ。
- **過去cycleの棲み分け**: 完了spec/graph/evidenceはcycle配下のimmutable provenance、plan-ledgerはcycle lineage、knowledge storeはsource_ref付き蒸留知識を担う。新cycleのactive DAGへ過去nodeを混ぜず、採用したknowledge refsと必要なexternal artifact inputだけを明示的・有界に注入する。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。`--mode update` は Edit 差分のみ。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort (§5 section 床+phase 完全性+§9 DAG/topsort) / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート 6 本 = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。C01/C02 いずれの route も build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影し、mode=update として `run-skill-create` へ渡す (既存 skill への Edit 差分・新規ファイル追加のみ・全書き換え禁止)。C02 は depends_on:[C01] で C01 の後に消費される。
- **task-graph 参照契約**: `handoff-run-plugin-dev-plan.json` は実在する `task-graph.json` を `task_graph_ref` で参照する。本planは新契約を実装するbootstrap cycleのため、現行固定shapeではP05のC01とP09のC02だけをlegacy `entity_ref` routeへ割り当て、design/test/review nodeはnullのdirect taskとする。C17 build後のshapeでは各実行可能leafが`execution_kind`/`task_spec_ref`を持ち、component-buildだけが`route_ref`を持つparityへ移行する。cycle-idはhandoff fieldから読み、path末尾解析は禁止する。
- **producer/consumer 境界 (対 harness-creator)**: 本 plan (producer=plugin-dev-planner) の所有範囲は task-graph の schema/導出/検証/ready-set 計算器のみ。dispatch (SubAgent 並列投入)・state write-back・produces 成果物の consumes 注入・discovered-task の emit は consumer 側 (`plugin-plans/harness-creator/` plan、target_plugin_slug=harness-creator) が component 化する L4 実行系の所有であり本 plan の component として計上しない。task state ファイル (確定: `eval-log/<slug>/build/task-state.json`、route-build-report と同居。harness P02 の resolve_build_dir(target_plugin_slug, cycle_id) で解消済み) の単一 writer は consumer 側、C01 は初期 state (全 pending) 生成までを担う。境界語彙は harness-creator 側 goal-spec.json の constraints/checklist C7 と 1:1 で揃え、最終正本は `references/pipeline-boundary-contract.md` (harness-creator plan C7 で追記予定)。build 成果物 (task-state.json/route-<id>.json) のスコープ化に必要な cycle-id は `handoff.cycle_id` から読む契約 (上記) を consumer 側が踏襲する。**harness 側実行時契約 (C10/C11/C12) との所有区分**: harness-creator 側 goal-spec.json は C10 (冪等 resume(a)/孤児 running 回収(b)/build lease 排他(c)/graph_hash pin 不一致 fail-closed 検出(d))・C11 (task-events.jsonl の append-only イベントログ・単一 writer=親 dispatcher)・C12 (ready-set 空+未完了>0+running=0 の停滞検出) を consumer 側の実行責務として追加した。これらはいずれも consumer が実行するが、C10(d) が参照する graph_hash の算出規約と task-state.json の schema (lease フィールド含む) の所有は producer (本 plan, C16) のままであり、consumer は C16 の schema/graph_hash 算出ロジックを再実装せず producer 側 `derive-task-graph.graph_hash()` の算出値と照合するのみである。
- **plan 出力ディレクトリ規約 (C13)**: `specfm.plan_output_dir(name, out_dir=None, base=PLAN_OUTPUT_BASE, cycle_id=None)` を拡張し、`cycle_id` 省略時は現行 flat 配置 (`plugin-plans/<slug>/`) を不変維持、指定時のみ `plugin-plans/<slug>/<cycle_id>/` の周回サブディレクトリを返す。`plugin-plans/<slug>/plan-ledger.json` (単一 writer=planner) が cycle_id/status∈{active,finished,superseded}/plan_dir/summary を保持し、同時 active 重複を `check-plan-ledger.py` が fail-closed 検出する。完了 plan の `finish/` 移動は台帳の status 遷移で代替し、既存 flat 配置 plan は暗黙単一 cycle として後方互換を維持、既存 plan の移行は `migrate-plan-layout.py` が担う。
- **graph 可視化 renderer (C15)**: `render-task-graph-mermaid.py` が canonical task-graph.json → mermaid 依存グラフ図 (`<plan_dir>/task-graph.mmd`) を決定論導出する。node は state 別 `classDef` で色分け、edge は 4 型 (parent_of/depends_on/produces/consumes) を線種で区別し、depends_on のみを辿るクリティカルパスを `linkStyle` で強調する。graph の canonical 順序 (C11 と同一) で走査するため同一 graph からの render は byte 一致し、graph に無い要素 (id/title/type 以外の装飾テキスト等) は描画しない。
- **実行時契約 schema SSOT (C16)**: `schemas/task-state.schema.json` (新規) が state 遷移値域・schema_version・graph_hash・lease (running 状態の started_at/期限)・**blocked_reason** (blocked 状態の起点故障 origin-failure / 下流伝播 propagated を区別する第一級 field・値域 {origin-failure, propagated}・`state==blocked` のとき running→lease と同型の条件付き必須) を定義する。C12 (handoff-notes) と同型の所有/書込分離: schema 定義と graph_hash pin 整合検査 (`check-task-state-schema.py`) の所有は producer (本 plan) だが、実行時の task-state.json への書込 (state 遷移・lease 更新・blocked_reason 記録) は consumer (harness-creator 側 L4 実行系) の単独 writer 責務。graph_hash は build 開始時に C11 canonicalizer 由来の値を pin し、実行中の task-graph 変更 (discovered-task 受理含む) は hash 不一致で fail-closed、反映は次周回のみ。**blocked_reason の由来**: consumer=harness-creator は当初 blocked 遷移の起点/伝播区別を consumer 運用フィールド `notes.reason` へ暫定記録 (F9) し、schema 本体変更を producer 所有として cross_plan_request (GAP-FAILED-STATE-VOCAB) へ上げていた。本 C16 でこれを producer 所有の第一級 schema field へ昇格し、C12 停滞診断が伝播閉包を辿って起点 route を特定できる正式解決先とした (代替案の state enum への failed 追加は harness `ALLOWED_TRANSITIONS`・両 plan の永続 4 値域宣言・既存受入例へ波及し破壊的なため非採用・state 値域は 4 値のまま不変で本 field は additive)。
- **コンポーネント目録の所在**: buildable な実体 (skill×2 = 計 2: C01=run-plugin-dev-plan・C02=assign-plugin-plan-evaluator) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required (現状維持・entry_points/hooks 変更なし) | `plugin_meta.manifest` |
  | plugin-composition | required (現状維持) | `plugin-composition.yaml` |
  | harness/eval | required (現状維持) | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required (`references/task-graph-contract.md` 新規追加) | `plugin_meta.ssot_dedup` |
  | schemas | required (task-graph/discovered-task/handoff-notes/plan-ledger/task-state/task-execution-envelope/knowledge-ref の 7 schema 追加) | `plugin_level_surfaces.schemas` |
  | vendor | omitted | inventory `plugin_level_surfaces.vendor.omitted_reason` |
  | mcp_app_connector | omitted | inventory `plugin_level_surfaces.mcp_app_connector.omitted_reason` |
  | notion_config | omitted | inventory `plugin_level_surfaces.notion_config.omitted_reason` |

## 環境ポリシー
- **品質基準**: C01/C02 各々が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass。C01=loop 型・C02=assign=evaluator-verdict) を携帯する。C02 は skill_kind=assign のため feedback_contract は skip_reason で明示し (loop criteria 必須対象外)、goal_seek は対象外、prompt_layer:7layer は必須。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 5 周 (max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。
- **既存契約の非破壊**: task-graph 関連の新規ヘルパー・分岐 (check-build-handoff.py の `_check_task_graph_ref`・verify-index-topsort.py の `_shape_marker`) はデフォルト値で無効化され、task-graph を持たない既存 plan (`plugin-plans/finish/` 配下含む) の挙動を変えない (C7 の観測可能な証跡)。
- **discovered-task の二段受理**: 追加ノードのみ自動反映、既存エッジ張替え・component 追加の構造変更級はユーザー承認 (`--approved`) を要する。
- **handoff-notes の有界伝播**: went_well/friction_points/downstream_watchouts は各≤3件・文字数上限を schema 強制し、直接依存 (depends_on/consumes) の先行タスク分のみへ伝播する (推移的全履歴注入は禁止)。
- **plan-ledger の単一 writer + fail-closed**: `plan-ledger.json` の writer は planner (本 skill) のみ。同一 slug 配下で `status: active` のエントリが同時に 2 件以上存在する状態を `check-plan-ledger.py` が fail-closed で拒否し、非決定的な自動解決 (どちらかを勝手に選ぶ) は行わない。

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
- [ ] 基本定義 (plugin slug / purpose / スコープ / メタ循環の分離) が宣言されている。
- [ ] ドメイン知識 (2軸直交+第3射影 / component_kind 5種検討証跡 / 4エッジ型 / canonical serialization) が宣言されている。
- [ ] インフラ (実行環境 / core+拡張ゲート / task-graph参照契約 / producer/consumer境界 / 目録所在 / surface採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 現状値非焼込 / discovered-task二段受理 / handoff-notes有界伝播) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: task-graph schema がnode identity/phase_ref/entity_ref/execution_kind/route_ref/task_spec_ref/write_scope/acceptanceとedge 4型を機械検証し、graphのseed state=pending固定、runtime 4状態はtask-stateのみ、readyはcomputed-onlyとする。
- [ ] 要件 C2: derive-task-graph.py がphase policy+task specs+inventory routeから疎なtask-graphを決定論導出し、DAG非循環・orphan0・producer一意・inventory矛盾0に加え、component依存のtask直積展開0・推移冗長edge0・無意味な複製0・density上限超過0を検証する。
- [ ] 要件 C3: produces/consumes の artifact連結契約が仕様化され、consumes参照先producer不在・パス不整合をfail-closedで検出する検査が定義されている。
- [ ] 要件 C4: compute-ready-set.py がtask-stateからready-setを決定論計算し、write_scope衝突時はid昇順winner 1件+deferredを返し、直列チェーン/ダイヤモンド/blocked伝播/write_scope衝突の4ケースと一致する。
- [ ] 要件 C5: discovered-taskフォームschema+受理機構が仕様化され、additiveは安全な外ループ境界の次graph revisionへ自動採用、構造変更級はユーザー承認後に次revisionへ採用する二段受理になっている。
- [ ] 要件 C6: handoff-run-plugin-dev-plan.jsonがtask-graphへの参照(path+schema_version)を携帯し、routes[]とtask-graphのproducerタスクが1:1以上で対応する整合検査が仕様化されている。
- [ ] 要件 C7: task-graphを持たない既存plan(plugin-plans/finish/配下含む)が従来直列解釈のまま全既存決定論ゲートexit0を維持する後方互換がテストで固定されている。
- [ ] 要件 C8: fork evaluator (C02) がタスク細分化粒度の実行着手可能性・エッジ4型意味論の誤用有無をplan-findings.jsonでgenuine判定している。
- [ ] 要件 C9: plan一式がelegant-review 4条件を全PASSする設計記述を持ち、同梱決定論ゲートcore5/6invocations+拡張6本が全exit0で通過している。
- [ ] 要件 C10: タスク仕様書のファイル構成が13ファイル固定から解放される shape 解放仕様がcomponent化され、既存13phase形式のplanは後方互換でゲートexit0を維持し、shape markerで新旧判別が機械検出可能である。**shape_marker が `task-graph-derived` を採用するのは C14 非劣化ゲート (a,c の script + b の C02 genuine判定) が共にPASSした場合のみを前提条件とし、劣化検出時はshape解放をblockし`fixed-13-phase`へfallbackする**。
- [ ] 要件 C11: task-graph.jsonのcanonical serialization (安定key順・決定論的ソート・schema_version必須・配置規約単一固定) を強制するcanonicalizer+lintがcomponent化され、byte一致再現性テストと非正準graph拒否検査が定義されている。
- [ ] 要件 C12: handoff notes契約(went_well/friction_points/downstream_watchouts)がschema化され、件数上限(≤3)・文字数上限がschemaで機械強制され、伝播規則が有界(直接依存先タスク分のみ)で、advisory/actionableの切り分け規準が仕様化されている。
- [ ] 要件 C13: plan出力ディレクトリ規約 (cycle-id サブディレクトリ + plan-ledger.json台帳) がspecfm.plan_output_dir()の拡張として仕様化され、同時active重複がfail-closedで検出され、既存flat配置planの後方互換が全既存ゲートexit0で維持され、移行scriptが定義されている。
- [ ] 要件 C14: 新shape(task-graph駆動可変構成)の非劣化ゲートが(a)精度=二値受入基準携帯率の機械計測 (旧shape §5項目粒度を下回らない)・(b)品質=下流ハーネス実効性のC02 A/B比較genuine判定・(c)再現性=task-graph byte一致+仕様書構成一致の機械計測 の3軸で仕様化され、劣化検出時にshape解放をblockし旧shapeへfallbackする(平均回帰禁止)。
- [ ] 要件 C15: `render-task-graph-mermaid.py` がcanonical task-graph.jsonからmermaid依存グラフ図を決定論導出し、同一graphからの2回連続renderがbyte一致し、出力node id集合が入力graphのnode id集合とset一致する (graph外要素非描画) ことがテスト受入例で定義されている。
- [ ] 要件 C16: `schemas/task-state.schema.json`がstate遷移値域・schema_version・graph_hash・lease(running状態のstarted_at/期限)・blocked_reason(blocked状態のorigin-failure/propagatedを区別する第一級field・値域{origin-failure,propagated}・条件付き必須)を定義し、`check-task-state-schema.py`がrunning状態のlease必須違反・blocked状態のblocked_reason必須違反(欠落/値域外/非blockedでの付与)・graph_hash pin不一致 (build開始時固定値との相違) をfail-closedで検出する。blocked_reasonはconsumer=harness-creatorがnotes.reasonへ暫定記録していた区別(F9)をproducer所有の正式schema fieldへ昇格しC12停滞診断の起点route特定を可能にした対応 (GAP-FAILED-STATE-VOCAB解消) である旨が明記されている。schema/pin規約の所有はproducer (本plan)、task-state.jsonへの実書込はconsumer (harness-creator) の単独writerであるという所有/書込分離が明記されている。
- [ ] 要件 C17: 全実行可能leaf nodeが`execution_kind`+実在`task_spec_ref`を持ち、component-buildだけが`route_ref`を持つ。1 task spec+1 phase policy+route+受入基準+scope+inputs+notes+knowledge+verifyをTaskExecutionEnvelopeへ合成し、title単独/entity_ref暗黙route/13 phase全文prompt化をfail-closedで拒否する。
- [ ] 要件 C18: 構造=`task-graph.json`、可変状態=`task-state.json`、観測=`task-graph-status.json`/`task-progress.md`/`task-execution-report.html`が分離され、state遷移はconsumer単一writerとappend-only task-eventsへ記録される。HTMLは進捗図・実行フロー・route証跡・逸脱・外ループ・正本リンクを自己完結で表示し、build-summary保存後の再投影で最終完了ゲートを含む。同一revision内のcanonical graph bytesは不変、discovered-task採用は新revision/hashを作り、projectionはstateとparityする。
- [ ] 要件 C19: 完了cycleのspec/graph/evidenceをimmutableに保持し、plan-ledgerの`predecessor_cycle_id`でlineageを結ぶ。新cycleは過去nodeをactive DAGへ混在させず、source_ref/freshness/採用理由を持つknowledge refsと明示external artifact inputだけを有界注入する。
- [ ] C01/C02 がそれぞれ build_target 非空・builder/build_kind 整合・依存 DAG 非循環 (C02 は depends_on:[C01] のみで循環なし) で core 規律 (quality_gates + harness_coverage + feedback_contract/skip_reason) を携帯する。
- [ ] C01/C02 それぞれが >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が C01/C02 を builder/build_kind/build_args/build_target/depends_on 込みで後段 builder へルーティングし、task_graph_ref を携帯する。

## 受入確認

> 計画 (上記) が満たすのは「C01/C02 が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった改修が当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test / assign-plugin-plan-evaluator の genuine 判定)。purpose の正本 = `goal-spec.purpose`「plan 実行の直列律速を task-graph (第3の射影) で解消し、依存駆動の並列実行・成果物連結・discovered-task 還流を機械保証する」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| task-graph schema がnode/edge型制約を機械検証する (C1) | 型不整合を含む fixture task-graph.json を validate-task-graph.py へ通し検出結果を確認 | schemas/task-graph.schema.json + validate-task-graph.py |
| 導出→validator が疎なDAGを保証する (C2) | P04 のartifact join/barrier受入例でexit0、component配下task集合の直積・推移冗長edge・重複node・density上限超過fixtureでexit1を確認 | C01 の feedback_contract.criteria IN1/IN2 |
| artifact連結のfail-closed検出が機能する (C3) | consumesが存在しないproducerを指すfixtureでvalidate-task-graph.pyを実行しexit1を確認 | C01 の feedback_contract.criteria IN3 |
| ready-set計算が4ケースで期待値と一致する (C4) | P04の直列チェーン/ダイヤモンド/blocked伝播/write_scope衝突の4fixtureでcompute-ready-set.pyを実行し期待ready-setと一致することを確認 | C01 の feedback_contract.criteria OUT3 |
| discovered-taskが二段受理される (C5) | additiveなdiscovered-task formとstructuralなformのそれぞれでaccept-discovered-task.pyを実行し、後者が--approved無しで拒否されることを確認 | C01 の feedback_contract.criteria IN5 |
| handoffがtask_graph_refと routes 対応を携帯する (C6) | check-build-handoff.py拡張をhandoff-run-plugin-dev-plan.jsonへ実行しexit0を確認 | C01 の feedback_contract.criteria IN6 |
| 既存plan後方互換が維持される (C7/C9) | plugin-plans/finish/配下のplanへ既存決定論ゲート全本を実行しexit0を確認、plugins/plugin-dev-planner配下のpytest全件が既存件数から退行なくgreenであることを確認 | C01 の feedback_contract.criteria OUT1 |
| タスク粒度・エッジ意味論がgenuine判定される (C8) | assign-plugin-plan-evaluatorをfork実行し、判定結果がplan-findings.jsonのfindings[]へtask-graph-semantics bucketとして記録されることを確認 | R1-evaluate.md の C8 判定ステップ + plan-findings.json |
| shape marker で新旧判別が機械検出可能 (C10) | shape_marker未設定/fixed-13-phaseのfixtureとtask-graph-derivedのfixtureでverify-index-topsort.py拡張を実行し分岐を確認 | C01 の feedback_contract.criteria IN7 |
| canonical serializationがbyte一致再現し非正準を拒否する (C11) | 同一入力からのderive-task-graph.py 2回実行結果のbyte一致を確認、手動編集済みfixtureでvalidate-task-graph.pyがexit1することを確認 | C01 の feedback_contract.criteria IN8/OUT2 |
| handoff-notesの件数/文字数上限と有界伝播が機能する (C12) | 上限超過fixtureでhandoff-notes.schema.json検証がfail-closedすることを確認、推移的な間接依存タスクのnotesが伝播対象に含まれないことを確認 | C01 の feedback_contract.criteria IN9 |
| plan出力ディレクトリ規約が衝突を構造的に排除する (C13) | plan-ledger.jsonにactiveエントリを2件並べたfixtureでcheck-plan-ledger.pyを実行しexit1を確認、cycle_id省略時のplan_output_dir()が既存flat配置を返すことを確認 | C01 の feedback_contract.criteria IN10 |
| 新旧shape非劣化ゲートが劣化を検出しblock/fallbackする (C14) | P04のA/B比較fixture (旧shape/新shape) でcheck-shape-non-regression.pyを実行し(a)携帯率比較・(c)byte一致再現性がexit0/exit1を正しく判定することを確認、assign-plugin-plan-evaluatorをfork実行し(b)のA/B比較genuine判定がplan-findings.jsonのshape-ab-comparison bucketへ記録されることを確認 | C01 の feedback_contract.criteria IN11 + C02 の R1-evaluate.md C14(b) 判定ステップ |
| graph可視化rendererがbyte一致し graph外要素を描画しない (C15) | P04のT1-T4 fixtureでrender-task-graph-mermaid.pyを2回連続実行しbyte一致することを確認、出力mermaidのnode id集合が入力graphのnode id集合とset一致することを確認 | C01 の feedback_contract.criteria IN12 |
| task-state schemaとgraph_hash pinの整合がfail-closedで検出される (C16) | running状態でlease未設定のfixtureでcheck-task-state-schema.pyを実行しexit1を確認、blocked状態でblocked_reason欠落/値域外のfixtureで同スクリプトを実行しexit1を確認、build開始時pin値と異なるgraph_hashを持つfixtureで同スクリプトを実行しexit1を確認 | C01 の feedback_contract.criteria IN13 |
| TaskExecutionEnvelopeがnodeを実行可能promptへ安全に合成する (C17) | execution_kind/task_spec_ref/route_ref欠落、title-only、entity_ref暗黙route、13 phase全文注入fixtureを拒否し、正常fixtureでは1 task spec+1 phase policy+明示route+acceptance+inputs+notes+knowledge+verifyをschema PASSで出力する | C01 IN14 + C02 genuine判定 |
| 状態更新がcanonical graphを壊さずplan directoryで見える (C18) | pending→running→done中はgraph byte/hash不変、task-state/task-eventsとprojectionだけが更新され、discovered-task採用時は旧revision不変のまま新revision/hashへrepinすることを確認 | C01 IN15 |
| 過去cycle知識を安全に再利用できる (C19) | predecessor cycleの完了specはimmutable、新cycle graphに旧node 0、relevant knowledge_ref採用/不採用理由あり、source_ref無し・stale・全文履歴注入fixtureは拒否される | C01 IN16 + C02 genuine判定 |

build 後、C01 の `feedback_contract.criteria` が criteria-test として実行され、C02 (assign-plugin-plan-evaluator) の C8 判定が plan-findings.json へ記録され、上表の受入が PASS して初めて「purpose を満たす改修が出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
