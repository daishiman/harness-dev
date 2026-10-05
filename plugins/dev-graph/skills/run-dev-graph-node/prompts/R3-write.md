# Prompt: R3-write

> artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する

## Layer 1: 基本定義層

- `responsibility_id`: `R3-write`
- `skill`: `run-dev-graph-node`
- 不変目的: artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- containment receipt、classification decision (bind-github では不要)、artifact・feature package・bind-github の `bindings[]` のいずれか、R2 preview の `graph_revision_before`。apply の入力 JSON には必ず `expected_graph_revision` として渡し、省略しない (省略すると writer が `missing_expected_graph_revision` で拒否する)。

### 出力契約

- atomic node updateまたはimmutable package receiptと`graph_revision_after` (書込み時は新revision、`bind-github` の noop では`graph_revision_before`のまま)。

### 責務境界

- C02単一writer/lockのみで書き物理削除・partial commit・cross-feature edgeを禁止する。
- graph・content・receipt を Write/Edit や自作 script で直接書かない。

### 受入条件

- 通常writeはschema PASS、packageはP01..P13 exact 13・共通parent/package・DAG、失敗時applied_count=0になる。`bind-github` は `tracker_binding=github` へ切り替わり、本文のバイト列と `evaluation_status=pass` を保ち、既に同じ状態なら noop になる。

## Layer 3: インフラ層

- 使用資産: 通常 artifact の add/update と、確定済み issue/task の GitHub への切り替え (bind-github) は`build-graph-node.py`、exact-13 package は`register-package.py`、両者の書込み前検証は`validate-graph-schema.py`。bind-github も R2 preview の `graph_revision_before` を `expected_graph_revision` に渡す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-node/R3-write`

### 5.2 ゴール定義

- 目的: artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する
- 達成ゴール: atomic node updateまたはimmutable package receiptと`graph_revision_after` (`bind-github` の noop では`graph_revision_before`のまま) が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 通常writeはschema PASS、packageはP01..P13 exact 13・共通parent/package・DAG、失敗時applied_count=0になる。`bind-github` は `tracker_binding=github` へ切り替わり、本文のバイト列と `evaluation_status=pass` を保ち、既に同じ状態なら noop になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- receiptをC14/C27/呼出元へ返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

