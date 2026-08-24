# Prompt: R3-import

> 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する

## Layer 1: 基本定義層

- `responsibility_id`: `R3-import`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- confirmed chapters、validator PASS済みdelegation receipt/progress、evaluator PASS、system-spec-harness version、章ごとのrepo-relative path/SHA。

### 出力契約

- 同じsystem-spec attestationに束縛されたdry-run/apply C02 receiptとlineage/confirmation/evidence付きimport report。

### 責務境界

- C02迂回で書かず内容をfeatureへ複製せず、PASS以外の委譲・stale digest・未確定章を登録しない。

### 受入条件

- qualified `dev-graph:run-dev-graph-node` Skillが正規 C02 writerでdry-run→applyし、同じattestation、staged C11 PASS、`status=active`、`confirmation_status=confirmed`、`evaluation_status=pass`、lineage全field/evidence/readiness欠落0をreceiptで示す。FAIL時はgraph digest不変・追加artifact 0件になる。

## Layer 3: インフラ層

- 使用資産: qualified `dev-graph:run-dev-graph-node` Skillとその正規 `register-package.py artifacts --system-spec-attestation` / `validate-graph-schema.py` 経路。caller側にwriterを複製しない。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- evaluatorがFAIL/INDETERMINATE、4呼出しの不足/順序違反、evidence/receipt/progress/source SHA不一致のどれか1つでも C02 を呼ばない。C02 dry-run/C11がFAILならapplyせず、apply中失敗は正規writerのrollbackでpartial 0とする。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-system-spec/R3-import`。この responsibility は main context で実行し、`Agent` fork は行わない。独立評価は R2 が呼び出す qualified `system-spec-harness:assign-system-spec-completeness-evaluator` Skill 内の責務とする。

### 5.2 ゴール定義

- 目的: 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: attested C02 dry-run/apply receiptとlineage/confirmation/evidence付きimport reportが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] 同じattestationでC02 dry-run/applyが実行され、staged C11 PASSと全nodeのactive/confirmed/pass/lineage/evidence/readiness欠落0がreceiptで確認できる
- [ ] 委譲/evaluator/attestation/C11のFAIL経路でgraph digestが不変、追加artifactが0件である

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- ids/lineage/readinessをC04へ渡す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
