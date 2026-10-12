# Prompt: R3-status

> `extract-graph-status.py` (C24 の read と C11 の validate を中で通す) が返す rows から該当ノードを取り出し、status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)

## Layer 1: 基本定義層

- `responsibility_id`: `R3-status`
- `skill`: `run-dev-graph-status`
- 不変目的: `extract-graph-status.py` (C24 の read と C11 の validate を中で通す) が返す rows から該当ノードを取り出し、status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)
- inventory の summary (frontmatter の responsibilities と一致させる文): 「extract-graph-status.py の rows だけから該当ノードの status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)」。graph の読み取りと検索は `extract-graph-status.py` が行い、この責務はその rows だけを使う。
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- graph digest、query plan、検索前content/config digest。

### 出力契約

- node status/dependencies/linkage reportと検索後digest比較。

### 責務境界

- Write/Edit/external mutationを呼ばずroot外file_pathを表示しない。

### 受入条件

- reportが実状態一致、前後digest同一、external write 0になる。
- report の行は `extract-graph-status.py` の rows と一致し、`missing_required_keys` が0件である。

## Layer 3: インフラ層

- 使用資産: `extract-graph-status.py` (C24 の read と C11 の validate を中で通す)。行は script の `rows` だけを使い、graph を自分で読んで行を組み立てない。R2 の query plan を `--id/--kind/--project/--domain/--status/--feature/--tag/--tag-mode/--keyword` に写して起動し、exit 1 (`result: rejected`) なら行を出さず `validation.violations` と `missing_required_keys` を診断として返す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-status/R3-status`

### 5.2 ゴール定義

- 目的: `extract-graph-status.py` (C24 の read と C11 の validate を中で通す) が返す rows から該当ノードを取り出し、status/closed_at/依存関係を含む状態表示レポートを返す (書込みは行わない)
- 達成ゴール: node status/dependencies/linkage reportと検索後digest比較が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] reportが実状態一致、前後digest同一、external write 0になる
- [ ] report の行が `extract-graph-status.py` の rows そのもので、`read_only.changed` と `missing_required_keys` が0件である

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- read-only reportを返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

