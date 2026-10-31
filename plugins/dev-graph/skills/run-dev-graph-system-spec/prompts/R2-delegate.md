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
- 開始時の C24 receipt を JSON ファイルとして保存し、`repo_root` と `content_roots.repository` の realpath の一致を確認して固定する。委譲先の読込・fork による cwd の変更を、新しい caller root の根拠にしない。
- 取込元のstate・出典・章を生成する elicit・doc-fetch・compile の本処理Bashは、毎回先頭で `export CLAUDE_PROJECT_DIR='<開始時の receipt の repo_root>' && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && ...` とし、固定 root への移動・照合が exit 0 の場合だけ実処理へ進む。doc-fetch・compile の相対出力もこれで caller repo 内に置く。移動・照合に失敗したら `cwd_not_repo_root` で停止する。root の値は開始時 receipt から取り、`pwd` や別 cwd での C24 再探索から作らない。shell 変数は呼出しをまたいで残らないため毎回 export する。

- 独立検証用の既存pytestや、canonical moduleを直接呼ぶunit検証は本処理の代替ではない。callerのstate/章/出典をread-onlyにし、書込みを事前に許可された絶対パスのscratch配下だけへ隔離した場合は、そのtest fixture固有のcwdを使える。scratch成果をC05の評価対象・C02の取込元・本処理の実行証拠に流用しない。隔離と非変更を確認できなければ実行しない。本処理を自作driver・compilerへ置換することは禁止する。

### 出力契約

- elicit/条件付きdoc-fetch/compile/evaluator receiptsとconfirmed artifacts。
- evaluator の直前に `python3 -B "<skill root>/scripts/prepare-evaluation.py" --context-receipt "<開始時の C24 receipt の絶対パス>" --output eval-log/system-spec-completeness-report.json` を実行する。helper は receipt の write mode・repo/worktree/common-dir identity・content root を現在の C24 と照合し、repo 外の spec と、`eval-log/` 外・symlink 経由の report を拒否する。検査は読取専用で、exit 0 のときだけ args を含む JSON を返す。
- evaluator の Skill に渡す args は helper 出力の `skill_args` をそのまま使う。`--spec-dir` と `--output` は検証済み絶対パスなので、起動先の cwd が変わっても別の資料へ解決されない。helper が失敗したら `evaluation_context_invalid` で停止し、手書き args・receipt の書換え・cwd からの root 付替えで回避しない。再評価時も同じ開始時 receipt に対して helper を通す。
- evaluator の report の `spec_dir` は `--spec-dir` の絶対パスをそのまま格納し、ラベルや説明を混ぜない。C02 はこの絶対パスと取込元の実ディレクトリを照合できる。`evidence_ref` は helper 出力の repo 相対パス、source lineage も repo 相対にする。評価用の絶対パスは当該実走のローカル証跡に限り、別 repo や別 worktree に移して再利用しない。

### 責務境界

- 各ロジックを複製せずevaluatorを書換えずFAIL成果をimportしない。
- 委譲先の SKILL.md と、それが出力の前に読むよう指す責務 prompt は全文を読んでから、その委譲先の出力を作る。`head` や `sed` で一部の Layer だけを読んで済ませない。出力も書込みもしない gate だけの呼出し (`--resume` の検査など) は対象外とする。

### 受入条件

- 正規Skill呼出しだけでcoverage/source/evaluator gate全PASSになる。

## Layer 3: インフラ層

- 使用資産: 4 system-spec-harness Skills。
- source lineage と node の path は caller repository context からの相対パス。evaluator の起動 args と report の `spec_dir` は、上の境界検証済み絶対パスを当該実走のローカル証跡として保持する。

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
- [ ] 取込元を生成する本処理のBashごとに固定rootへの移動・照合をし、独立testの書込みは検証済みscratchだけである
- [ ] elicit・doc-fetch・compile の手順にある Bash の呼出しで、毎回 `CLAUDE_PROJECT_DIR` に開始時の receipt の `repo_root` を export している
- [ ] evaluator の args は helper の成功出力の `skill_args` で、失敗時には起動していない
- [ ] evaluator の report の `spec_dir` が、`--spec-dir` に渡したディレクトリ (取込元の章があるディレクトリ) に解決する
- [ ] 出力を作った委譲先ごとに、その SKILL.md と責務 prompt を全文読んでいる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- confirmed artifacts/evidenceをR3へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

