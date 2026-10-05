# Prompt: R2-plan

> 5 artifact kindを横断し、C19が取り込んだsystem-spec-harness成果物とexternal plugin system-dev-planner (run-system-dev-plan) 由来のsystem task planを引用する要件抽出計画を組み立てる

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-requirements`
- 不変目的: 5 artifact kindを横断し、C19が取り込んだsystem-spec-harness成果物とexternal plugin system-dev-planner (run-system-dev-plan) 由来のsystem task planを引用する要件抽出計画を組み立てる
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- 5 artifact kind、C19 lineage、system planner package/plan refs。

### 出力契約

- requirement→source→system task→handoff fieldのtrace plan。

### 責務境界

- elicitation/compile/13task生成を複製せず実装codeを計画しない。

### 受入条件

- 各requirementがconfirmed source/package phaseへ追跡できる。

## Layer 3: インフラ層

- 使用資産: Readとrun-system-dev-plan成果物。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-requirements/R2-plan`

### 5.2 ゴール定義

- 目的: 5 artifact kindを横断し、C19が取り込んだsystem-spec-harness成果物とexternal plugin system-dev-planner (run-system-dev-plan) 由来のsystem task planを引用する要件抽出計画を組み立てる
- 達成ゴール: requirement→source→system task→handoff fieldのtrace planが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 各requirementがconfirmed source/package phaseへ追跡できる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R2b/R3へtrace planを渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

