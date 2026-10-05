# Prompt: R2-plan

> 6 content root (issues/tasks/specs/architecture/features/docs)、frontmatter、routing policyに加え、GitHub enabled=false既定のissue repository/複数Project/field mapping/auto-add設定雛形を組み立てる。保存先やnode IDをユーザーへ求めない

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-init`
- 不変目的: 6 content root (issues/tasks/specs/architecture/features/docs)、frontmatter、routing policyに加え、GitHub enabled=false既定のissue repository/複数Project/field mapping/auto-add設定雛形を組み立てる。保存先やnode IDをユーザーへ求めない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- R1 receipt、repo-config schema、6 content root要件、GitHub publication policy。

### 出力契約

- 作成/保持対象、routing policy、`enabled:false`のIssue/複数Projects/field mapping/auto-add雛形を列挙したinit plan。

### 責務境界

- ファイルを作成せず、token/node IDを含めず、保存先をユーザーへ委ねない。

### 受入条件

- 6 root、state/cache/locks、templates、GitHub/worktree/hook policyが重複なくplanに現れる。

## Layer 3: インフラ層

- 使用資産: Read、repo-config schema、template contract。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-init/R2-plan`

### 5.2 ゴール定義

- 目的: 6 content root (issues/tasks/specs/architecture/features/docs)、frontmatter、routing policyに加え、GitHub enabled=false既定のissue repository/複数Project/field mapping/auto-add設定雛形を組み立てる。保存先やnode IDをユーザーへ求めない
- 達成ゴール: 作成/保持対象、routing policy、`enabled:false`のIssue/複数Projects/field mapping/auto-add雛形を列挙したinit planが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 6 root、state/cache/locks、templates、GitHub/worktree/hook policyが重複なくplanに現れる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R3/R4/R5が同一plan digestを消費する。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
