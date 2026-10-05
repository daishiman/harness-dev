# Prompt: R0-context

> C24でcaller repo/config/content rootsを解決し、全read/write realpathがroot内であることをpreflightする

## Layer 1: 基本定義層

- `responsibility_id`: `R0-context`
- `skill`: `run-dev-graph-node`
- 不変目的: C24でcaller repo/config/content rootsを解決し、全read/write realpathがroot内であることをpreflightする
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- caller context、repo config、artifact input、graph/content候補path。

### 出力契約

- repository identityと全realpath containment判定を持つwriter preflight receipt。

### 責務境界

- graph/contentを変更せずroot外・broken symlink・別common-dirを許容しない。

### 受入条件

- 全候補pathがroot内でrepository_idがconfig/graphと一致する。

## Layer 3: インフラ層

- 使用資産: `resolve-repo-context.py --mode write`。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-node/R0-context`

### 5.2 ゴール定義

- 目的: C24でcaller repo/config/content rootsを解決し、全read/write realpathがroot内であることをpreflightする
- 達成ゴール: repository identityと全realpath containment判定を持つwriter preflight receiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全候補pathがroot内でrepository_idがconfig/graphと一致する

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- PASS receiptだけをR1/R3/R4へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

