# Prompt: R4-tombstone

> `diff-github-issues.py` の計画が示す GitHub Issue の close/delete (自分では判定しない) を受け取り、C02 経由でローカルグラフノードを物理削除せず tombstone/status 遷移 (open→closed 等) として双方向伝播する

## Layer 1: 基本定義層

- `responsibility_id`: `R4-tombstone`
- `skill`: `run-dev-graph-sync`
- 不変目的: `diff-github-issues.py` の計画が示す GitHub Issue の close/delete (自分では判定しない) を受け取り、C02 経由でローカルグラフノードを物理削除せず tombstone/status 遷移 (open→closed 等) として双方向伝播する
- inventory の summary (frontmatter の responsibilities と一致させる文で、ここでは書き換えない): 「GitHub Issue の close/delete を検知し、C02 経由でローカルグラフノードを物理削除せず tombstone/status 遷移 (open→closed 等) として双方向伝播する」。今の手順では close/delete の判定は `diff-github-issues.py` が行い、この責務はその計画を C02 に渡すだけである。
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- GitHub close/delete event、local node/linkage、last-synced snapshot。

### 出力契約

- C02向けtombstone/status transition requestとpropagation result。

### 責務境界

- nodeを物理削除せずC02迂回でstatusを書かない。

### 受入条件

- graph_node_id/linkageを保持し許可transitionだけが反映される。
- 削除は `diff-github-issues.py` の tombstone 計画を当てた後の再計画が `converged` になり、一時的な失敗は tombstone にならず retry に残る。

## Layer 3: インフラ層

- 使用資産: gh-bridgeとSkill run-dev-graph-node。Issue の close と削除は `diff-github-issues.py` の計画から受け取り、自分で判定しない。close は state import (status=closed)、削除 (linked number が解決しない・HTTP 410) は `kind: remote-deleted` の import (status=tombstoned) として同計画の `update_input` に入るので、それを C02 `update` に渡す。tombstone 済みの node は次の計画で `deleted_issues` (解決済み) に移り、missing を残さず収束する。
- 一時的な失敗 (rate limit・HTTP 429/5xx・timeout) は `missing_issues` の `action: retry`、権限・repository・HTTP 404 の失敗は `action: investigate` で、どちらも tombstone にしない。package member の削除は C02 が拒否するので `conflicts` の `remote-deleted` (local-authority) として R6 に渡す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-sync/R4-tombstone`

### 5.2 ゴール定義

- 目的: `diff-github-issues.py` の計画が示す GitHub Issue の close/delete (自分では判定しない) を受け取り、C02 経由でローカルグラフノードを物理削除せず tombstone/status 遷移 (open→closed 等) として双方向伝播する
- 達成ゴール: C02向けtombstone/status transition requestとpropagation resultが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] graph_node_id/linkageを保持し許可transitionだけが反映される
- [ ] 削除の tombstone 計画を当てた後の再計画で missing_issues が0件になり、一時的な失敗は retry のまま残る

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- receiptをsync ledgerへ戻す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

