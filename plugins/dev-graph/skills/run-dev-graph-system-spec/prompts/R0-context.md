# Prompt: R0-context

> C24で呼出しrepoのsystem_spec rootを解決し、symlink元や別repoのsystem-specを読まないcontainmentを検証する

## Layer 1: 基本定義層

- `responsibility_id`: `R0-context`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: C24で呼出しrepoのsystem_spec rootを解決し、symlink元や別repoのsystem-specを読まないcontainmentを検証する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- caller context、repo-local system-spec root、plugin source。

### 出力契約

- repository identity、content root、code authorityを分離したreceipt。
- resume 判定: lineage gate の `checked=0` は新規作成、`checked>=1` かつ exit 0 は取込済み node を保持した再開。

### 責務境界

- symlink元/別repo contentを読まずroot外/broken linkを許容しない。
- lineage gate が exit 1/2 のときは取込元の付け替えや digest の書換えで辻褄を合わせず、`violations[]` を提示して停止する (artifact_delivery は `artifact_created` に留まる)。

### 受入条件

- system_spec realpathがcaller repo内でrepository_id/common-dir一致になる。
- lineage gate が exit 0 で、resume か新規作成かが `checked` から一意に決まる。

## Layer 3: インフラ層

- 使用資産: resolve-repo-context、`../../scripts/validate-source-lineage.py --repo-root <DEV_GRAPH_ROOT> [--graph <path>] [--node-id <id> ...]` (skill root 起点。副作用なし、exit 0=pass / 1=violation / 2=usage・入力エラー)。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-system-spec/R0-context`

### 5.2 ゴール定義

- 目的: C24で呼出しrepoのsystem_spec rootを解決し、symlink元や別repoのsystem-specを読まないcontainmentを検証する
- 達成ゴール: repository identity、content root、code authorityを分離したreceiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] system_spec realpathがcaller repo内でrepository_id/common-dir一致になる
- [ ] `validate-source-lineage.py` が exit 0 で、`checked` に応じて新規作成か再開かを決めた

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- R1/R2/R3へreceiptを渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

