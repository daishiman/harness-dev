# Prompt: R4-template

> 共通/5kind/architecture 5 subtype/API/system phase/system task overlay/template contractを`.dev-graph/templates/`へ冪等scaffoldし、利用者編集済み版は上書きしない

## Layer 1: 基本定義層

- `responsibility_id`: `R4-template`
- `skill`: `run-dev-graph-init`
- 不変目的: 共通/5kind/architecture 5 subtype/API/system phase/system task overlay/template contractを`.dev-graph/templates/`へ冪等scaffoldし、利用者編集済み版は上書きしない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- plugin template contract、共通/5 kind/architecture subtype/API/system overlay、target templates root。

### 出力契約

- `build-init-scaffold.py` の結果のうち template の分。新規 copy (`created` のうち `.dev-graph/templates/` 配下)、同 digest の保持 (`preserved`)、利用者編集の検出 (`migration_preview` の plugin/local sha256) を分けて示す。R4 は自前の receipt を作らない。

### 責務境界

- 欠落資産だけ作成し利用者編集済みtemplateを上書きせずplugin側を変更しない。

### 受入条件

- contract列挙templateが欠落0、二回目copy 0、編集済み版hashが不変になる。

## Layer 3: インフラ層

- 使用資産: `../../scripts/build-init-scaffold.py` (skill root 起点。R3 と同じ 1 回の起動で template も欠落時だけコピーする) と、template contract の Read。template を Write/Edit や heredoc で直接書かない。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-init/R4-template`

### 5.2 ゴール定義

- 目的: 共通/5kind/architecture 5 subtype/API/system phase/system task overlay/template contractを`.dev-graph/templates/`へ冪等scaffoldし、利用者編集済み版は上書きしない
- 達成ゴール: `build-init-scaffold.py` の結果で template の新規 copy、同 digest の保持、利用者編集の検出が分かれて確認でき、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] contract列挙templateが欠落0、二回目copy 0、編集済み版hashが不変になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- script を別に起動せず、R3 が起動した `build-init-scaffold.py` の結果から template の分を検証する。init receipt は script が create-only で書くので、後から追記しない。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

