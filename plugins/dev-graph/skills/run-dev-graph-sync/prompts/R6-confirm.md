# Prompt: R6-confirm

> id+updated_at 同時競合で立てた手動確認フラグを次回同期の入力として読み取り、利用者の確認結果を反映した上で当該ノードのフラグを解消する

## Layer 1: 基本定義層

- `responsibility_id`: `R6-confirm`
- `skill`: `run-dev-graph-sync`
- 不変目的: id+updated_at 同時競合で立てた手動確認フラグを次回同期の入力として読み取り、利用者の確認結果を反映した上で当該ノードのフラグを解消する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- manual flag、競合双方値/updated_at、ユーザーdecision。

### 出力契約

- 採用値、decision evidence、解消flagを持つrequest。

### 責務境界

- 判断を推測せずGitHub表示値を無断でdurable local値にしない。

### 受入条件

- decisionがsnapshotに束縛されC02適用後の次回同期でflagが消える。

## Layer 3: インフラ層

- 使用資産: AskUserQuestionとSkill run-dev-graph-node。手動確認フラグは `diff-github-issues.py` の confirmations 行で、その decision は行の local/remote/local_updated_at/remote_updated_at を写して `--decisions` に渡す。Projects field の decision は conflict 行の base/local/remote を写して `diff-github-project-fields.py --decisions` に渡す。どちらも値が変わった decision は stale として使わない。`unsupported-export` は field の option/iteration に無い値なので、local を採っても書けない。`cause` が no-base/both-changed/decided-* なら remote を採る decision を、local-only/local-authority なら Project field に option/iteration を足すか local を戻す手順を提示する。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-sync/R6-confirm`

### 5.2 ゴール定義

- 目的: id+updated_at 同時競合で立てた手動確認フラグを次回同期の入力として読み取り、利用者の確認結果を反映した上で当該ノードのフラグを解消する
- 達成ゴール: 採用値、decision evidence、解消flagを持つrequestが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] decisionがsnapshotに束縛されC02適用後の次回同期でflagが消える

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- receiptをcanonical base更新へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

