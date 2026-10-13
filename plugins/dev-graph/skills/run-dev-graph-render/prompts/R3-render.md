# Prompt: R3-render

> render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す

## Layer 1: 基本定義層

- `responsibility_id`: `R3-render`
- `skill`: `run-dev-graph-render`
- 不変目的: render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す
- 成功条件は Layer 2 の受入条件と Layer 5 の二値 checklist の同時充足とする。

## Layer 2: ドメイン層

### 入力契約

- input digest付きmodel、repo内output、任意でfeatureごとのC02 registration receipt。

### 出力契約

- 単一自己完結HTMLとcounts/output digest receipt。registration receiptを渡したときは`receipt_checks`も返す。
- receiptと合わないときはHTMLを出さず、stderrのJSON (`receipt_mismatches[]`) を理由として返す。

### 責務境界

- 外部runtime参照を生成せずgraph/contentを書かない。
- receiptとの不一致を、receiptを外して描き直すことで回避しない。

### 受入条件

- external script/link 0、SVG/inline JSとfeature X/Y progressがbrowser live trialで表示され、receiptのnode/edge/progress countsとinput/output digestが実体に一致する。
- registration receiptを渡したfeatureは、Y (子task数) が`expected_count`と、子taskの集合が`node_ids`と、子taskの`source_lineage.source_digest`がreceiptの`source_digest`と一致する。X (doneの子task数) は`applied_count`と照合しない。

## Layer 3: インフラ層

- 使用資産: render-graph-htmlとbrowser live trial。
- feature の registration receipt があれば --receipt で渡す。不一致の exit 1 のときは成果物を出さずに止め、理由を返す。`--receipt PATH` は feature ごとに繰り返して渡せる。exit 1 の stderr は `{"ok": false, "error": "receipt_mismatch", "receipt_mismatches": [...]}` で、各要素の `feature`/`problems`/`missing_ids`/`extra_ids`/`expected_count`/`actual_count`/`digest_mismatch_ids` がどの feature の何が合わないかを示す。
- path は caller repository context または skill-relative reference から解決し、環境固有の絶対 path を成果物へ保存しない。

## Layer 4: 共通ポリシー層

- 共通の内容は `../../references/prompt-common-layers.md` (skill root 起点) の「Layer 4」に従う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

- 共通の内容 (5.1 の fork 方針、5.2 の背景、5.3 の共通項目、5.4 実行方式) は `../../references/prompt-common-layers.md` の「Layer 5」に従う。5.3 は共通項目と下の項目がすべて YES のときに到達とする。

### 5.1 担当 agent

- `run-dev-graph-render/R3-render`

### 5.2 ゴール定義

- 目的: render-graph-html.py で静的HTML/CSS + SVG + インラインJSを生成しコミットまたはCI生成可能な成果物を返す
- 達成ゴール: 単一自己完結HTMLとcounts/output digest receiptが生成され、受入条件を満たした状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

- [ ] external script/link 0、SVG/inline JSとfeature X/Y progressがbrowser live trialで表示され、receiptのnode/edge/progress countsとinput/output digestが実体に一致する
- [ ] registration receiptを渡したときは`receipt_checks[].problems`がすべて空である。不一致のexit 1ではHTMLを出していない

## Layer 6: オーケストレーション層

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 6」に従う。
- HTML/receiptを呼出元へ返す。
- `--receipt` の不一致で exit 1 のときは、成果物を出さずに止め、stderr の `receipt_mismatches` を理由として呼出元へ返す。

## Layer 7: UserInput

- 共通の内容は `../../references/prompt-common-layers.md` の「Layer 7」に従う。

## 出力指示

Layer 2 の入力・出力・責務境界・受入条件を正本としてこの単一責務だけを実行し、思考過程を出力せず、artifact/receipt、検証結果、未達 blocker だけを返す。
