# goal-verdict: dev-graph:run-dev-graph-node (20261005T0940-p83r)

VERDICT: PASS

## 根拠

判定には被験 session の自己申告 (`out/status.json` = PASS、pane の `DONE: PASS`) を使っていない。以下はすべて、評価者が fixture の実物と plugin script を自分で叩いて確かめた結果である。

- fixture への操作は 3 種類だけで、複製もしていない。
  - 読み取り
  - `validate-graph-schema.py`
  - `resolve-repo-context.py --mode read`
  - `build-graph-node.py ... --dry-run`
- 被験 session が scratchpad に残した更新前 snapshot (`/private/tmp/claude-501/-Users-dm-dev-dev------harness/b38279e8-e268-4d7c-ab3b-d66c0b8f2510/scratchpad/snap1/`) は比較に使った。使う前に receipt の digest と照合し、本物の r1 状態であることを確かめている。
- `L<n>` は transcript.jsonl の 1 始まりの行番号、`#n` は tool_use の通し番号 (全 26 件) を指す。
- 評価に使った plugin ファイルは trial 開始 (09:38) 以降に変更されていない (mtime で確認)。対象は次のとおり。
  - `SKILL.md` (09:10)
  - `prompts/R0〜R4` (06:09〜08:16)
  - `build-graph-node.py` (09:09)
  - `validate-graph-schema.py` (06:21)
  - `prompt-common-layers.md` (06:09)

### 準備 (init と 5 kind の登録)

- `ls .dev-graph/state/receipts` の結果は次の 3 件だった。
  - `init-20261005T003946138073Z.json`
  - `node-r000001-add.json`
  - `node-r000002-update.json`
- `node-r000001-add.json` の中身は次のとおり。
  - owner=`C02/run-dev-graph-node`、status=applied、operation=add、applied_count=5
  - graph_revision 0→1
  - node_ids=[issue-login-timeout, task-login-timeout-guard, spec-auth-session, arch-auth-frontend, doc-auth-runbook]
  - classification は 5 件とも decision=auto。issue は confidence 0.92 / margin 0.87 で、他の 4 件もそれぞれ閾値を満たしている。
  - `input_sha256=bae4548a…` は `shasum -a 256 .dev-graph/cache/inputs/add-5kinds.json` と一致した。
- 現行の graph.json の nodes は issue / task / specification / architecture / document が 1 件ずつだった。`tracker_binding` は 5 件とも `none`。
- `resolve-repo-context.py --repo-root <fixture> --mode read` は exit 0 だった。repository_id `local:sha256:70843a47…` は、config.json と 2 つの node receipt の repository_id と一致した。

### 本題 1: 冪等な連続更新

- **apply が実際に起きた**
  - `node-r000002-update.json` は status=applied、operation=update、applied_count=1、graph_revision_before=1 / after=2、node_ids=[issue-login-timeout] だった。`pre_write_validation.findings=0`。
  - 現行 graph.json は `graph_revision=2` だった。その canonical digest を `build-graph-node.py` の `_canonical_digest` で評価者が計算すると `sha256:d50ca8ef…` になり、receipt の `graph_digest_after` と一致した。
  - receipt の `input_sha256=45432ddf…` は `update-issue-append.json` の sha256 と一致した。入力の中身は `expected_graph_revision: 1` と `append_sections: {"調査メモ": …}` だけである。
  - transcript #21 (L153) では、`--dry-run` (status=preview、write_count=0) の後に dry-run なしの apply (status=applied、write_count=3、exit 0) を実行している。staging の編集で止まらず、apply まで到達している。
- **graph_node_id と file_path が変わっていない**
  - snapshot の `graph.json` は canonical digest が r1 receipt の `graph_digest_after` (`4dbebb01…`) と一致したので、本物の r1 状態と判断した。
  - これと現行 graph を比べると、issue は前後とも `issue-login-timeout` / `issues/login-timeout.md` だった。
  - node で変わった field は `updated_at` と `implementation_readiness` (checked_at だけが変わった) の 2 つだけだった。
