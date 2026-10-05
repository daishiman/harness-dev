# Prompt: R1-elicit

> 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する

## Layer 1: 基本定義層

- `responsibility_id`: `R1-elicit`
- `skill`: `run-dev-graph-render`
- 不変目的: 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- caller graph、scope ID、output path、repo context。

### 出力契約

- 実在subgraphとrepo内HTML outputを確定したrender request。

### 責務境界

- graph/contentを変更せずrepo外出力/外部URLを受理しない。

### 受入条件

- scope実在、output realpath root内、input digest固定になる。

## Layer 3: インフラ層

- 使用資産: Read/AskUserQuestionとC24/C11。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-render/R1-elicit`

### 5.2 ゴール定義

- 目的: 可視化対象範囲と静的HTML出力先パスをヒアリングして確定する
- 達成ゴール: 実在subgraphとrepo内HTML outputを確定したrender requestが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] scope実在、output realpath root内、input digest固定になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R2へrequestを渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

