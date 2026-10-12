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
- elicit・doc-fetch・compile の各委譲の前に、cwd が `DEV_GRAPH_ROOT` と同じ dir か、`CLAUDE_PROJECT_DIR` が空でなければそれも同じ dir かを、1つの Bash の呼出しで確かめる (例: `DEV_GRAPH_ROOT='<開始時の receipt の repo_root>' && [ -n "$DEV_GRAPH_ROOT" ] && [ "$(pwd -P)" = "$(cd "$DEV_GRAPH_ROOT" && pwd -P)" ] && { [ -z "$CLAUDE_PROJECT_DIR" ] || [ "$(cd "$CLAUDE_PROJECT_DIR" && pwd -P)" = "$(cd "$DEV_GRAPH_ROOT" && pwd -P)" ]; }`)。doc-fetch と compile は相対の書き先 (`fetched-references.json`、`--out-dir` の既定の `system-spec`) を cwd から解決するので、cwd が違うと caller repo の外に書く。Bash の呼出しには `CLAUDE_PROJECT_DIR` が渡らないのが普通なので、未設定を不一致として扱わない (扱うと毎回止まる。値は下の項目のとおり、委譲先の呼出しの中で代入する)。exit 0 でなければ委譲せず、`cwd_not_repo_root` で FAIL として止める。
- elicit・doc-fetch・compile の手順にある Bash の呼出しでは、毎回その呼出しの先頭で `CLAUDE_PROJECT_DIR` に開始時の C24 receipt の `repo_root` の値を書いて export する (例: `export CLAUDE_PROJECT_DIR='<開始時の receipt の repo_root>' && python3 "<elicit の scripts>/apply-spec-transition.py" bootstrap --out "$CLAUDE_PROJECT_DIR/system-spec/spec-state.json"`)。elicit の SKILL.md は state の正本を `$CLAUDE_PROJECT_DIR/system-spec/spec-state.json` に置き、cwd に倒すのは slash command だけなので、代入しないと `--out` が `/system-spec/spec-state.json` になる。shell 変数は呼出しをまたいで残らないので、毎回書く (`pwd` や C24 の再実行から作らない)。

### 出力契約

- elicit/条件付きdoc-fetch/compile/evaluator receiptsとconfirmed artifacts。
- evaluator は `--spec-dir <repo 相対の system_spec root> --output <repo の中の eval-log/ 配下の report のパス>` で起動する。`--spec-dir` は C24 receipt の system_spec root (resolve 済みの絶対パス) を repo root からの相対パスに直した値にする。report を repo の外に置くと、C02 の `evidence_ref` (repo 相対のパス) で指せない。
- evaluator の Skill に渡す args は、cwd が `DEV_GRAPH_ROOT` と同じ dir かの確認と同じ1つの Bash の呼出しで、確認が exit 0 のときだけ出力して作る (例: `DEV_GRAPH_ROOT='<開始時の receipt の repo_root>' && [ -n "$DEV_GRAPH_ROOT" ] && [ "$(pwd -P)" = "$(cd "$DEV_GRAPH_ROOT" && pwd -P)" ] && printf -- '--spec-dir %s --output %s\n' "<repo 相対の system_spec root>" "eval-log/<report>.json"`)。その出力をそのまま args にして evaluator を起動し、確認と起動の間に cwd を変える呼出しを挟まない。args を手で書いて起動したり、起動の後に確認したりしない。出力が無いとき (確認が exit 0 でないとき) は evaluator を起動せず、`cwd_not_repo_root` で FAIL として止める。evaluator は相対の `--spec-dir` と `--output` を cwd から解決し、C02 は repo root から解決するので、cwd が違うと別の dir を評価した report を C02 が受け入れうる。`cd` で cwd を移して起動し直さず、R3 の「1回だけ回し直す」の対象にもしない。`DEV_GRAPH_ROOT` が空だと `cd ""` が cwd に留まって一致してしまうので、`-n` の確認を外さない。shell 変数は Bash の呼出しをまたいで残らないので、`DEV_GRAPH_ROOT` には毎回、開始時の C24 receipt の `repo_root` の値をそのまま書く (`pwd` や C24 の再実行から作らない)。
- evaluator の report の `spec_dir` は、repo root からの相対パス (例: `system-spec`) で、`--spec-dir` に渡した値と同じにする。`(read-only で評価)` のような説明の語やラベルを書き足さない。C02 は相対の `spec_dir` を repo root から解決し、取込元のディレクトリに解決しない report を `invalid_confirmation_evidence` で拒む。

### 責務境界

- 各ロジックを複製せずevaluatorを書換えずFAIL成果をimportしない。
- 委譲先の SKILL.md と、それが出力の前に読むよう指す責務 prompt は全文を読んでから、その委譲先の出力を作る。`head` や `sed` で一部の Layer だけを読んで済ませない。出力も書込みもしない gate だけの呼出し (`--resume` の検査など) は対象外とする。

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
- [ ] elicit・doc-fetch・compile の各委譲の前に、cwd が `DEV_GRAPH_ROOT` と同じ dir か (`CLAUDE_PROJECT_DIR` が空でなければそれも) を確かめている
- [ ] elicit・doc-fetch・compile の手順にある Bash の呼出しで、毎回 `CLAUDE_PROJECT_DIR` に開始時の receipt の `repo_root` を export している
- [ ] evaluator の args を、cwd の確認と同じ呼出しが exit 0 で出力した行から作り、その後に起動している (出力が無ければ起動せず `cwd_not_repo_root` で止めている)
- [ ] evaluator の report の `spec_dir` が、`--spec-dir` に渡したディレクトリ (取込元の章があるディレクトリ) に解決する
- [ ] 出力を作った委譲先ごとに、その SKILL.md と責務 prompt を全文読んでいる

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- confirmed artifacts/evidenceをR3へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

