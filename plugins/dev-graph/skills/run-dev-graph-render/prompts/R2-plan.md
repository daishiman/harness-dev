# Prompt: R2-plan

> SVGノード配置とHTML/CSSレイアウトの生成計画を組み立てる

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-render`
- 不変目的: SVGノード配置とHTML/CSSレイアウトの生成計画を組み立てる
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- validated subgraph、node/edge/parent_feature、request。

### 出力契約

- SVG layout、edge layer、X/Y progress、inline CSS/JSのrender model。

### 責務境界

- CDN/npm/外部参照を採用せずfeature間/内edgeを混同しない。

### 受入条件

- 全node/edge一意配置、feature X/Yがtask実数と一致する。

## Layer 3: インフラ層

- 使用資産: Readとrender-graph-html contract。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-render/R2-plan`。重い判断または独立検証は `Agent` で分離 context に fork する。

### 5.2 ゴール定義

- 目的: SVGノード配置とHTML/CSSレイアウトの生成計画を組み立てる
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: SVG layout、edge layer、X/Y progress、inline CSS/JSのrender modelが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] 全node/edge一意配置、feature X/Yがtask実数と一致する

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- R3へmodel/countsを渡す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

