# task-progress (live 実行状態・派生ビュー)

> `project-task-status.py` 生成の派生ビュー。構造の正本は `task-graph.json`、状態の正本は build dir の `task-state.json`。手書き編集しない (再生成で上書き)。build 異常終了時は最後の 投影時点のスナップショットで stale の可能性がある (最新は再投影で得る)。

- 凡例: ✓=done / ▶=running / ✗=blocked / ☐=pending / ⏳=未処理の発見タスク (外ループ待ち)
- 完了率: **100%** (40/40)
- 状態内訳: done=40 / running=0 / blocked=0 / pending=0
- route-report 数: 14
- graph_hash pin: `sha256:8a5e843db8ab76ed2e8f94d988e4157eb59a4717c04b73b462be8a12a4ac70f0`

## このタスクの目的と、導入で得られる価値

### 技術的な詳細 (エンジニア向け)
- **本質的な問題・課題**: 従来の『13 lifecycle文書 + 可変N task』は、説明用phaseと実行taskを二重化し、Dev Graphのマクロ責務とSystem Dev Plannerのミクロ責務を混線させていた。新契約では1 featureをexact 13 executable task specsへ変換し、P01..P13の欠落・重複・14件目をfail-closedする。
- **導入すると何ができるようになるか**:
  - system-spec-harness の確定成果物 (system-spec/index.md・00-requirements-definition.md 等の確定章 + architecture graph node) を読み、implementation_readiness (complete/incomplete) を決定論判定する共有ゲート。
  - guard-implementation-readiness。
  - run-system-dev-plan。
  - assign-system-dev-plan-evaluator。
  - システム開発構想からgoal-specを確定したいとき、dev-graph呼出し引数とsystem-spec-harness確定成果物を引用入力として最尤ゴールを推定したいときに使う。
  - 1 featureをworkstream観点で分析し、P01..P13に1件ずつ対応するexact 13 executable task specs、13-entry inventory、13-node intra-feature DAGを生成したいときに使う。
  - 生成したtask-spec/workstream-inventory/task-graphが4条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) と決定論ゲートを満たすか独立評価したいときに使う。
  - システム開発タスク仕様書生成をdev-graphから (または人手で) 手動起動する。
- **責務境界・非目標**:
  - 実プラグインは生成せず、goal-spec + 13 phase + workstream-inventory + task-graph + handoff の L3 plan までに留める。
  - 仕様書・アーキテクチャの内容構築 (ヒアリング/出典取得/compile/完成度評価) は plugins/system-spec-harness/ へ委譲し複製しない (DRY)。system-dev-planner は system-spec-harness の確定成果物 (system-spec/index.md・00-requirements-definition.md 等の確定章・architecture graph node) を引用入力とする。
  - ハーネスcode/assetsはsymlink物理元からロードしてよいが、content/config/state/cache/lock authorityは呼出元repositoryに限定し、symlink物理元や別repositoryの管理contentを読書きしない。
  - .dev-graph/config.json は repository 相対 path のみを許可し、issues/tasks/specs/architecture/docs/system-spec/published/staging/state/cache/lock roots を map する。absolute path、.. traversal、symlink escape、realpath(root外) は拒否する。
  - init はrepo-local config/directories/editable templatesを冪等に生成し、既存docs/specs/architecture/tasks/issuesを上書きしない。複数repo同時実行でもstate/cache/lock/stagingを共有しない。
- **目的 (何をするか)**:
  - dev-graphが管理する1つのfeatureを入力に
  - その機能を達成するPhase 1〜13の小さな実行タスク仕様書を各phaseちょうど1件
  - 合計13件と機能内依存DAGへ変換するper-featureミクロファクトリsystem-dev-plannerを計画するfeature・architecture・feature間依存は生成せずdev-graphへ委譲し
  - 13 taskは共通parent_feature/feature_package_idを持ってatomic登録される
