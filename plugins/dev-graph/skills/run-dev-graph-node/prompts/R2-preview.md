# Prompt: R2-preview

> 分類previewを提示し、閾値未達時だけ確認して正規pathを確定する

## Layer 1: 基本定義層

- `responsibility_id`: `R2-preview`
- `skill`: `run-dev-graph-node`
- 不変目的: 分類previewを提示し、閾値未達時だけ確認して正規pathを確定する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- R1候補、confidence/margin閾値、任意user decision。分類を伴わない `bind-github` は R1 候補を持たず、代わりに切り替え対象の確定済み issue/task の `bindings[]` (`graph_node_id` と任意の `publication_mode`) を受け取る。

### 出力契約

- 自動確定または明示確認済みkind/domain/project/path decision receipt。分類を伴わない `bind-github` は decision receipt を作らず、`graph_node_id` と preview の `graph_revision_before` だけを返す。

### 責務境界

- 閾値達成時は質問せず未達時だけAskUserQuestionを使い任意pathを要求しない。
- preview は `build-graph-node.py add|update|bind-github --dry-run` だけで作り、write 0 とする。`bind-github` は確定済みの既存 issue/task の binding を切り替えるだけなので kind/domain/project/path を分類せず、preview の `graph_revision_before` だけを R3 へ渡す。

### 受入条件

- decision sourceが`auto`/`user_confirmed`のどちらか (C14 が宣言した feature と、それが参照する architecture だけは`c14_macro_contract`。分類を伴わない `bind-github` は decision source を持たない) で、候補とpreviewの`graph_revision_before`がR3へ渡す`expected_graph_revision`と一致する。

## Layer 3: インフラ層

- 使用資産: AskUserQuestionとRead、`build-graph-node.py add|update|bind-github --dry-run` (preview)。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-node/R2-preview`

### 5.2 ゴール定義

- 目的: 分類previewを提示し、閾値未達時だけ確認して正規pathを確定する
- 達成ゴール: 自動確定または明示確認済みkind/domain/project/path decision receipt (`bind-github` では `graph_node_id` と `graph_revision_before`) が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] decision sourceが`auto`/`user_confirmed`のどちらか (C14 が宣言した feature と、それが参照する architecture だけは`c14_macro_contract`。分類を伴わない `bind-github` は decision source を持たない) で、候補とpreviewの`graph_revision_before`がR3へ渡す`expected_graph_revision`と一致する

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- decisionをR3/R4へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

