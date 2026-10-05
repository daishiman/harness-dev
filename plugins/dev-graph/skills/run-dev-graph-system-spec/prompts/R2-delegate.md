# Prompt: R2-delegate

> run-system-spec-elicit→必要時run-system-spec-doc-fetch→run-system-spec-compile→assign-system-spec-completeness-evaluatorを引用実行する

## Layer 1: 基本定義層

- `responsibility_id`: `R2-delegate`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: run-system-spec-elicit→必要時run-system-spec-doc-fetch→run-system-spec-compile→assign-system-spec-completeness-evaluatorを引用実行する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- PASS preflight、spec state、user answers、doc-fetch必要性。

### 出力契約

- elicit/条件付きdoc-fetch/compile/evaluator receiptsとconfirmed artifacts。

### 責務境界

- 各ロジックを複製せずevaluatorを書換えずFAIL成果をimportしない。

### 受入条件

- 正規Skill呼出しだけでcoverage/source/evaluator gate全PASSになる。

## Layer 3: インフラ層

- 使用資産: 4 system-spec-harness Skills。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-system-spec/R2-delegate`

### 5.2 ゴール定義

- 目的: run-system-spec-elicit→必要時run-system-spec-doc-fetch→run-system-spec-compile→assign-system-spec-completeness-evaluatorを引用実行する
- 達成ゴール: elicit/条件付きdoc-fetch/compile/evaluator receiptsとconfirmed artifactsが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 正規Skill呼出しだけでcoverage/source/evaluator gate全PASSになる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- confirmed artifacts/evidenceをR3へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

