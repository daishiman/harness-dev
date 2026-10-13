# Prompt: R3-import

> 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する

## Layer 1: 基本定義層

- `responsibility_id`: `R3-import`
- `skill`: `run-dev-graph-system-spec`
- 不変目的: 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- confirmed chapters、evaluator PASS、origin lineage、readiness。
- evaluator の report の `spec_dir` が、取込元の章があるディレクトリに解決すること。解決しないとき (C02 が `invalid_confirmation_evidence` で拒んだときを含む) は、report を手で書き換えず、R2 に戻して evaluator を正しい `--spec-dir` で1回だけ回し直す。それでも解決しなければ FAIL で止め、report の `spec_dir` と渡した `--spec-dir` を添えて、system-spec-harness の契約の課題として報告する。回し直しでも R2 の起動前の cwd の確認を通す。cwd が `DEV_GRAPH_ROOT` と違うこと (`cwd_not_repo_root`) は回し直しの対象にせず、evaluator を起動せずに FAIL で止める。

### 出力契約

- C02 receiptとlineage/confirmation/evidence付きimport report。

### 責務境界

- C02迂回で書かず内容をfeatureへ複製せず未確定章を登録しない。
- evaluator の report の `verdict` が `PASS` になるまで、取込の入力 (C02 に渡す payload のファイル) を書かず、C02 の Skill も起動しない。FAIL の report のまま取込の準備を進めない。
- C02 の `--dry-run` には、確定の add と同じ payload (`confirmation_evidence` を含む) を渡す。payload を変えた dry-run は、確定の取込の予行にならない。

### 受入条件

- 全node正規kind、lineage全field/evidence/readiness欠落0になる。
- import 後の lineage gate が exit 0 になる (exit 1/2 なら import report を完成扱いにせず診断を提示して停止する)。

## Layer 3: インフラ層

- 使用資産: Skill run-dev-graph-nodeとvalidate-graph-schema、`../../scripts/validate-source-lineage.py --repo-root <DEV_GRAPH_ROOT> --node-id <imported id> ...` (skill root 起点。exit 0=pass / 1=violation / 2=usage・入力エラー)。C02 の add も同じ検査で `source_lineage_unverified` を返す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-system-spec/R3-import`

### 5.2 ゴール定義

- 目的: 確定system-spec章をC02経由で登録しsource_lineage(origin_kind/plugin/path/version/digest/imported_at)、confirmation=confirmed、evaluator evidenceを保持する
- 達成ゴール: C02 receiptとlineage/confirmation/evidence付きimport reportが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] 全node正規kind、lineage全field/evidence/readiness欠落0になる
- [ ] import した node id を渡した `validate-source-lineage.py` が exit 0 になる
- [ ] C02 の dry-run と確定の add に、`confirmation_evidence` を含む同じ payload を渡している
- [ ] 取込の入力を書いたのも C02 の Skill を起動したのも、evaluator の PASS の report ができた後である

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- ids/lineage/readinessをC04へ渡す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。

