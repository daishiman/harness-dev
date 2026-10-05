# Prompt: R1-preflight

> system-spec-harness versionが>=0.1.0 <1.0.0でrequired 4 entry pointsを持つことを確認し、不一致/未導入ならfallbackせず診断付きfail-closedにする

## Layer 1: 基本定義層

- `responsibility_id`: `R1-preflight`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: system-spec-harness versionが>=0.1.0 <1.0.0でrequired 4 entry pointsを持つことを確認し、不一致/未導入ならfallbackせず診断付きfail-closedにする
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- system-spec-harness manifest、version、exports。

### 出力契約

- version rangeとrequired 4 entry pointのavailability receipt。

### 責務境界

- 不一致時fallback/複製へ進まず外部pluginを変更しない。

### 受入条件

- >=0.1.0 <1.0.0かつelicit/doc-fetch/compile/evaluator実在になる。

## Layer 3: インフラ層

- 使用資産: Readとmanifest検査。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-system-spec/R1-preflight`

### 5.2 ゴール定義

- 目的: system-spec-harness versionが>=0.1.0 <1.0.0でrequired 4 entry pointsを持つことを確認し、不一致/未導入ならfallbackせず診断付きfail-closedにする
- 達成ゴール: version rangeとrequired 4 entry pointのavailability receiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] >=0.1.0 <1.0.0かつelicit/doc-fetch/compile/evaluator実在になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- PASSだけR2へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

