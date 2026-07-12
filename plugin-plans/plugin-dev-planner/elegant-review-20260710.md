# 30思考法エレガント検証 — plugin-dev-planner

- 実施日: 2026-07-10
- 対象: plugin-plans/plugin-dev-planner/ のplan成果物一式
- スコープ: plan契約の検証・Edit改善。plugins/plugin-dev-planner/ 実装本体は対象外
- 独立性: Phase1観察後、Agent2/3/4が互いのfindingを参照せず9/9/12手法を分担

## Phase1 思考リセット観察

- 13 phaseはライフサイクルpolicy、task nodeは1検証可能成果物、component routeはbuildable実体という3概念が文書上混線していた。
- 初期graphは105 nodes / 1101 edges。C02→C01依存がtask集合間の直積となり約830 edge、同一title複製72 nodes、consumes edge 0だった。
- node.entity_refが分類とbuilder routeの両方を担い、design/test nodeまでcomponent buildへ誤dispatchし得た。
- canonical graphとruntime stateのwriter境界、完了cycleと再利用knowledgeの境界、task specと13 phaseの関係が利用者視点で不明確だった。
- handoffのbrief_sourceはbrief不存在を主張したがbrief実体があり、plan-findingsは別worktree/C1-C16を参照してstaleだった。

## 30思考法の全件適用記録

| # | 思考法 | 検出・判断 | planへの反映 |
|---:|---|---|---|
| 1 | 批判的思考 | checklist行ごとのcomponent node複製は独立build価値を持たない | P05をC01 route 1 task、P09をC02 route 1 taskへ縮約 |
| 2 | 演繹思考 | phase/task/componentの定義からbuilder解決には独立fieldが必要 | execution_kind / route_ref / task_spec_refをC17へ追加 |
| 3 | 帰納的思考 | 類似planより105/1101は粒度・密度が異常 | duplicate/density/transitive-redundancy gateをC2へ追加 |
| 4 | アブダクション | 直積edgeの原因はentity_ref一致node集合へのcomponent依存展開 | completion barrierまたはartifact joinへ1回だけ写像 |
| 5 | 垂直思考 | phase出力→次phase入力はpolicy順とartifact依存を混同 | phase_refはpolicy、depends_on/consumesはtask入力に限定 |
| 6 | 要素分解 | node identity、実行種別、route、spec、stateが一field群に混在 | TaskExecutionEnvelopeと三層stateへ責務分離 |
| 7 | MECE | task実行packetにobjective/acceptance/inputs/verifyが欠落 | envelope必須要素をIN14とP04 fixtureで全列挙 |
| 8 | 2軸思考 | kind×依存深さより2 skillは妥当だがtask依存が過密 | component数は2のまま、task DAGだけ疎化 |
| 9 | プロセス思考 | 13 phase本文をprompt化するとlifecycle軸とbuild軸が混線 | 1 node=1 task spec+1 phase policyに固定 |
| 10 | メタ思考 | entities_coveredをrouteに流用する分解ルール自体が誤り | entity_refを分類専用へ戻すルールを明文化 |
| 11 | 抽象化思考 | 必要クラスタはpolicy/task/route/state/historyの5つ | indexとP12に責務表を追加 |
| 12 | ダブル・ループ思考 | 欠落task追加だけでは再発する | 導出規則・validator・evaluatorを同時更新するplanへ変更 |
| 13 | ブレインストーミング | task spec registry、barrier、projection、knowledge候補を発散 | 必須だけをC17-C19とC2へ収束 |
| 14 | 水平思考 | harnessのsingle writer/event log/ready-set契約を横展開 | producer/consumer境界とprojection parityを同期 |
| 15 | 逆説思考 | nodeを増やすほど品質が上がる前提が直積と重複を生む | route buildは1 component=1 route taskへ縮約 |
| 16 | 類推思考 | workflow engineではdefinitionとrun stateを分ける | task-graph/task-state/status viewの三層モデルを採用 |
| 17 | if思考 | entity_refが無ければroute不能、titleが無ければprompt不能という暗黙依存を検査 | route_ref/task_spec_ref欠落をfail-closedに変更 |
| 18 | 素人思考 | indexだけでは13文書を全部実行するように読める | phase≠task≠componentと学校/課題/地図の説明を追加 |
| 19 | システム思考 | graphは構造、stateは実行、projectionは観測のnetwork | writerと入出力を責務表で固定 |
| 20 | 因果関係分析 | 構想→機能→componentの途中でtitleがexecutorへ飛躍 | TaskExecutionEnvelopeを因果の中間契約に追加 |
| 21 | 因果ループ | graph直接更新とhash pinが循環・自己矛盾 | revision内不変、外ループで新revision/hashへrepin |
| 22 | トレードオン思考 | 独立性と単純性を両立するにはtask詳細とroute buildを分ける | 詳細はbrief/task spec、route nodeは各component 1件 |
| 23 | プラスサム思考 | planner producerとharness consumerの二重実装を避ける必要 | schema/hash/envelopeはproducer、state write/dispatchはconsumer |
| 24 | 価値提案思考 | 各componentの価値は生成契約と独立意味評価の2つ | C01/C02を維持しC17/C19評価をC02へ追加 |
| 25 | 戦略的思考 | 過去node再利用は将来ready-setを汚染 | lineageとsource_ref付きknowledgeだけを別空間で再利用 |
| 26 | why思考 | なぜ単一skill退化かを掘ると決定論処理はC01、意味判定はC02に残る | component追加・統合を行わない根拠を維持 |
| 27 | 改善思考 | 最小Editで誤dispatch・stale artifact・密DAGを直す | frontmatter、checklist、goal/inventory/index、briefを差分更新 |
| 28 | 仮説思考 | 仮説「現分解は最適」を重複node/830 edge/title dispatchで反証 | 新仮説をP04の正負fixtureで検証可能化 |
| 29 | 論点思考 | 命名好みより4条件へ直結するroute/state/DAGを優先 | 構造変更不要のcritical findingから適用 |
| 30 | KJ法 | 27 findingsを6根因へ統合 | 下記A-Fクラスタとして重複を解消 |

