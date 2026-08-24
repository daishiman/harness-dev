# Prompt: R1-elicit

> 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する

## Layer 1: 基本定義層

- `responsibility_id`: `R1-elicit`
- `skill`: `run-dev-graph-render`
- 不変目的: 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- caller graph、scope ID、scope内のfeature packageに対応するC02 registration receipt群、output path、repo context。

### 出力契約

- caller repo authority、実在subgraph、featureごとのC02 receipt、repo内HTML outputを確定したrender request。

### 責務境界

- graph/contentを変更せずrepo外出力/外部URLを受理しない。

### 受入条件

- scope実在、固定点closure確定、子taskを持つfeatureとC02 receiptの1:1対応、graph/receipt/output realpath root内、symlink通過・file位置のdirectory 0件、input digest固定になる。

## Layer 3: インフラ層

- 使用資産: Read/AskUserQuestionとC24/C11。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-render/R1-elicit`。親SKILLの `goal_seek.fork=inline` に従いmain contextで実行し、別contextにforkしない。

### 5.2 ゴール定義

- 目的: 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: 実在subgraphとrepo内HTML outputを確定したrender requestが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] scope実在・closure・C02 receipt 1:1対応、graph/receipt/output realpath root内、symlink通過・file位置のdirectory 0件、input digest固定になる

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- R2へrequestを渡す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
