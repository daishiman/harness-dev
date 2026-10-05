# goal-verdict: dev-graph:run-dev-graph-node (20261005T1500-p83m)

VERDICT: PASS

## 根拠

以下で F = `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83m-node`、P = `/Users/dm/dev/dev/個人開発/harness/plugins/dev-graph/scripts`、S = 被験 session の scratchpad (`/private/tmp/claude-501/-Users-dm-dev-dev------harness/874b4056-8cf0-46ae-ab5b-9a1a9227dd85/scratchpad`) とする。fixture は書き換えていない。行ったのは read-only の操作と `--dry-run` だけ。`status.json` の自己申告は判定に使っていない。

### 準備: init と 5 kind の登録 (全 node が tracker_binding=none)
- `cat $F/.dev-graph/state/receipts/init-*.json` → `owner=C01/run-dev-graph-init`、`status=applied`、`hook_source=plugin`、`schema_result.valid=true`、violation 0。
- `python3 $P/resolve-repo-context.py --repo-root $F --mode read` → exit 0、`repository_id=local:sha256:043bfe68…`。この値は config.json と全 receipt の repository_id に一致する。
- `node-r000001-add.json` → `owner=C02/run-dev-graph-node`、`operation=add`、`applied_count=5`、`graph_revision 0→1`、`pre_write_validation.findings=0`。classification は 5 件とも `decision=auto`。confidence は 0.87〜0.92、margin は 0.79〜0.87 で、閾値 (0.80 / 0.15) を満たす。
- 最終 graph を python で読み、node を列挙した → issue / task / specification / architecture / document の 5 node。5 件とも `tracker_binding=none`。各本文の frontmatter (`graph_node_id`・`artifact_kind`・`file_path`・`tracker_binding`) も graph と一致する。architecture は `artifact_subtypes=["backend"]`。
- `shasum -a 256 $F/.dev-graph/cache/node-inputs/add-5kind.json` = `019ea5d7…`。receipt r1 の `input_sha256` と一致する。

### 本題 1: 冪等な連続更新
- **apply が実際に起きたこと**: `node-r000002-update.json` は `status=applied`、`operation=update`、`applied_count=1`、`graph_revision_before=1 → graph_revision_after=2`、`sections_appended=["調査メモ"]`、`sections_replaced=[]`、`unmanaged_body_preserved=true` を持つ。現行 `graph.json` の `graph_revision` は 2。canonical digest を `_canonical_digest` と同じ式で再計算すると `sha256:d2ca29e6…` になり、receipt r2 の `graph_digest_after` と一致する。入力 `update-issue-append.json` の sha256 `0062de6c…` も receipt r2 の `input_sha256` と一致する。被験 session の transcript では、writer は `--dry-run` なし (`build-graph-node.py update --repo-root $F --input …`) で呼ばれている。
- **更新前のスナップショットが本物であること**: S/graph-r1.json の canonical digest を計算すると `sha256:87c9bae0…` で、immutable receipt r1 の `graph_digest_after` と一致する。S/issue-before.md の sha256 `b4e2cdb8…` も、receipt r1 の issue `sha256_after` と receipt r2 の `sha256_before` の両方に一致する。どちらも改ざんのない r1 時点の実体と確認できた。
- **graph_node_id と file_path が不変であること**: graph-r1 と現行 graph を node ごとに比較した。issue-login-timeout は `file_path` が前後とも `issues/login-timeout.md` で、id 集合も一致する。差分のある field は `updated_at` と `implementation_readiness.checked_at` (時刻) だけだった。本文 frontmatter の `graph_node_id` と `file_path` も変わっていない。
- **全置換されず、追記 section だけが増えたこと**: `diff S/issue-before.md $F/issues/login-timeout.md` の差分は、frontmatter の時刻 2 行 (updated_at と implementation_readiness.checked_at) と、末尾の `## 調査メモ` + 本文 1 段落の追加だけだった。既存の見出しと本文はすべて残っている。現行 issue の sha256 `40cfa4b4…` は receipt r2 の `sha256_after` と一致する。
- **他 4 kind の node が無変更であること**: tasks/specs/architecture/docs の 4 本文の現 sha256 (`341f8b3a…`・`28562bf5…`・`af8a46f7…`・`58c9fae9…`) は、receipt r1 の `sha256_after` と完全に一致する。graph 上の 4 node も graph-r1 との差分 field が 0 件で、graph の top-level の差分は `graph_revision` 1→2 だけだった。

