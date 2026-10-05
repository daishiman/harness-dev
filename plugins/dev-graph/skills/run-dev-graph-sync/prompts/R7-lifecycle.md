# Prompt: R7-lifecycle

> C26でlinked PRのmerged/default-branch/closing-reference evidenceとC27 pending worktree eventをreconcileし、cleanなdefault branch worktreeだけでtask status/completion_evidence/execution_contextsをatomic更新する

## Layer 1: 基本定義層

- `responsibility_id`: `R7-lifecycle`
- `skill`: `run-dev-graph-sync`
- 不変目的: C26でlinked PRのmerged/default-branch/closing-reference evidenceとC27 pending worktree eventをreconcileし、cleanなdefault branch worktreeだけでtask status/completion_evidence/execution_contextsをatomic更新する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- PR merge/default-branch/closing evidence、C27 pending event、worktree cleanliness。

### 出力契約

- C26 reconciliation receiptとtask status/evidence/context収束結果。

### 責務境界

- closed-unmerged、feature/dirty worktree、policy不足をdoneにせず直接graphを書かない。

### 受入条件

- policy充足default mergeだけdone、feature eventはclean default適用までpendingに残る。

## Layer 3: インフラ層

- 使用資産: reconcile-github-lifecycleとmanage-worktree-lease。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-sync/R7-lifecycle`

### 5.2 ゴール定義

- 目的: C26でlinked PRのmerged/default-branch/closing-reference evidenceとC27 pending worktree eventをreconcileし、cleanなdefault branch worktreeだけでtask status/completion_evidence/execution_contextsをatomic更新する
- 達成ゴール: C26 reconciliation receiptとtask status/evidence/context収束結果が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] policy充足default mergeだけdone、feature eventはclean default適用までpendingに残る

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- receiptをsync ledgerへ合流する。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

