# Prompt: R3-init

> resolved repo内へrepository_idを埋めたconfig/content/state/cache/locksを生成し、GitHub設定はowner/project number/field nameだけをrepo-local保存、token/node IDは保存しない

## Layer 1: 基本定義層

- `responsibility_id`: `R3-init`
- `skill`: `run-dev-graph-init`
- 不変目的: resolved repo内へrepository_idを埋めたconfig/content/state/cache/locksを生成し、GitHub設定はowner/project number/field nameだけをrepo-local保存、token/node IDは保存しない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- 検証済みcontext receipt、init plan、既存repo-local file digest。

### 出力契約

- repo-local config/graph/state/cache/locks/content rootsの作成・保持結果とimmutable init receipt。

### 責務境界

- resolved repo外、絶対path、secret、GitHub node IDを書かず既存fileを上書きしない。

### 受入条件

- `repository_id`を含む全必須資産が揃い、二回目planned changeが0、schema gateがexit0になる。

## Layer 3: インフラ層

- 使用資産: `../../scripts/build-init-scaffold.py --repo-root <path> [--config <path>] [--hook-source plugin|project-fallback] [--dry-run]` (skill root 起点)。scaffold を Write/Edit や heredoc で直接書かず、この script に委譲する。
- status と exit: `applied`/`noop`/`preview` は exit 0、`rejected` は exit 1 (何も作らない)、`error` は exit 2。二回目は `status=noop` (`planned_changes=0`・`write_count=0`) になる。
- script 内で repo-config schema と `validate-graph-schema.py` を書込み前に通し、create-only の init receipt (`.dev-graph/state/receipts/init-<UTC>.json`) を書く。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-init/R3-init`

### 5.2 ゴール定義

- 目的: resolved repo内へrepository_idを埋めたconfig/content/state/cache/locksを生成し、GitHub設定はowner/project number/field nameだけをrepo-local保存、token/node IDは保存しない
- 達成ゴール: repo-local config/graph/state/cache/locks/content rootsの作成・保持結果とimmutable init receiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] `repository_id`を含む全必須資産が揃い、二回目planned changeが0、schema gateがexit0になる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- init receipt は `build-init-scaffold.py` が create-only で書くので、R4/R5 の結果を後から合流しない。R4 は同じ script の結果から template の分を検証し、R5 は hook の適用 receipt を別に返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

