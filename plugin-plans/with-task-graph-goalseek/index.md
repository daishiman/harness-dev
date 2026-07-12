---
id: IDX0
title: with-goal-seek engine:task-graph 変種追加計画 index (main)
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
    reason: "harness-creator は distributable:false かつ NEVER_DISTRIBUTE denylist(改名前の旧名由来)対象で PKG-001..015 の配布契約検査は非該当。本 plan は既存 run-build-skill skill 内部への engine 変種追加のみで配布境界自体を変更しない"
  governance:
    applicable: false
    reason: "run-skill-rubric-governance が所有する評価 rubric 正本(plan-rubric.json 等)は本 plan で変更しない。本 plan は run-build-skill の with-goal-seek engine 拡張であり rubric governance の対象外"
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    enabled: false
    reason: "本 plan は既存 skill(run-build-skill)への engine 変種追加であり新規 skill 作成を伴わない。self-reflect(C02)は既存 progress.json への自己追記のみで外部 Notion 受け皿への feedback 配備を伴わない"
---

# with-goal-seek engine:task-graph 変種追加計画 index (main)

> 本計画は新規プラグイン構想ではなく、既存プラグイン `harness-creator` の `run-build-skill` へ、量産される全出力ハーネスの goal-seek に「task-graph 順序駆動(依存充足順の実行 + 実行中に発見した新タスクの自己反映)」と「生成 harness の skill / slash-command / sub-agent / script 横断 dependency graph の knowledge 化・利用」を、既存 `with-goal-seek` の **engine 変種 `engine: task-graph`** として追加する `existing-plugin-update` 計画である。独立 combinator flag(`with_task_graph`)は新設しない。設計原則は【単一truth】: 別状態ファイル(task-graph.json)を新設せず、with-goal-seek の既存状態(progress.json の checklist + intermediate.jsonl アンカー)のみを唯一の真実源とする。本計画はこの能力ギャップを、既存 build-pipeline task-graph(`plugin-plans/harness-creator/` が実装した producer/consumer 分離型・`/capability-build` 消費側機構)とは**別概念**の「1 ハーネス自己完結・単一 self-writer」engine 変種として、checklist C1-C12(H1-H6 の解消と cross-surface dependency knowledge の補完含む)として解消する。

