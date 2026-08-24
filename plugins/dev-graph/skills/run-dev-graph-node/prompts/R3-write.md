# Prompt: R3-write

> artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する

## Layer 1: 基本定義層

- `responsibility_id`: `R3-write`
- `skill`: `run-dev-graph-node`
- 不変目的: artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- containment receipt、classification decision、artifact、C14 macro intentまたはfeature package、graph revision。

### 出力契約

- atomic node/macro update、immutable macro/package receiptと新graph revision、またはlegacy package receipt用versioned revalidation evidence。

### 責務境界

- 通常artifactはメンテナンス済み `register-package.py artifacts --repo-root ... --input ... --plan ... [--patches ...] [--initial-state ...]` をdry-run→applyで呼ぶ。C14 macroは同じintentを`preview-macro --dry-run`→`apply-macro --expected-candidate-digest ... --receipt ...`の順で渡し、featureの`architecture_refs`はtop-level architectureからC02に導出させる。`--initial-state` は新規local-only履歴artifactの明示closed importだけに限定する。一時writerの自作、直接graph/content書込み、preview candidateのcopy、物理削除、partial commit、cross-feature edgeを禁止する。

### 受入条件

- 通常writeは新規path占有とdurable pathのsymlinkをstaging前に拒否した上で `owner=C02/run-dev-graph-node` / `operation=write_artifacts` / `temporary_driver=false` / staged C11 PASS、macroはpreview/apply candidate digest一致・C11 PASS・immutable receipt、packageはP01..P13 exact 13・共通parent/package・DAGとなる。legacy receipt再検証は旧receipt/graphを変更せずcurrent C11/sourceを束縛したevidenceだけをatomic発行し、失敗時partial 0になる。

## Layer 3: インフラ層

- 使用資産: プラグイン内の `register-package.py artifacts/preview-macro/apply-macro/register`、`validate-graph-schema.py`。scratchpadにwriter scriptは作らない。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-node/R3-write`。`goal_seek.fork=inline` に従いmain contextで実行する。

### 5.2 ゴール定義

- 目的: artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: atomic node updateまたはimmutable package receiptと新graph revisionが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] 通常write/macroはC11 PASS、macroはpreview/apply digest一致、packageはP01..P13 exact 13・共通parent/package・DAG、失敗時partial 0になる

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- receiptをC14/C27/呼出元へ返す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