- **背景・前提**:
  - 従来の『13 lifecycle文書 + 可変N task』は、説明用phaseと実行taskを二重化し、Dev Graphのマクロ責務とSystem Dev Plannerのミクロ責務を混線させていた。
  - 新契約では1 featureをexact 13 executable task specsへ変換し、P01..P13の欠落・重複・14件目をfail-closedする。
  - 仕様/architecture内容はsystem-spec-harnessを引用し、feature間依存はdev-graphのfeature DAGを正本とする。
  - 実行中の追加作業は該当phaseへのEditまたは新feature candidateとしてマクロ層へ返す。
- **到達状態 (Goal)**: system-dev-planner自身のL3 plugin planと、runtime出力であるexact 13-task feature execution package契約・13-node DAG・handoff・atomic promotion・multi-repository isolationが決定論ゲートと独立評価で検証可能な状態になっている

## タスクの依存関係 (何が何に依存して進むか)
> 全 40 タスク・92 依存エッジ。各フェーズの詳細は下記チェックリスト、完全な関係は HTML レポートを参照。
- 起点タスク (依存なしで最初に着手可能): `S01`

## P01
> 🎯 何のため: 何を作るか — 要件と作業方針を固める
- ✓ `P01` requirements
- ✓ `S01` 目的・境界・source pin・repo-local要件を確定する

## P02
> 🎯 何のため: どう作るか — 構成・データ・依存を設計する
- ✓ `P02` design
- ✓ `S02` workstream・repo runtime・promotion契約を設計する

## P03
> 🎯 何のため: 設計を独立レビューで検証する
- ✓ `P03` design-review
- ✓ `S03` 独立design reviewを通す

## P04
> 🎯 何のため: 検証方法 (テスト) を先に設計する
- ✓ `P04` test-design
- ✓ `S04` criteriaとnegative test matrixをRedで固定する

## P05
> 🎯 何のため: 各部品を実際に作る (実装)
- ✓ `B-C01` run-system-dev-planをbuildする
- ✓ `B-C02` assign-system-dev-plan-evaluatorをbuildする
- ✓ `B-C03` goal elicitor agentをbuildする
- ✓ `B-C04` workstream architect agentをbuildする
- ✓ `B-C05` independent evaluator agentをbuildする
- ✓ `B-C06` system-dev-plan commandをbuildする
- ✓ `B-C07` readiness/containment hookをbuildする
- ✓ `B-C08` readiness validatorをbuildする
- ✓ `B-C09` caller repository resolverをbuildする
- ✓ `B-C10` repo-local idempotent initをbuildする
- ✓ `B-C11` same-digest atomic promoterをbuildする
- ✓ `B-C12` staging生成物deterministic validatorをbuildする
- ✓ `D-C13` system plan lock lifecycle managerをbuildする
- ✓ `D-C14` system build handoffとregistration receipt境界をbuildする
- ✓ `P05` implementation
- ✓ `S05` 14 componentのL4 build完了を集約する

## P06
> 🎯 何のため: 作った部品を動かして検証する
- ✓ `P06` test-run
- ✓ `S06` coverageとmulti-repo integration testを実行する

## P07
> 🎯 何のため: 合格ライン (受け入れ基準) を定める
- ✓ `P07` acceptance-criteria
- ✓ `S07` purpose由来の受入基準を確定する

## P08
> 🎯 何のため: 重複を整理し保守しやすくする
- ✓ `P08` refactoring
- ✓ `S08` system task templateのSSOTを正規化する

## P09
> 🎯 何のため: 全体の品質ゲートを通す
- ✓ `P09` quality-assurance
- ✓ `S09` quality/security/portability gatesを確認する

## P10
> 🎯 何のため: 最終レビューで仕上がりを確認する
- ✓ `P10` final-review
- ✓ `S10` 独立final reviewを通す

## P11
> 🎯 何のため: 検証した証拠を残す
- ✓ `P11` evidence
- ✓ `S11` 再現可能なgate evidenceを集約する

## P12
> 🎯 何のため: 使い方・導入手順を文書化する
- ✓ `P12` documentation
- ✓ `S12` 利用・導入・復旧文書を確定する

## P13
> 🎯 何のため: リリースしてよいか判定する
- ✓ `P13` release
- ✓ `S13` L3 planをrelease-readyとして引き渡す

