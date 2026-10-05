# Prompt: R2-plan

> Issueはid+updated_at、Projects custom fieldsはfield value updatedAtを競合hint、last-synced snapshotを削除/renameを含むcanonical baseとする3-way diffで同期計画を作る。Statusはlocal_to_project固定でremote変更を完了authorityにしない

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-sync`
- 不変目的: Issueはid+updated_at、Projects custom fieldsはfield value updatedAtを競合hint、last-synced snapshotを削除/renameを含むcanonical baseとする3-way diffで同期計画を作る。Statusはlocal_to_project固定でremote変更を完了authorityにしない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- local graph、remote snapshots、last-synced base、field value updatedAt。

### 出力契約

- local-only/remote-only/both/unchanged、manual conflict、retryを持つ3-way plan。

### 責務境界

- 書込まずremote Project Statusをcompletion authorityにせず削除/renameを落とさない。

### 受入条件

- 全差分が一分類を持ち双方変更write 0、片側変更の向きが明示される。

## Layer 3: インフラ層

- 使用資産: Readとgh-bridge dry-run。Issue は `diff-github-issues.py` (read-only) が updated_at の新しい側で exports/imports を、同時刻は書込み 0 の confirmations (手動確認フラグ) を返す。Projects field は `diff-github-project-fields.py` (read-only) が `field_snapshot` を base に exports/imports/conflicts/link_input を返し、`--issue-plan` (同じ graph_revision の Issue の計画) に行が残る node への import は `held` に回す。どちらも option/iteration に無い値は `unsupported-export`、reopen は conflict として write 0 の分類に残す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-sync/R2-plan`

### 5.2 ゴール定義

- 目的: Issueはid+updated_at、Projects custom fieldsはfield value updatedAtを競合hint、last-synced snapshotを削除/renameを含むcanonical baseとする3-way diffで同期計画を作る。Statusはlocal_to_project固定でremote変更を完了authorityにしない
- 達成ゴール: local-only/remote-only/both/unchanged、manual conflict、retryを持つ3-way planが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全差分が一分類を持ち双方変更write 0、片側変更の向きが明示される

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R3/R4/R5/R6が同じplan digestを消費する。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