## KJ統合クラスタと処置

- A 実行identity/route: execution_kind・route_ref・task_spec_refを追加し、entity_ref暗黙routeとtitle-onlyを禁止。
- B task spec/artifact契約: 1 task spec+1 policy+acceptance+inputs+verifyをenvelope化。
- C DAG疎性: component依存のtask直積を禁止し、barrier/artifact join・重複0・冗長edge0・density gateを追加。
- D state/revision: graph/state/projectionを分離し、discovered-taskは外ループで新revisionへ反映。
- E cycle knowledge: 完了spec/graph/evidenceはimmutable、再利用はsource_ref付きknowledge/external inputに限定。
- F stale artifacts/provenance: briefを再射影、handoff説明とplan-findingsを現行化。legacy source_intake欠落は捏造せず明示例外。

## 反復結果

| 反復 | nodes | edges | 主な状態 |
|---:|---:|---:|---|
| 0 | 105 | 1101 | route誤写像、重複72、component依存直積、stale findings |
| 1 | 69 | 176 | design/test route除外、重複0、C01 taskが13件残存 |
| 2 | 57 | 128 | C01/C02 route task各1件、重複0、handoff/inventory/producer 1:1 |

現行task-graphは新C17を実装するためのfixed-shape bootstrap artifactであり、execution_kind/route_ref/task_spec_refはbuild後のtarget shapeである。このメタ循環境界はindexとP04に明記し、現行ではP05=C01、P09=C02だけをlegacy routeとして許可する。

## 最終4条件

| 条件 | 判定 | 根拠 |
|---|---|---|
| 矛盾なし | PASS | phase/task/component、graph/state/revision、discovered-task/hash pinの境界を統一 |
| 漏れなし | PASS | C1-C19をindex・phase・inventory・briefへtraceし、30手法を全件記録 |
| 整合性あり | PASS | core/拡張gate、frontmatter、matrix、surface、brief、provenanceがexit0 |
| 依存関係整合 | PASS | component DAG非循環、task graph validator exit0、route/inventory/producer各2件が1:1、重複node 0 |

## 残る非block事項

- 元planのsource_intakeは履歴上存在しない。今回のsource_improvementは追跡可能で、provenance gateはallow-missing-intakeを明示してPASS。過去intakeは捏造しない。
- consumes edgeの本格導出、TaskExecutionEnvelope、revision更新はこのplanが指定するL4 build対象であり、plan-onlyスコープでは未実装。