- **既存本文が全置換されず、追記した section だけが増えた**
  - snapshot の issue ファイルの sha256 は `97cca7a7…` で、r1 の `sha256_after` と r2 の `sha256_before` の両方と一致した。
  - `diff` の結果は次のとおり。
    - 本文の差分は、末尾に追加された `## 調査メモ` とその本文 1 段落だけだった。
    - frontmatter の差分は `updated_at` と `implementation_readiness.checked_at` の 2 行だけだった。
    - 更新前の本文 (frontmatter を除く) は、更新後の本文の先頭とバイト単位で一致した。
    - 見出しは 10 個から 11 個に増え、増えたのは `## 調査メモ` だけだった。
  - 現行ファイルの sha256 は r2 の `sha256_after` (`90697774…`) と一致した。receipt にも `unmanaged_body_preserved=true`、`sections_replaced=[]`、`sections_appended=["調査メモ"]` が記録されている。
- **他の 4 kind の node が無変更**
  - tasks / specs / architecture / docs の 4 ファイルは、現行の sha256 が r1 receipt の `sha256_after` と一致した。
  - graph 上の 4 node の object も、r1 snapshot と全 field で一致した (差分 field 0)。

### 本題 2: feature を直接 add すると C14 で fail-closed する

- **投入が拒否された**
  - transcript #24 (L172) で、被験 session は `--dry-run` を付けずに `build-graph-node.py add --repo-root <fixture> --input .dev-graph/cache/inputs/add-feature-direct.json` を実行している。
  - 入力は `expected_graph_revision: 2`、`artifact_kind: "feature"` で、classification は付いているが macro は無い。
  - 出力は次のとおりで、`apply exit=1` だった。

    ```
    {"applied_count":0,"code":"feature_requires_c14_macro_contract","error":"feature nodes are declared by the C14 macro contract (add with artifact_kind=feature and macro{...}); R1/R2 routing never yields them","findings":[],"status":"rejected","valid":false,"write_count":0}
    ```

  - 評価者が同じ入力 (sha256 `b030fa7a…`) を `--dry-run` で投入し直すと、同じ code・status=rejected・applied_count=0・write_count=0 と exit=1 が再現した。拒否を出しているのは `build-graph-node.py` の 525 行目の `WriterError("feature_requires_c14_macro_contract", …)` である。
- **拒否後も features/ が 0 件で、graph が壊れていない**
  - `ls -la features` は空だった。graph.json に artifact_kind=feature の node は 0 件、nodes は 5 件のままだった。
  - receipt は r000002 までで、拒否された投入の receipt は作られていない。
  - transcript #24 の記録では、拒否の前後で graph.json の生 sha256 は `f240df49…` のまま変わっていない。現行の生 sha256 も `f240df49…` で、canonical digest は r2 receipt と一致する。
  - 評価者の dry-run の前後で、fixture 全ファイル (.git を除く) の digest は変わらなかった (`70e4cada…` → `70e4cada…`)。

### 本題 3: 最終確認

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph .dev-graph/state/graph.json --repo-root <fixture>` の結果は次のとおりだった。
  - exit=0
  - `valid: true`、`graph_validation.status=pass`、`violation_count=0`、`violations=[]`

## 経路制約

- **Skill の起動**
  - #3 (L39) で `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root <fixture> --hook-source plugin"})` を、#10 (L80) で `Skill({skill:"dev-graph:run-dev-graph-node", …})` を実際に呼んでいる。
  - どちらも結果は `Launching skill: …` で、repo 側の SKILL 本文 (Base directory `plugins/dev-graph/skills/...`) が展開されている。
