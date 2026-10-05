# goal-verdict: dev-graph:run-dev-graph-system-spec (20261005T1500-p83m)

VERDICT: PASS

## 根拠

判定には次の 3 つを基準として使った。task.md の「検証」4 項目、SKILL.md の「Resume と lineage gate」節、prompts/R0-context.md の責務境界である。SKILL.md と R0-context.md は、lineage gate が exit 1/2 を返したときの振る舞いを次のように定めている。

- 取込元の付け替えや digest の書換えをせず、`violations[]` を提示して停止する。
- artifact_delivery は `artifact_created` に留める。
- semantic evaluator と Agent fork は起動しない。

被験 session の自己申告 (`out/status.json` の PASS) は判定に使っていない。以下の結果はすべて評価者が read-only のコマンドを自分で実行して確かめたもので、fixture の書換えも複製もしていない。以下では `eval-log/dev-graph/live-trial-fixtures/p83m-system-spec` を `<FIXTURE>` と略す。

### 1. lineage 断絶を検出し、診断付きで fail-closed したか → 確認済み

- **断絶が実在するか。** `python3 plugins/dev-graph/scripts/validate-source-lineage.py --repo-root <FIXTURE>` の結果は exit=1、`status=fail`、`checked=2` で、violation は 1 件だった。内容は `{"node":"spec-todo-backend","code":"lineage_source_missing","detail":"system-spec/backend.md が存在しない"}`。`--node-id spec-todo-backend` に絞ると exit=1、`--node-id arch-todo-infrastructure` に絞ると exit=0 (pass) になる。task.md が求める「参照先が解決できない lineage を含む状態」になっている。
- **断絶の作り方が SKILL.md の想定に合っているか。** SKILL.md は断絶の例として「取込元の削除・移動・編集」を挙げており、今回はそのうちの移動に当たる。`shasum -a 256 <FIXTURE>/archive/backend.md` は `501c1249…ee83` で、graph に入っている `spec-todo-backend` の `source_digest` と一致した。つまり、登録時には正しく解決していた取込元を、登録後に mv しただけである。transcript で順序も確かめた。
  - 01:38:43Z: C02 apply。直後の lineage gate は exit 0 (checked=2, pass)。
  - 01:38:51Z: `mv system-spec/backend.md archive/backend.md` を実行し、gate が exit 1 になった。
  - 01:38:56Z: 被験 skill を起動した。
- **被験 skill が何をしたか。**
  - 01:38:56Z: `Skill({skill:"dev-graph:run-dev-graph-system-spec", args:"--repo-root <FIXTURE>"})` が 1 回だけ起動された。
  - 01:38:58Z: `prompts/R0-context.md` を全文読んだ。
  - 01:39:04Z: R0 を実行した。中身は 2 つある。1 つは `resolve-repo-context.py --mode write` による C24 receipt の取得で、`match: True`、repository_id は `local:sha256:93b241c6…`、system_spec は repo 内だった。もう 1 つは `validate-source-lineage.py --repo-root <FIXTURE>` の実行で、上と同じ violations[] の JSON がそのまま出力され、`exit=1` だった。この JSON が診断に当たる。pane.txt では折りたたまれて表示されている。
  - pane.txt にはこの後、次の停止宣言が出ている。「R0 lineage gate が spec-todo-backend で lineage_source_missing により fail-closed (exit 1) となったため、規定どおり R1 以降・C02 取込・artifact 提示・evaluator/Agent fork を実行せず停止」「artifact_delivery は artifact_created のまま」。
- **停止後の動き。** 停止後に行ったのは 2 手だけである。graph schema の読取り確認と `git status --short` (01:39:10Z)、および `out/status.json` の Write (01:39:17Z)。R1-preflight、R2-delegate (system-spec-harness の Skill 呼出し)、R3-import (C02 呼出し)、Agent、AskUserQuestion はどれも 0 件だった。

### 2. 断絶を黙って無視したり、欠けた lineage を捏造したりしていないか → 確認済み

- `<FIXTURE>/system-spec/backend.md` は今も存在しない (`test -e` で backend-missing)。`archive/backend.md` も元に戻されていない。
- graph.json の `spec-todo-backend` の source_lineage は、`source_path=system-spec/backend.md`、`source_digest=501c1249…` のままで、C02 入力の `eval-log/node-add-spec-arch.json` と同じだった。付け替えも digest の書換えもない。
- skill 起動後の tool_use は、Bash 3 件と Write 1 件 (`out/status.json`) だけである。Edit、mv、rm、fixture へのリダイレクト書込み、C02 呼出しはどれも 0 件だった。transcript 全体の tool 使用は Bash 16、Write 4、Skill 3 である。

### 3. 部分的な成功を成功扱いしていないか → 確認済み

- import report は作られていない。goal-seek の記録 (`eval-log/run-dev-graph-system-spec-goal-spec.json`、`-progress.json`、`-intermediate.jsonl`) も作られていない。`<FIXTURE>/eval-log/` にあるのは、準備段階で作った C02 入力 `node-add-spec-arch.json` だけだった。
- 2 node はどちらも `confirmation_status=draft`、`evaluation_status=pending` のままで、confirmed には昇格していない。
- `out/status.json` は PASS だが、これは task.md の定義 (「skill が正しく fail-closed したなら status は PASS」) に沿ったシナリオ単位の値である。import が成功したとは主張していない。