## 基本定義
- **プラグイン slug**: `harness-creator`(plan_dir=`plugin-plans/with-task-graph-goalseek/`・build 対象は `plugins/harness-creator/skills/run-build-skill/` 配下のみ)。
- **最上位目的(purpose)**: 量産される出力ハーネスの goal-seek に task-graph 順序駆動を、既存 with-goal-seek の engine 変種 `engine: task-graph` として追加する開発計画を作る(goal-spec.json purpose 逐語)。
- **仕様駆動(大前提)**: 要件の正本は `goal-spec.json` の checklist(C1-C12)。仕様書(本 index + 13 phase + component-inventory)はその被覆であり、実装との乖離が出たら仕様を先に更新してから build へ戻す(spec-first)。
- **スコープ(含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `handoff-run-plugin-dev-plan.json` + `envelope-draft/plugin.json` の生成(計画 = L3 契約まで)。
- **スコープ(含まない)**: 実 `plugins/harness-creator/` への script/skill 実装反映(L4・後段 run-skill-create/run-build-skill(parent-skill-build)への実装が委譲先)。既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)の一切の改変(goal-spec constraints #2)。独立 combinator flag の新設(goal-spec constraints #3)。

## ドメイン知識
- **engine 変種**: with-goal-seek の `goal_seek.engine` フィールド(既定 `inline`、追加 opt-in 値 `task-graph`)。独立 combinator flag ではなく、既に default-ON の with-goal-seek 内部の選択値として表現する(H5 解消)。
- **depends_on**: checklist item への additive フィールド(`goal-seek-loop.schema.json` へ追加)。array<string>・pattern `^C[0-9]+$`・default `[]`。依存先 item が全て `status==done` になって初めて当該 item は ready 集合に入る。
- **ready 集合**: depends_on が全充足かつ `status==pending` の checklist item を id 昇順で決定論算出したもの(C01 ready-set-from-checklist.py が算出)。write_scope フィールド・tie-break 機構は持たない(逐次単一 self-writer ゆえ構造的に不要・H1 解消)。
- **self-reflect append**: 実行中に発見した新規タスクを、別状態ファイルを新設せず checklist(progress.json)の末尾へ新しい item として追記する仕組み(C02 self-reflect-append.py)。追記された item は done-judge が毎回スキャンする同一配列の一部になるため、発見した課題が完了判定へ反映されない非統合は構造的に発生しない(単一truth原則・H3 解消)。
- **consumption verifier**: depends_on 消費(ready 集合の実行)と self-reflect 完了gate が実際に機能していることを、既存 with-goal-seek の intermediate.jsonl アンカー検査と同型の機械検査トークンとして生成 SKILL.md へ埋め込む仕組み(C03/C04 が担当・H4 解消)。
- **既存 compute-ready-set.py の正しい位置付け**(H2 解消): `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py` の write_scope tie-break(id 昇順で勝者 1 件を採用し残りを deferred/conflicts へ回す)は「バグ」ではなく、複数 candidate が同時に ready になり得る**並列/多ノード dispatch モデル**を前提とした意図的な fail-closed 回避設計である(同ファイル docstring L16-27・実装 L90-109)。本計画の engine:task-graph 変種は**逐次単一 self-writer**であり、この並列 dispatch 前提が構造的に成立しないため、同型の tie-break 機構を複製しない。詳細な file:line 引用は `phase-02-design.md` H2 節を参照。
- **既存 build-pipeline task-graph との区別**: `plugin-plans/harness-creator/` が実装した producer(plugin-dev-planner)/ consumer(capability-build 側 `/capability-build` route-mode dispatch)の片方向 writer 2 プラグイン構成であり、本計画の「with-goal-seek engine:task-graph 変種」とは別概念。本計画はこれを一切改変しない。

## インフラ
- ツール: Read/Glob/Grep(既存正本確認)・Write/Edit(plan 成果物生成)・`Bash(python3 *)`(`plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-*.py` 系の決定論ゲート実行)。
- 実行環境前提: cwd = リポジトリルート(`/Users/dm/dev/dev/xlocal/xl-skills/.worktrees/task-20260705-210449-wt-3`)。C01-C04/C06-C08 の実装は Python 標準ライブラリのみで完結する(`stdlib_only: true`)。
- 依存: `plugins/harness-creator/skills/run-build-skill/` の既存 combinator 機構(`render-combinators.py` / `schemas/build-flags.schema.json` / `schemas/goal-seek-loop.schema.json` / `scripts/lint-goal-seek.py`)。

## 環境ポリシー
- 品質基準: 全 buildable component が harness_coverage.min>=80 + quality_gates(p0_lint 網羅 / build_trace=required / elegant_review C1-C4 all_pass / content_review verdict=PASS / evaluator threshold>=80,high_max==0)を携帯する。
- 共通ポリシー: 具体値は self-relative パス(`plugins/harness-creator/...`)で表現し `$PROJECT_ROOT`/`$CLAUDE_PLUGIN_ROOT` の未解決展開を残さない。
- エスカレーション方針: 決定論ゲート FAIL は該当成果物を修正し最大反復後も未達なら orchestrator(呼び出し元)へ差し戻す。単一 skill 退化の疑いがある場合は不要 surface の根拠を追加するか component 分解を見直す。

## Component 一覧 (1行 role 表)
| id | component_kind | build_target | 責務(1行) |
|---|---|---|---|
| C01 | script | `plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/ready-set-from-checklist.py` | checklist の depends_on から ready 集合をステートレス算出(write_scope 機構なし) |
| C02 | script | `plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/self-reflect-append.py` | discovered task を checklist 末尾へ単一truth追記(既存 item 不変・サイクル検査) |
| C06 | script | `plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/extract-capability-dependency-graph.py` | 生成 harness の skill/command/agent/hook/script surface から dependency graph を抽出 |
| C07 | script | `plugins/harness-creator/skills/run-build-skill/templates/task-graph-engine/scripts/record-capability-graph-knowledge.py` | dependency graph を Loop A/Loop B knowledge entry へ source_ref 付きで記録 |
| C03 | script | `plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py` | with-goal-seek へ task-graph 配線・C06/C07 同梱・knowledge consult 手順を追加 |
| C04 | script | `plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py` | engine:task-graph 変種の SSOT drift + consumption verifier トークンを self-test 検査 |
| C08 | script | `plugins/harness-creator/skills/run-build-skill/scripts/lint-capability-graph-knowledge.py` | dependency graph knowledge の同梱・記録・各 surface consult 配線を検査 |
| C05 | skill | `plugins/harness-creator/skills/run-build-skill/` | C01-C04/C06-C08 機構を SKILL.md prose Step へ統合(update) |

## ゲート一覧 (同梱決定論ゲート 11 本)
本表は `assign-plugin-plan-evaluator`(`plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/scripts/evaluate-plan.py` の `_gate_defs()` + `references/plan-rubric.json` の `deterministic_gates` G1-G11)が実際に走らせるゲート集合と 1:1 で一致する(スコープは R2/R3 生成物=本 plan_dir。goal-spec.json 自体の検証(`check-plugin-goal-spec.py`)は R1 の入力検証であり、evaluator が回す R2/R3 出力ゲート集合には含まれないため本表から除外する)。

| # | 区分 | script | 対応 checklist | evaluator gate id |
|---|---|---|---|---|
| 1 | core | `verify-index-topsort.py` | C4 | G1 |
| 2 | core | `detect-unassigned.py` | C5 | G2 |
| 3 | core | `check-spec-frontmatter.py` | C1,C4 | G3 |
| 4 | core | `check-spec-gates.py` | C2 | G4 |
| 5 | core | `validate-task-graph.py` | C5 | G11 |
| 6 | extended | `check-spec-matrix-coverage.py --self-test` | C12 | G5 |
| 7 | extended | `check-spec-matrix-coverage.py` (PLAN_DIR) | C12 | G6 |
| 8 | extended | `check-surface-inventory.py` | C1 | G7 |
| 9 | extended | `check-build-handoff.py` | C3 | G8 |
| 10 | extended | `check-requirements-coverage.py` | C1,C2 | G9 |
| 11 | extended | `check-runtime-portability.py` | C1 | G10 |

core 5 種(#1-5)+ 拡張 6 呼び出し(#6-11、うち matrix-coverage は self-test/PLAN_DIR の 2 回呼び出し)= 合計 11 本。本表が唯一のゲート内訳表であり、他 phase ファイルはこの表を引用する(単一表原則)。`validate-task-graph.py` は本 plan 自身の build-dispatch メタ成果物 `task-graph.json`(`derive-task-graph.py` が component-inventory.json + 13 phase §5 完了チェックリストから決定論導出する第 3 の射影)の DAG 非循環/orphan 0/producer 一意/inventory 依存整合/非正準拒否を検査し、checklist C5(依存 DAG 非循環)に detect-unassigned.py と並んで結線される。

## フェーズ一覧

1. P01 — requirements(要件)/ 未実施
2. P02 — design(設計)/ 未実施
3. P03 — design-review(レビュー)/ 未実施
4. P04 — test-design(テスト)/ 未実施
5. P05 — implementation(実装)/ 未実施
6. P06 — test-run(テスト)/ 未実施
7. P07 — acceptance-criteria(判定)/ 未実施
8. P08 — refactoring(改善)/ 未実施
9. P09 — quality-assurance(品質)/ 未実施
10. P10 — final-review(レビュー)/ 未実施
11. P11 — evidence(検証)/ 未実施
12. P12 — documentation(文書)/ 未実施
13. P13 — release(完了)/ 未実施

## 完了チェックリスト
goal-spec checklist 全項目(C1-C12)の受入基準を二値で列挙する:
- [ ] C1: `component-inventory.json` が with-goal-seek engine 変種の buildable 実体(C01-C08)を分解し独立 combinator flag を新設せず、`plugin_level_surfaces`(8 surface)の採否を記録している
- [ ] C2: 各 buildable component(C01-C08)が quality_gates + harness_coverage を携帯している
- [ ] C3: `handoff-run-plugin-dev-plan.json` が各 component の builder/build_kind/build_args/build_target を持ち routes↔inventory が 1:1 対応する
- [ ] C4: 本 index.md が P01..P13 を phase_number 昇順で全列挙し plugin_meta と本節(完了チェックリスト)+ 受入確認章 + Component 一覧(1行 role 表)を携帯している
- [ ] C5: component 依存 DAG(C01→依存なし、C02→C01、C06→C01/C02、C07→C02/C06、C03→C01/C02/C06/C07、C04→C03、C08→C03/C06/C07、C05→C03/C04/C06/C07/C08。矢印は X→Y=X depends_on Y で統一)が非循環で unassigned 0 件である
- [ ] C6: 【単一truth】checklist を唯一の状態とし self-reflect が discovered task を checklist item として追記して完了判定を gate する設計が `phase-02-design.md` H3 節に明記されている
- [ ] C7: 逐次単一 self-writer ゆえ write_scope 並列衝突機構は不要であること、および既存 compute-ready-set.py の tie-break が並列 dispatch 前提の意図的機構(バグでない)であることが file:line 引用付きで `phase-02-design.md` H1/H2 節に明記されている
- [ ] C8: 生成物が依存順序を実際に消費し discovered task が完了を gate し、cross-surface dependency graph knowledge を各 surface が consult することの consumption verifier が intermediate.jsonl アンカー検査と同型で `phase-02-design.md` H4/H6 節に埋め込み設計として明記されている
- [ ] C9: 既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)を無改変とする境界が本 index の ## 受入確認 に明記されている
- [ ] C10: default/opt-in 軸が with-goal-seek の engine 選択(engine: inline 既定 / engine: task-graph)として確定し purpose と設計文書で一貫している(`phase-02-design.md` H5 節)
- [ ] C11: 同梱決定論ゲート(core 5 + 拡張 6 = 11 本)が全 exit0 で、上記 ## ゲート一覧 の単一表で内訳が列挙され各 gate が checklist 項目へ結線されている
- [ ] C12: 適用される harness-creator 仕様 46 行の焼き先が反映され、C12 の機械判定(check-spec-matrix-coverage.py)と elegant-review C1-C4 全 PASS の設計意図(`phase-03-design-review.md` LR1-LR4)が別項目に分離されている
- [ ] 基本定義/ドメイン知識/インフラ/環境ポリシーの各節が非空である
- [ ] 13 フェーズファイルが全て存在し `entities_covered` で C01-C08 が全て >=1 phase から参照される(orphan 0 件)

## 受入確認
build 後に組み上がった実プラグイン(`plugins/harness-creator/skills/run-build-skill/`)が purpose を満たすか確認する trace:
- goal-spec checklist C1-C12 の全項目が上記完了チェックリストで done 相当になっていること。
- brief.goal_seek.engine=task-graph 指定で生成したハーネスの SKILL.md に engine:task-graph 変種の配線サブセクション(『### ゴールシーク配線(task-graph 変種)』『### ゴールシーク検証(task-graph 変種・機械検査)』)が注入され、同梱 scripts/ に C01/C02/C06/C07(ready-set-from-checklist.py / self-reflect-append.py / extract-capability-dependency-graph.py / record-capability-graph-knowledge.py)がコピーされ、C04 拡張後の `lint-goal-seek.py` self-test と C08 `lint-capability-graph-knowledge.py` が exit0 になること。
- **既存 build-pipeline task-graph(`plugin-plans/harness-creator/`、producer=plugin-dev-planner / consumer=capability-build の `/capability-build` route-mode dispatch 機構)は本計画の対象外であり、本計画の build_target・side_effect_targets のいずれにも `plugin-plans/harness-creator/` 配下のファイルは一切含まれない。** この非改変境界は goal-spec constraints #2 / checklist C9 の直接充足であり、`plugins/harness-creator/skills/run-build-skill/` 配下(C01-C08)への変更のみが本計画のスコープである。
- 独立 combinator flag(`with_task_graph`)は一切追加されておらず、default/opt-in 軸は with-goal-seek 自体の `engine` 選択値(既定 `inline` / opt-in `task-graph`)としてのみ表現されていること(goal-spec constraints #3 / checklist C10)。
- 単一truth設計(H3)と write_scope 並列衝突機構不要の判断根拠(H1/H2)は `phase-02-design.md` の該当節で機械可読な形で明記され、`lint-goal-seek.py` 拡張 self-test(C04)と `lint-capability-graph-knowledge.py`(C08)が consumption verifier / dependency knowledge consult トークンの存在を機械検査する。
