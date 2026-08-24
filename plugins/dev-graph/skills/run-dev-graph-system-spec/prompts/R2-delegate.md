# Prompt: R2-delegate

> run-system-spec-elicit→run-system-spec-doc-fetch(no-op可)→run-system-spec-compile→assign-system-spec-completeness-evaluatorを必ず順番どおり引用実行する

## Layer 1: 基本定義層

- `responsibility_id`: `R2-delegate`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: run-system-spec-elicit→run-system-spec-doc-fetch(no-op可)→run-system-spec-compile→assign-system-spec-completeness-evaluatorを必ず順番どおり引用実行する
- 上記の「必要時」は doc-fetch の取得・更新効果が必要時という意味であり、qualified entrypoint の呼出し自体を条件付きにしない。既存参照が有効なら呼び出した Skill が `no-op` を返す。
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- PASS preflight、spec state、user answers、delegation receipt。

### 出力契約

- elicit/doc-fetch/compile/evaluator の順序付き invocation receipt と confirmed artifacts。

### 責務境界

- 各ロジックを複製せずevaluatorを書換えずFAIL成果をimportしない。

### 受入条件

- 4つの qualified Skill を順番どおり実呼出しし、各戻りの repo-relative evidence と SHA-256 が delegation validator で PASS になる。既存 fetched-references が有効でも doc-fetch を呼び、正規 Skill の no-op/refresh 判断を得る。

## Layer 3: インフラ層

- 使用資産: 4 system-spec-harness Skills。
- 使用する qualified entrypoint は `system-spec-harness:run-system-spec-elicit` → `system-spec-harness:run-system-spec-doc-fetch` → `system-spec-harness:run-system-spec-compile` → `system-spec-harness:assign-system-spec-completeness-evaluator` の4つで固定する。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 入力契約、authority、containment、schema のいずれかが未達なら fail-closed とし、部分成功を PASS にしない。
- secret と認証情報を prompt 出力、graph、receipt に埋め込まない。
- 同一入力と同一 revision/digest では同じ decision と output shape を返す。
- future invocation を receipt へ先書きしない。各 Skill の戻りを得た直後だけ `invocations[]` に追記し、`validate-system-spec-delegation.py` exit 0 前に progress を4/4またはPASSにしない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent

- `run-dev-graph-system-spec/R2-delegate`。この responsibility は main context で実行し、`Agent` fork は行わない。独立評価は R2 が呼び出す qualified `system-spec-harness:assign-system-spec-completeness-evaluator` Skill 内の責務とする。

### 5.2 ゴール定義

- 目的: run-system-spec-elicit→run-system-spec-doc-fetch(no-op可)→run-system-spec-compile→assign-system-spec-completeness-evaluatorを必ず順番どおり引用実行する
- 背景: この責務を隣接 responsibility から分離し、入力・出力・authority を一意にする。
- 達成ゴール: elicit/doc-fetch/compile/evaluator の4実呼出し receipt と confirmed artifacts が生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 宣言した入力が全て検証済みである
- [ ] 出力が宣言した shape と authority を満たす
- [ ] 責務境界に反する read/write/delegation が0件である
- [ ] 4 qualified Skill の順序・evidence digest・progress 4/4 が delegation validator で一致する

### 5.4 実行方式

- 固定手順を持たない。未達 checklist を評価し、操作を都度立案・実行・検証する。各周回末に `original_goal`、`delta_from_original`、`merged_directive_for_next`、`drift_signal` を追記し、最大5周で未達なら上位 skill へ fail-closed で返す。

## Layer 6: オーケストレーション層

- confirmed artifacts/evidenceをR3へ渡す。
- 前段 receipt/digest と後段 input digest を一致させ、stale handoff を拒否する。

## Layer 7: UserInput

- 不足情報が実行結果を変える場合だけ `AskUserQuestion` を使う。repo policy で決まる値、保存先、secret、node ID は質問しない。
- ユーザー提示は日本語、schema key/CLI parameter は原語を保つ。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
