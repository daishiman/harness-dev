# capability-build post-build elegant review R2

- date: 2026-07-11
- target: `plugin-plans/plugin-dev-planner/handoff-run-plugin-dev-plan.json` の C01/C02 実体、task-graph 実行証跡、Harness Creator consumer/runtime と量産 engine 境界
- orchestration: reset observer → 3 independent analysts → improvement executor
- methods: 30/30 used, skip 0
- iteration: 1/3

## Phase 1 — reset observation

C01=`run-plugin-dev-plan`、C02=`assign-plugin-plan-evaluator` の2 route、bootstrap graph 58 nodes/130 edges、runtime projection 58/58 done、accepted discovered-task 4件と外ループ3周を、採点せず事実として固定した。canonical graph と task-state の graph hash は `sha256:c636b6aaff4be0ea6d6648e2a184173a5f53afe17047f96337c56628d46b41a8` で一致した。

## Phase 2 — 30 methods

| # | method | independent observation | R2 disposition |
|---:|---|---|---|
| 1 | 批判的思考 | `consumes` 正本とready/envelopeの向きが逆 | artifact→consumer taskへ統一 |
| 2 | 演繹思考 | canonical graphのstate=pending固定をschemaが強制しない | graphはpending const、runtime4値はtask-stateのみ |
| 3 | 帰納的思考 | validator/ready/envelopeのfixture conventionが二系統 | cross-contract fixtureへ統合 |
| 4 | アブダクション | `gate-final` failureとsummary recoveryが矛盾 | TG-C08再実行、finalをok/3件へ更新 |
| 5 | 垂直思考 | C17の本質はtitle/entity暗黙dispatch排除 | target-shape leaf必須gateへ接地 |
| 6 | 要素分解 | C19のref/date/path/hashが弱く空走査PASS | knowledge schema、実在/date/hash/non-vacuous gate |
| 7 | MECE | graph/state/projectionのうちprojectionを実比較しない | 3ファイルの集合/state/summary/hashを比較 |
| 8 | 2軸思考 | evaluator実装量に対しS5-S9対象plan評価が不足 | post-build findingsへ5 bucketを記録 |
| 9 | プロセス思考 | outer-loop後の57/128評価が58/130へ追随しない | metrics/hash/review artifactを更新 |
| 10 | メタ思考 | schema/rendererはあるがtarget graph producerが無い | task-spec→leaf producerを実装 |
| 11 | 抽象化思考 | task specとenvelopeでknowledge契約強度が異なる | `knowledge-ref.schema.json` を共有SSOT化 |
| 12 | ダブル・ループ思考 | 改善実体がfinal evidenceへ還流しない | final gateを再生成 |
| 13 | ブレインストーミング | fixed付加/一時合成/target正本/golden等6案 | task-spec正本 + golden + 全leaf render gateを採用 |
| 14 | 水平思考 | consumerは実state pathを受けるがproducer checkerはPLAN_DIR固定 | 明示3 path CLIへ揃えた |
| 15 | 逆説思考 | rendererを経路から外してもunit testsが緑 | generated target plan全leaf E2Eを追加 |
| 16 | 類推思考 | shape reader分岐はあるがwriter分岐がない | derive/validate/R3を同じmarkerへ揃えた |
| 17 | if思考 | path/routeが増えるとtraversal/danglingが通る | containmentとhandoff route joinを追加 |
| 18 | 素人思考 | done表示からbootstrap/target差を判別できない | checklist/full profile claimを機械可読化 |
| 19 | システム思考 | task-spec→graph→envelope→consumerの連鎖が切れる | producer/consumer両側のE2E契約を接続 |
| 20 | 因果関係分析 | edge向きdriftがready/input/stall/blockedへ波及 | truth tableとshared resolverへ収束 |
| 21 | 因果ループ | optional fieldsがbootstrap永続化を自己強化 | target marker時だけ厳格必須化 |
| 22 | トレードオン思考 | 後方互換とtarget厳格性を一律optionalで妥協 | shape別条件付きgateを採用 |
| 23 | プラスサム思考 | plannerとharnessが別解釈を持つ | Harness Creator resolverを単一化 |
| 24 | 価値提案思考 | 利用価値は実envelopeを追加質問なしで作れること | 全leaf renderabilityを停止条件化 |
| 25 | 戦略的思考 | stale/dangling knowledgeとactive predecessorが将来腐敗 | date/source/hash/statusを検査 |
| 26 | why思考 | drift根因はedge endpoint roleが型で不明瞭 | docs/schema description/validator/testsを同期 |
| 27 | 改善思考 | S5-S9定義後も実build評価が閉じない | fresh 3-way reviewをpost-build findingsへ反映 |
| 28 | 仮説思考 | 「C17-C19反映済み」を代表planで反証できた | 反例を回帰テスト化し全件greenまで修正 |
| 29 | 論点思考 | 生成Harnessのtask-graphはfullかchecklistかが最大論点 | `engine_profile=checklist-graph`, `full_task_spec_graph=false` 固定 |
| 30 | KJ法 | 契約違反/反映漏れ/過剰寛容/cross-plugin/証跡乖離へ島化 | 根因順に直列統合 |

