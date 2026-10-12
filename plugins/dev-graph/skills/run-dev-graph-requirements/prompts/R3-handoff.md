# Prompt: R3-handoff

> C11のreadiness検証とsystem-dev-planner所有のsystem-plan検証 (validate-system-plan.py) の完了時だけ要件定義書をcapability-build/task-graph buildへhandoffする。不足時はmissing_sectionsを返して停止し、実装コードは生成しない

## Layer 1: 基本定義層

- `responsibility_id`: `R3-handoff`
- `skill`: `run-dev-graph-requirements`
- 不変目的: C11のreadiness検証とsystem-dev-planner所有のsystem-plan検証 (validate-system-plan.py) の完了時だけ要件定義書をcapability-build/task-graph buildへhandoffする。不足時はmissing_sectionsを返して停止し、実装コードは生成しない
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- PASS receipt、trace plan、validated system plan、requirements candidate。
- `validate-readiness-binding.py` の binding report と、handoff 対象 node と binding の `graph.digest` (`--expect-graph-digest`) を渡した `guard-requirements-handoff.py` の guard report。

### 出力契約

- atomic requirements document、capability-build handoff ref、snapshot digest。
- guard が exit 1 のときは handoff 0件と、guard report の `missing_sections` (closure 全件) と `blocked[].remediation` (owner・upstream・owners・referenced_by)。
- guard が exit 2 (`status: snapshot_mismatch`) のときは handoff 0件と、guard report の `graph.digest`・`graph.expected_digest`・`graph.graph_revision`。
- guard が report の無い exit 2 (usage・C24・IO の例外。stdout は空で、stderr に理由が出る) のときは handoff 0件と、止まった理由としての stderr の例外の内容。

### 責務境界

- 未達時handoff/code 0、外部validator結果を書換えない。

### 受入条件

- 全requirement/source/package refを持ちdigest一致、self-generated code 0になる。
- handoff する node は guard report の `handoff` と同じ集合で、snapshot digest は binding report の `graph.digest` と同じである。
- binding report の `graph.digest` と guard report の `graph.digest` が一致する (guard の `graph.digest_match: true`)。2つの script が同じ graph の snapshot を見たことを、この一致で確かめる。

## Layer 3: インフラ層

- 使用資産: `guard-requirements-handoff.py --repo-root <root> --node <id> [--node <id>]... --expect-graph-digest <binding の graph.digest>`、WriteとSkill capability-buildへのhandoff。
- Write と Skill は、`validate-readiness-binding.py` と `guard-requirements-handoff.py` がともに exit 0 (guard の `handoff_count` が scope 全件) で、binding の `graph.digest` と guard の `graph.digest` が一致するときだけ使う。guard が exit 1 (`status: withheld`) なら何も書かず、`missing_sections` と `remediation` をそのまま返して止まる。guard が exit 2 (`status: snapshot_mismatch`。binding の後に graph が変わった) なら何も書かず、binding からやり直す。report の無い exit 2 (usage・C24・IO の例外) も何も書かず、stderr の例外の内容を止まった理由として返して止まる。closure の一部だけを handoff しない。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-requirements/R3-handoff`

### 5.2 ゴール定義

- 目的: C11のreadiness検証とsystem-dev-planner所有のsystem-plan検証 (validate-system-plan.py) の完了時だけ要件定義書をcapability-build/task-graph buildへhandoffする。不足時はmissing_sectionsを返して停止し、実装コードは生成しない
- 達成ゴール: atomic requirements document、capability-build handoff ref、snapshot digestが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全requirement/source/package refを持ちdigest一致、self-generated code 0になる
- [ ] guard が exit 1 のとき、handoff と Write が0件で、guard report の `missing_sections` と `remediation` を全件返している
- [ ] handoff したとき、binding report の `graph.digest` と guard report の `graph.digest` が一致し、記録した snapshot digest もその値である

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- task-graph consumerへ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

