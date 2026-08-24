# Prompt: R2-plan

> 自然文のwantからfeatureノード群+architectureノード+機能間depends_onへのマクロ分解案を組み立てる (1機能=13タスク仕様書への細分解はsystem-dev-plannerへ委譲しここでは行わない)

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-decompose`
- 不変目的: 自然文のwantからfeatureノード群+architectureノード+機能間depends_onへのマクロ分解案を組み立てる (1機能=13タスク仕様書への細分解はsystem-dev-plannerへ委譲しここでは行わない)
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- macro brief、existing architecture/features、routing policy。

### 出力契約

- C02へ渡す `macro-intent.schema.json` 準拠intent (`schema_version/observed_at/project_id/source_digest/architecture/features`)。graph nodeとreceiptは出力しない。

### 責務境界

- 13 phase task、candidate graph、receiptを手書きせずarchitectureを複製せずdraftを投影しない。feature intentは `graph_node_id/title/domain/purpose/goal/scope_in/scope_out/acceptance/depends_on/resource_scope` だけを持ち、`architecture_refs` はC02がtop-level architectureから導出する。macro intentからgraphへの正規化はC02 `preview-macro|apply-macro`だけが行う。

### 受入条件

- macro intentにarchitecture 1件、feature 1件以上、feature間だけを参照するdepends_on、feature必須意味fieldが揃い、C02 schema検証へ入力可能になる。

## Layer 3: インフラ層

- 使用資産: Read。意味分解をmacro intentへ限定し、schema/DAG検証は後段C02とAgent macro verifierへ委譲する。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-decompose/R2-plan`。重い判断または独立検証は `Agent` で分離 context に fork する。

### 5.2 ゴール定義

- 目的: 自然文のwantからfeatureノード群+architectureノード+機能間depends_onへのマクロ分解案を組み立てる (1機能=13タスク仕様書への細分解はsystem-dev-plannerへ委譲しここでは行わない)
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: top-level architecture 1件とfeature intent群、機能間depends_onだけを持つmacro intentが生成され、graph node共通fieldと`architecture_refs`の導出はC02に委譲された状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] 循環0、task粒度混入0、feature必須field欠落0になる

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- macro intentをR3のC02 `preview-macro`→`apply-macro`、ready featureをR2bへ渡す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