## Phase 3 — applied improvements

- C17: `shape_marker=task-graph-derived` で `task-specs/*.md` を1 spec=1 executable leafへ決定論射影。`execution_kind/task_spec_ref/acceptance/write_scope/produces`、component-buildの`route_ref`をfail-closed必須化。
- edge contract: `depends_on=consumer task→producer task`、`produces=producer task→artifact`、`consumes=artifact→consumer task` をplanner/Harness Creatorで統一。
- C18: canonical graphはpending seed固定。実 `task-state.json` と `task-graph-status.json` のnode/state/summary/hashを比較。
- C19: knowledge ref schema、日付、source実在、external input sha256、target task-spec非空、predecessor non-activeを検査。rendererも同契約を消費。
- evidence: `gate-final.json` をknowledge Loop A/B各3件の`ok`へ再生成。plan-findingsを58/130と現hashへ更新。
- generated harness: task-graph 4資産をbriefから決定論materializeし、同一brief2回byte一致、欠落/byte/profile driftをbuild-plan/lintで拒否。

## Verification

- plugin-dev-planner: 864 passed, 1 skipped
- Harness Creator: 372 passed
- route/inventory parity: PASS (2 routes)
- route reports `--complete`: PASS
- plan gates: index/DAG, unassigned, frontmatter, spec gates, 46-row matrix, surface inventory, handoff, runtime portability, task graph, task state, C18 parity, C19: all PASS
- C14: current plan is fixed-13-phase, adoption gate is explicitly not-applicable; target-shape behavior is covered by focused tests
- Harness materializer: same brief→same plan/assets; missing or byte/profile drift→FAIL

## Four-condition verdict

### Current declared build contract

| condition | verdict | evidence |
|---|---|---|
| 矛盾なし | PASS | state ownership、edge direction、final evidenceを単一化 |
| 漏れなし | PASS | C17-C19 target/runtime gatesとS5-S9 findingsを接続 |
| 整合性あり | PASS | schema/docs/tests/route/brief/build target parity |
| 依存関係整合 | PASS | planner+Harness Creator cross-contract tests、dangling producer fail-closed |

### Expanded generated-harness requirement

現 `engine: task-graph` は再現性のある **checklist-graph** 量産までPASSする。一方、plugin-dev-planner相当の `task-specs→graph→envelope→task-state/projection→discovered-task外ループ` を生成Harness自身へ同梱する **full task-spec graph** は未実装で、`full_task_spec_graph=false` と capability gaps により成功扱いを禁止した。この拡張要件の「漏れなし」は未達であり、既存 `with-task-graph-goalseek` planが明示する「build-pipeline task-graph非改変」境界を変更する structural follow-up として人間承認が必要。
