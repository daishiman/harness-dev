# Prompt: R2-plan

> 欠落時は6 content rootの既定値を組み立て、既存時は検証済みeffective configを保持し、routing/GitHub/worktree/hook policyと実行後readiness gateをdry-run receiptへ決定論的に出力する

## Layer 1: 基本定義層

- `responsibility_id`: `R2-plan`
- `skill`: `run-dev-graph-init`
- 不変目的: 欠落時は6 content rootの既定値を組み立て、既存時は検証済みeffective configを保持し、routing/GitHub/worktree/hook policyと実行後readiness gateをdry-run receiptへ決定論的に出力する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- R1 receipt、repo-config schema、6 content root要件、GitHub publication policy。

### 出力契約

- 正本`../scripts/build-dev-graph.py --dry-run`が返す、検証済みeffective config/digest、作成/保持対象、routing/GitHub/execution tracker/worktree/hook policy、apply後のreadiness gateを列挙したinit plan。未実行gateのPASSは予測しない。

### 責務境界

- 正本initializer以外でconfig/receipt/runnerを組み立てず、token/node IDを含めず、保存先をユーザーへ委ねない。

### 受入条件

- 既存configがあればそのcustom root/graphを保持し、なければ6 root既定値を使い、state/cache/locks/templates、GitHub/worktree/hook policyと実測予定gateが重複なくplanに現れる。

## Layer 3: インフラ層

- 使用資産: 正本`../scripts/build-dev-graph.py --dry-run`、repo-config schema、template contract。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-init/R2-plan`。frontmatterの`fork:inline`に従いmain contextで処理する。

### 5.2 ゴール定義

- 目的: 欠落時は6 content rootの既定値を組み立て、既存時は検証済みeffective configを保持し、routing/GitHub/worktree/hook policyと実行後readiness gateをdry-run receiptへ決定論的に出力する
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: effective config/digest、作成/保持対象、routing policy、GitHub/worktree/hook policy、apply後のreadiness gateを列挙したinit planが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] effective configのcustom root/graphまたは欠落時既定値、state/cache/locks、templates、GitHub/worktree/hook policy、apply後gateが重複なくplanに現れる

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- R3/R4/R5が同一plan digestを消費する。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
