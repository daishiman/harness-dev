# Prompt: R3-render

> render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す

## Layer 1: 基本定義層

- `responsibility_id`: `R3-render`
- `skill`: `run-dev-graph-render`
- 不変目的: render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- input digest付きmodel、repo内output。

### 出力契約

- 単一自己完結HTMLとcounts/output digest receipt。

### 責務境界

- 外部runtime参照を生成せずgraph/contentを書かない。

### 受入条件

- external script/link 0、SVG/inline JSとfeature X/Y progressがbrowser live trialで表示され、receiptのnode/edge/progress countsとinput/output digestが実体に一致する。

## Layer 3: インフラ層

- 使用資産: render-graph-htmlとbrowser live trial。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-render/R3-render`

### 5.2 ゴール定義

- 目的: render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す
- 達成ゴール: 単一自己完結HTMLとcounts/output digest receiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] external script/link 0、SVG/inline JSとfeature X/Y progressがbrowser live trialで表示され、receiptのnode/edge/progress countsとinput/output digestが実体に一致する

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- HTML/receiptを呼出元へ返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
