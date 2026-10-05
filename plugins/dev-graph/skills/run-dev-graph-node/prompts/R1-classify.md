# Prompt: R1-classify

> 成果物内容からartifact_kind/domain/project_id候補、confidence、reason、候補pathを推定する。保存先を質問しない

## Layer 1: 基本定義層

- `responsibility_id`: `R1-classify`
- `skill`: `run-dev-graph-node`
- 不変目的: 成果物内容からartifact_kind/domain/project_id候補、confidence、reason、候補pathを推定する。保存先を質問しない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- artifact本文、kind/domain/project hint、routing policy、template contract。

### 出力契約

- kind/domain/project/path/confidence/reasonと第二候補を持つclassification preview。

### 責務境界

- 保存先を質問せず書込まずfeatureはC14 macro contract時だけ候補化する。

### 受入条件

- 通常5 artifactが正規rootに写像されconfidence/top-two marginが再現可能になる。

## Layer 3: インフラ層

- 使用資産: Readとrouting policy。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-node/R1-classify`

### 5.2 ゴール定義

- 目的: 成果物内容からartifact_kind/domain/project_id候補、confidence、reason、候補pathを推定する。保存先を質問しない
- 達成ゴール: kind/domain/project/path/confidence/reasonと第二候補を持つclassification previewが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 通常5 artifactが正規rootに写像されconfidence/top-two marginが再現可能になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R2へ候補集合と根拠を渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