- **責務の代行**: なかった。
  - init の書込みは、init の実装本体である `build-init-scaffold.py` を通している。順序は dry-run (#7)、apply (#8、status=applied)、2 回目の noop で、その後に schema 検証 exit 0 (#9) を確認している。
  - node の add と update は、どちらも `build-graph-node.py` を通している。先に `--dry-run` の preview (#17 / #21 前半) を取り、そこで得た graph_revision_before (0 と 1) を `expected_graph_revision` に渡して apply している (#18 / #21 後半)。
  - session 内の inline python は、writer の出力 JSON の表示と、snapshot との比較 (読み取り) だけだった。
- **graph / config / content への直接書込み**: なかった。
  - Write tool の書込み先は 4 か所だけだった。
    - `.dev-graph/cache/inputs/add-5kinds.json` (#16)
    - `.dev-graph/cache/inputs/update-issue-append.json` (#20)
    - `.dev-graph/cache/inputs/add-feature-direct.json` (#23)
    - `out/status.json` (#26)
  - Edit tool は 0 回だった。
  - Bash による書込みは 2 種類だけだった。
    - writer の出力を `$TMPDIR` へリダイレクト
    - #19 の scratchpad への `cp` (fixture から見れば読み取り)
  - receipts/ の 2 件は writer の `receipt_path` と一致し、`input_sha256` も入力ファイルと一致する。被験者が receipt を手で書いた形跡は無い。
- **subagent (Agent tool)**: 0 回。
  - SKILL.md の `artifact_delivery.pre_choice_forbidden` は、利用者の選択前に subagent を使うことを禁じている。Agent による fork は、light / standard / detailed を選んだ後の goal-seek (`semantic_evaluator_started`) でだけ求められる。
  - この trial は人間に聞かずに最後まで進む条件なので、accept-as-is の経路になる。したがって Agent を起動していないことは SKILL の要求どおりである。init も同じ契約で、SKILL.md 158 行目が「accept-as-isではSubAgent/loopとも0回」と定めている。
- **責務 prompt の事前読込**
  - init の R1〜R5 は、#5 (L50) で `cat` により全文を読んでいる。init の出力 (#7 / #8) より前である。
  - node の R0〜R4 は、#11 (L90) と #12 (L94) の 2 回の `sed` で読んでいる。最初の入力 JSON の Write (#16) より前である。
    - 2 つの範囲の和集合を評価者が再現すると、読まれなかった行は各ファイルの Layer 4 本文の 1 行 (`- 共通の内容は ../../references/prompt-common-layers.md … の「Layer 4」に従う。`) と前後の空行だけだった。
    - Layer 1・2・3・5・6・7 と出力指示は、すべて読まれている。
    - 読まれなかったこの 1 行は責務に固有の指示ではない。init の prompt (#5) で同じ文面を既に読んでいる。
- **external mutation guard**: preview を発行していない。`build-external-*`・`gh`・`bd` の呼び出しも 0 件で、pending guard context による Bash の遮断も起きていない (attachment と pane で確認)。
- **out/ への書込み**: `status.json` の 1 ファイルだけだった (評価者が `ls` で確認)。
- **人間への問い合わせ**: AskUserQuestion は 0 回だった。最初の指示 (L1 付近の task.md の読込指示) の後に、人間からの入力は無い。transcript の user 行は、tool_result と、Skill 本文の展開 (isMeta) だけである。

### 判定に影響しない観察

1. `references/prompt-common-layers.md` (prompt の Layer 4〜7 の共通部分の正本) は、init でも node でも開かれていない。task.md が読むことを求めているのは `prompts/R*.md` で、その本体は上のとおり読まれている。共通層の規範の中身は、どれも行動上守られている。
   - fail-closed で部分成功を PASS にしない
   - secret を埋め込まない
   - revision/digest による stale の拒否 (`expected_graph_revision` の CAS)
   - 不要な AskUserQuestion をしない
2. node skill について、accept-as-is を選んだことを明示した発言は無い (init では L75 付近の発言「準備用途のため accept-as-is で handoff」で明示している)。
3. 準備で登録した 5 node は、readiness が `incomplete` のままである (`readiness_fill` は返されたが、埋めていない)。ただし見出しは template どおりにすべて揃っており、schema 検証は pass している。task.md の検証項目にも含まれていない。

## blocker

なし

gate_response_count: 0
