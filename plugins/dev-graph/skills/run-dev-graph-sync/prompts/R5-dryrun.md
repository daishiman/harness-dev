# Prompt: R5-dryrun

> --dry-run時はIssue作成/更新/close、Project item-add/item-editを一切実行せず、project alias・field別の反映予定差分だけを提示する

## Layer 1: 基本定義層

- `responsibility_id`: `R5-dryrun`
- `skill`: `run-dev-graph-sync`
- 不変目的: --dry-run時はIssue作成/更新/close、Project item-add/item-editを一切実行せず、project alias・field別の反映予定差分だけを提示する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- 3-way plan、aliases、mutation candidates、dry-run flag。

### 出力契約

- Issue/item/field operationのalias別preview。

### 責務境界

- GitHub/Beads/local graph writeを呼ばずpreviewをapply receiptとしない。

### 受入条件

- planned operationが漏れなくmutation invocation count 0になる。

## Layer 3: インフラ層

- 使用資産: gh-bridge dry-run。反映予定差分は Issue/Projects field 計画の exports・imports・confirmations・conflicts (`unsupported-export` を含む) をそのまま提示する。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-sync/R5-dryrun`

### 5.2 ゴール定義

- 目的: --dry-run時はIssue作成/更新/close、Project item-add/item-editを一切実行せず、project alias・field別の反映予定差分だけを提示する
- 達成ゴール: Issue/item/field operationのalias別previewが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] planned operationが漏れなくmutation invocation count 0になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- 承認後だけapply入力へ変換する。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