### 本題 2: feature を直接 add すると C14 で fail-closed すること
- 被験 session の transcript (tool call #28) で、writer が `--dry-run` なしで呼ばれていることを確認した (`build-graph-node.py add --repo-root $F --input .dev-graph/cache/node-inputs/add-feature-direct.json`)。入力は `artifact_kind: "feature"` で、`expected_graph_revision: 2` と通常の classification を持ち、macro を持たない。tool result にはエラー出力そのもの (`"status":"rejected"`、`"code":"feature_requires_c14_macro_contract"`、`"applied_count":0`、`"write_count":0`、`exit=1`) が残っている。直後の確認結果は、`features/` が 0 件、receipt が 3 件のまま、`cmp` で graph が unchanged、validate が exit 0。
- 自分でも同じ入力を `--dry-run` で writer に投入した (`python3 $P/build-graph-node.py add --repo-root $F --input .dev-graph/cache/node-inputs/add-feature-direct.json --dry-run`)。結果は exit 1、`code=feature_requires_c14_macro_contract`、`applied_count=0`、`write_count=0` で、同じ理由で拒否されることを確認した。投入前後で graph.json の sha256 は `9f66b3f3…` のまま変わらない。
- 拒否後の状態: `ls $F/features` は空。graph にも `artifact_kind=feature` の node や `features/` 配下の file_path は 0 件。receipts は `init-*`・`node-r000001-add`・`node-r000002-update` の 3 件だけで、r000003 は無い。graph_revision は 2 のまま。

### 本題 3: 最終確認
- `python3 $P/validate-graph-schema.py --graph $F/.dev-graph/state/graph.json --repo-root $F` → **exit 0**、`graph_validation.status=pass`、`violation_count=0`。(5 node が readiness `incomplete` と出るのは template の placeholder が残っているためで、schema 違反ではない。task は 1 section の追記だけを要求している。)

## 経路制約
- **Skill 起動**: transcript に `Skill({skill:"dev-graph:run-dev-graph-init", args:"--repo-root $F --hook-source plugin"})` と `Skill({skill:"dev-graph:run-dev-graph-node", args:"add --repo-root $F"})` の 2 回がある。どちらも "Launching skill" で読み込まれた。node の Skill 起動時に `--input` が無いのは、入力ファイルを起動後に作ったためである。その後の add・update・feature add は、同じ skill context の中で C02 writer (`build-graph-node.py`) を毎回呼んでいる。
- **責務 prompt の読込み**: init は `prompts/*.md` を全文 cat した後で、R1 resolver → R2 dry-run → R3/R4 apply の順に進めている。node は R0〜R4 の 5 本について、Layer 2〜7 と出力指示を入力 JSON の Write (#17) より前に読んでいる。ただし冒頭の Layer 1 (約 10 行) は表示範囲の外だった。中身は SKILL.md frontmatter の `responsibilities[].summary` と同じ文で、実質的な欠落は無いと判断した (所見に留め、blocker にはしない)。
- **代行の有無**: 自作の python は JSON の要約表示とスナップショットの比較にしか使っていない。分類・preview・書込み・検証はすべて plugin script (`resolve-repo-context.py`、`build-init-scaffold.py`、`build-graph-node.py` の add/update と `--dry-run`、`validate-graph-schema.py`) が担っている。skill の責務を代わりに実行した script は無い。
- **直接書込みの有無**: Write/Edit の対象は 4 つだけだった。入力 JSON 3 本 (`$F/.dev-graph/cache/node-inputs/` の add-5kind / update-issue-append / add-feature-direct。SKILL.md は writer の入力を repo 内に置くことを要求している) と、`out/status.json`。`sed -i` も更新入力 JSON に `expected_graph_revision` を足すのに使っただけである。graph.json・config.json・receipt・content 本文を Write/Edit/リダイレクトで直接書いた操作は無い。
- **Agent (subagent)**: 起動 0 回。SKILL.md (node と init の両方) は `artifact_delivery.pre_choice_forbidden` で、利用者が light/standard/detailed を選ぶ前の subagent を禁じている。Agent での fork は選択後の `semantic_evaluator_started` でだけ有効になる。task.md が人間への質問を禁じているので選択の局面は発生せず、未起動は契約どおりである。(所見: 選択肢の提示と accept-as-is の明示的な記録は transcript に残っていない。質問禁止の trial 制約の下では accept-as-is 相当として扱った。)
- **external mutation guard**: preview は出していない。Bash が guard で塞がれた記録も、hook の blocking error も無い。

## blocker
なし

gate_response_count: 0