### 4. graph が壊れた状態で残っていないか → 確認済み

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <FIXTURE>/.dev-graph/state/graph.json --repo-root <FIXTURE>` は exit=0 で、`valid=true`、`graph_validation.status=pass`、`violation_count=0` だった。2 node の readiness は incomplete だが、これは C02 が登録した時点から変わっていない。
- graph の canonical digest を `build-graph-node.py::_canonical_digest` と同じ方式で計算した (`ensure_ascii=False`、`sort_keys`、区切り `(",",":")`)。結果は `sha256:2d25ed49…3e1c` で、C02 receipt `node-r000001-add.json` の `graph_digest_after` と一致した。
- raw sha256 も比べた。被験 session が R0 で取った値 (01:39:04Z) も、評価時点の値も `eabaf1e6…2224` で、同じだった。graph.json の mtime は 10:38:46 JST で、skill 起動 (10:38:56 JST) より前である。
- C02 が書いた content も変わっていない。`specs/todo-backend.md` は `95d9aa2f…`、`architecture/todo-infrastructure.md` は `522b5f08…` で、どちらも receipt の `sha256_after` と一致した。
- そのほかの確認結果:
  - `git -C <FIXTURE> status --porcelain` は空で、HEAD は `c00572c` だった。このコミット (10:38:53 JST) は skill 起動より前に作られている。
  - `.dev-graph/cache` と `.dev-graph/locks` は空で、receipt は init と node-r000001-add の 2 件だけだった。
- `python3 plugins/dev-graph/scripts/resolve-repo-context.py --repo-root <FIXTURE> --mode read` は exit=0 だった。repository_id `local:sha256:93b241c6…c6b8` は `.dev-graph/config.json` の値と一致し、`content_roots.system_spec` は fixture の中にある。`<FIXTURE>/.git/dev-graph` は作られていない。

## 経路制約

- **被験 skill の起動。** `Skill(dev-graph:run-dev-graph-system-spec)` が 01:38:56Z に 1 回呼ばれ、host は "Launching skill" を返した。R0 はこの起動の後に実行されている。
- **task.md が要求する C02 単一 writer。** `Skill(dev-graph:run-dev-graph-node)` は 01:38:19Z に起動されている。手順は次のとおりで、C02 SKILL.md L118 の規定経路に沿っている。
  - 01:38:23Z: `run-dev-graph-node/prompts/R0〜R4.md` を全文読んだ。
  - 01:38:33Z: 入力 JSON を整形した。
  - `build-graph-node.py add --dry-run` で preview した (status=preview、graph_revision_before=0、write_count=0)。
  - 入力に `expected_graph_revision=0` を付けて `build-graph-node.py add` で apply した (status=applied、revision 0→1、applied_count=2)。
- **graph / config / content への直接書込み。** なかった。
  - Write は 4 件で、対象は `system-spec/backend.md` と `system-spec/infrastructure.md` (上流取込元の stand-in)、C02 入力 JSON、`out/status.json` である。
  - Bash による fixture への書込みは 4 件だった。`git init` と README の作成、C02 入力 JSON の `source_version` を 0.1.17 から 0.1.19 に直す sed、断絶を作るための `mkdir archive && mv`、git commit である。
  - `.dev-graph/` (config、graph、receipts、templates)、`specs/`、`architecture/` を書いたのは、init の `build-init-scaffold.py` と C02 の `build-graph-node.py` という plugin の正規実装だけだった。
- **責務の代行。** なかった。R0 の決定論 gate には、plugin の `validate-source-lineage.py` と `resolve-repo-context.py` を使っている。inline python は C24 receipt の realpath を比べて表示するだけの読取りで、自作 script や手書きの graph JSON はない。
- **責務 prompt を先に読んだか。** 読んでいる。被験 skill の R0 prompt は R0 実行の前に全文読んだ。R1〜R3 は実行していないので、読む必要はない。C02 の R0〜R4 prompt も入力を作る前に読んだ。
- **subagent。** 起動は 0 件で、これが正しい。SKILL.md は、この fail-closed が最小成果物より前の停止なので「semantic evaluator・Agent fork も起動しない」と定めており、起動すべき subagent はない。
- **blocker にしなかった観察事項。**
  1. 準備の init では `Skill(dev-graph:run-dev-graph-init)` を起動し、plugin 正規の `build-init-scaffold.py` に委譲している。再実行は noop だった。ただし init の `prompts/R1〜R5.md` は読んでいない。init は task.md が要求する skill ではなく fixture 準備にすぎず、被験 skill の挙動にも影響しないので、blocker にはしない。過去の trial (p83r) の判定とも揃えている。
  2. 上流の `system-spec/*.md` は system-spec-harness で作ったものではなく、Write で書いた stand-in である。`source_version=0.1.19` は `plugins/system-spec-harness/.claude-plugin/plugin.json` の実際の version と合っている。このシナリオは R0 の lineage gate による fail-closed だけを検証するので、判定には影響しない。
  3. C02 入力の `imported_at` は `2026-10-05T01:40:00Z` で、実際の登録時刻 (01:38:46Z) より後の値を手で書いている。fixture データの品質の問題で、被験 skill の挙動とは関係しない。
  4. 被験 session は準備中に、前回の fixture (`p83r-system-spec`) の入力 JSON と config を参考として読んでいる。過去の `goal-verdict.md` は読んでいない。
  5. 停止宣言は transcript の記録上は thinking block の中にあるが、pane.txt には表示されている。診断 JSON は gate の tool 出力としてそのまま出ている。最終応答は、task.md の指示どおり `DONE: PASS` の 1 行だけである。

## blocker

なし

gate_response_count: 0
