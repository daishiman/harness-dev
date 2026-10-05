# Prompt: R3-schedule

> binding=beadsはC28のbd ready --jsonかつstatus/depends_on edge parity=confirmedの候補だけ、github/noneはstatus=activeかつconfirmed/pass/readiness completeだけをschedule-graph.pyへ渡し、resource_scope非重複batchへ整形する

## Layer 1: 基本定義層

- `responsibility_id`: `R3-schedule`
- `skill`: `run-dev-graph-schedule`
- 不変目的: binding=beadsはC28のbd ready --jsonかつstatus/depends_on edge parity=confirmedの候補だけ、github/noneはstatus=activeかつconfirmed/pass/readiness completeだけをschedule-graph.pyへ渡し、resource_scope非重複batchへ整形する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- schedule plan、candidates、dependencies、leases、touches。

### 出力契約

- feature/task別ready-set、batches、conflicts、branch/claim command。

### 責務境界

- read-only、自身でclaimせず未充足/lease衝突を推薦しない。

### 受入条件

- 全推薦eligible、batch touch重複0、branch=devgraph/idになる。

## Layer 3: インフラ層

- 使用資産: schedule-graphとAgent verifier。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-schedule/R3-schedule`

### 5.2 ゴール定義

- 目的: binding=beadsはC28のbd ready --jsonかつstatus/depends_on edge parity=confirmedの候補だけ、github/noneはstatus=activeかつconfirmed/pass/readiness completeだけをschedule-graph.pyへ渡し、resource_scope非重複batchへ整形する
- 達成ゴール: feature/task別ready-set、batches、conflicts、branch/claim commandが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全推薦eligible、batch touch重複0、branch=devgraph/idになる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- public claim commandと返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

