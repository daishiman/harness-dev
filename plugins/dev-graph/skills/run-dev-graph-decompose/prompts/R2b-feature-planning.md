# Prompt: R2b-feature-planning

> ready featureごとにsystem-dev-plannerを起動し、返却packageがP01..P13 exact 13 task/13-node DAG、共通parent_feature/feature_package_idを満たす場合だけC02へ渡す。手動/system-dev-planも同じ検査経路を通す

## Layer 1: 基本定義層

- `responsibility_id`: `R2b-feature-planning`
- `skill`: `run-dev-graph-decompose`
- 不変目的: ready featureごとにsystem-dev-plannerを起動し、返却packageがP01..P13 exact 13 task/13-node DAG、共通parent_feature/feature_package_idを満たす場合だけC02へ渡す。手動/system-dev-planも同じ検査経路を通す
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- ready feature contextと自動/手動system plan package。

### 出力契約

- source digest、P01..P13 exact set、13-node DAG、共通parent/packageを検証したcandidate。

### 責務境界

- invalid packageをC02へ渡さず経路別keyを作らずtaskを修復生成しない。

### 受入条件

- 13 node/phase exact-set、内部edgeのみ、parent/package一意になる。

## Layer 3: インフラ層

- 使用資産: Skill run-system-dev-planとpackage validator。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-decompose/R2b-feature-planning`

### 5.2 ゴール定義

- 目的: ready featureごとにsystem-dev-plannerを起動し、返却packageがP01..P13 exact 13 task/13-node DAG、共通parent_feature/feature_package_idを満たす場合だけC02へ渡す。手動/system-dev-planも同じ検査経路を通す
- 達成ゴール: source digest、P01..P13 exact set、13-node DAG、共通parent/packageを検証したcandidateが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 13 node/phase exact-set、内部edgeのみ、parent/package一意になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- PASSだけR3へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
