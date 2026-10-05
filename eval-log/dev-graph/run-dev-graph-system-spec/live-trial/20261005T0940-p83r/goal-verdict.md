# goal-verdict: dev-graph:run-dev-graph-system-spec (20261005T0940-p83r)

VERDICT: PASS

## 根拠

判定の基準は、task.md の「検証」4 項目と、SKILL.md の「Resume と lineage gate」節と、R0-context.md の責務境界である。SKILL.md と R0-context.md は、lineage gate が exit 1/2 を返したら次のように振る舞うことを求めている。取込元の付け替えも digest の書換えもせず、`violations[]` を提示して停止する。artifact_delivery は `artifact_created` に留め、semantic evaluator と Agent fork は起動しない。被験 session の自己申告 (`out/status.json` の PASS) は判定に使っていない。以下に挙げる結果は、すべて評価者が自分で read-only のコマンドを実行して確かめたものである。fixture は書き換えておらず、複製もしていない。以下では `<FIXTURE>` を `eval-log/dev-graph/live-trial-fixtures/p83r-system-spec` の略として使う。

### 1. lineage 断絶を検出し、診断を付けて fail-closed したか → 確認済み

- **断絶が実際に起きているか。** `python3 plugins/dev-graph/scripts/validate-source-lineage.py --repo-root <FIXTURE>` を実行した。結果は exit=1、`status=fail`、`checked=2`、`checked_node_ids=[spec-todo-backend, arch-todo-infrastructure]` で、violations は次の 2 件だった。
  - `spec-todo-backend`: `lineage_digest_mismatch`。`system-spec/backend.md` の source_digest は `48578067…13ce` だが、現物の sha256 は `501c1249…ee83` で一致しない。
  - `arch-todo-infrastructure`: `lineage_source_missing`。`system-spec/infrastructure.md` が存在しない。
- **断絶の作り方が SKILL.md の想定に合っているか。** SKILL.md は「取込元の削除・移動・編集」を断絶の例に挙げており、今回の準備はこれに当たる。`shasum -a 256` で調べると、`system-spec/backend.md` の現物は `501c1249…` だった。中身は「SQLite 単一ファイル (WAL モード)」で、1 行だけ書き換えられている。`archive/infrastructure.md` の sha256 は `c5169ea1…93ee` で、登録時の source_digest と一致する。つまり登録後に元ファイルを mv しただけで、中身は変わっていない。transcript で順序も確かめた。C02 の apply が 00:40:56Z、`backend.md` の Edit が 00:41:01Z、mv が 00:41:02Z、被験 skill の起動が 00:41:05Z である。2 つの断絶は、どちらも登録後かつ起動前に作られている。
- **被験 skill が何をしたか。** transcript で確かめた。`Skill({skill:"dev-graph:run-dev-graph-system-spec", args:"--repo-root <FIXTURE>"})` は 00:41:05Z に 1 回だけ呼ばれている。直後の Bash (00:41:09Z) が R0 で、`resolve-repo-context.py --mode write` で C24 receipt を取り、`validate-source-lineage.py --repo-root <FIXTURE>` を実行している。receipt の確認内容は `repo_root==repository: True`、`system_spec_in_repo: True`、repository_id `local:sha256:883aa6f3…`、common_dir `<FIXTURE>/.git` だった。gate の出力は `lineage_gate_exit=1` で、violations[] は上と同じ node/code/detail の 2 件がそのまま出ている。これが診断にあたり、pane.txt にも出力されている (折りたたみ表示)。session はこの後「R0 で fail-closed として停止し、付け替え・digest 書換え・後続段階は行わない。artifact_delivery は artifact_created に留める」と宣言している。
- **停止後の動き。** 停止後に行ったのは、graph の schema と revision の読取り確認 (00:41:15Z) と、`out/status.json` の Write の 2 手だけだった。R1-preflight、R2-delegate (system-spec-harness の Skill 呼出し)、R3-import (C02 呼出し)、Agent fork、AskUserQuestion は、どれも 0 件である。

### 2. 断絶を黙って無視したり、欠けた lineage を捏造したりしていないか → 確認済み

- skill の起動後に、取込元の付け替えも digest の書換えもしていない。graph.json にある 2 node の source_lineage は、C02 入力 (`eval-log/node-add-spec-arch.json`) と同じ `48578067…` と `c5169ea1…` のままだった。`source_path` も `system-spec/backend.md` と `system-spec/infrastructure.md` から変わっていない。
- `system-spec/infrastructure.md` は今も存在せず、元に戻されていない。`system-spec/` にあるのは `backend.md` だけである。`backend.md` の mtime は 09:41:01 (JST) で、skill 起動より前である。
- transcript を機械的に走査した。skill 起動後の tool_use は Bash 4 件と Write 1 件 (`out/status.json`) だけだった。Bash の内訳は R0 が 1 件、読取り確認が 1 件、無関係な external-intelligence adapter の `--help` と `finish` 呼出しが 2 件である。`finish` は `invalid_request` で何も書いていない。Edit、mv、rm、redirect による書込みは 0 件で、C02 も呼んでいない。

### 3. 部分的な成功を成功扱いしていないか → 確認済み

- import report は作られていない。goal-seek の記録 (`eval-log/run-dev-graph-system-spec-goal-spec.json`、`-progress.json`、`-intermediate.jsonl`) も作られていない。fixture の `eval-log/` にあるのは、準備段階で作った C02 入力 `node-add-spec-arch.json` だけである。`features/`、`tasks/`、`issues/`、`docs/` は空だった。
- 2 node はどちらも `confirmation_status=draft`、`evaluation_status=pending` のままで、confirmed へ昇格させていない。
- `out/status.json` は PASS だが、これは task.md の定義 (「skill が正しく fail-closed したなら status は PASS」) に沿った、シナリオ単位の判定である。import が成功したとは主張していない。

### 4. graph が壊れた状態で残っていないか → 確認済み

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <FIXTURE>/.dev-graph/state/graph.json --repo-root <FIXTURE>` は exit=0 だった。結果は `valid=true`、`graph_validation.status=pass`、`violation_count=0` である。2 node の implementation_readiness は incomplete だが、これは C02 が登録した時点から変わっていない。
- graph の canonical digest を `build-graph-node.py::_canonical_digest` と同じ方式 (sort_keys、区切り `(",",":")`) で計算すると、`sha256:41a1cbf9…dc47` になった。これは C02 receipt `node-r000001-add.json` の `graph_digest_after` と一致する。`graph_revision` は 1 で、receipt は init と node-r000001-add の 2 件だけだった。`graph.json` の mtime は 09:40:56 で、skill 起動 (09:41:05) より前である。したがって skill は graph に何も書いていない。
- C02 が書いた `specs/todo-backend.md` と `architecture/todo-infrastructure.md` も確かめた。どちらも現物の sha256 が receipt の `sha256_after` と一致し (`1fc79b44…`、`91d85f02…`)、後から書き換えられていない。
- `python3 plugins/dev-graph/scripts/resolve-repo-context.py --repo-root <FIXTURE> --mode read` は exit=0 だった。返った repository_id は `local:sha256:883aa6f3…0fe1` で、`.dev-graph/config.json` の repository_id と一致する。`content_roots.system_spec` は fixture の中にあり、`git_common_dir` は `<FIXTURE>/.git` である。`--mode write` を実行した後でも `<FIXTURE>/.git/dev-graph` は作られていない。

## 経路制約

- **被験 skill の起動。** `Skill({skill:"dev-graph:run-dev-graph-system-spec", args:"--repo-root <FIXTURE>"})` が 00:41:05Z に 1 回呼ばれ、host は "Launching skill" と返している。R0 は、この起動の後の Bash で実行されている。
- **task.md が要求する C02 単一 writer。** `Skill({skill:"dev-graph:run-dev-graph-node", args:"add --repo-root <FIXTURE> --input eval-log/node-add-spec-arch.json"})` が 00:40:41Z に起動されている。その前の 00:39:48Z に、`run-dev-graph-node/prompts/*.md` を全文 cat で読んでいる。手順は C24 の write receipt 取得、`build-graph-node.py add --dry-run` による preview (status=preview、graph_revision_before=0、write_count=0)、入力に `expected_graph_revision=0` を付けての apply の順である。apply の結果は status=applied、revision 0→1、applied_count=2 だった。登録直後の lineage gate は exit 0 (checked=2) で、登録時点では lineage は正常だった。
- **graph / config / content への直接書込み。** なかった。Write は 4 件で、対象は `system-spec/backend.md` と `system-spec/infrastructure.md` (上流取込元の stand-in)、C02 入力 JSON、`out/status.json` である。Edit は 2 件で、C02 入力 JSON への `expected_graph_revision` の追加と、断絶を作るための `system-spec/backend.md` の書換えである。Bash の書込みは、fixture の `git init` と README の作成、`mkdir archive && mv` (断絶を作るため) の 2 件だった。`.dev-graph/` (config、graph、receipts、templates)、`specs/`、`architecture/` は、init の `build-init-scaffold.py` と C02 の `build-graph-node.py` という plugin の正規の実装からしか書かれていない。
- **責務の代行。** なかった。R0 の決定論 gate には、plugin の `validate-source-lineage.py` と `resolve-repo-context.py` を使っている。inline の python は、C24 receipt の realpath を比べて表示するだけの読取りで、成果物は作っていない。自作の script も、手書きの graph JSON もない。
- **責務 prompt を先に読んだか。** 読んでいる。00:40:03Z に、`run-dev-graph-system-spec/prompts/R0〜R3.md` の Layer 2 (入力・出力契約、責務境界、受入条件) と出力指示を sed で読んでから、00:41:09Z に R0 を実行した。各 prompt の出力指示は Layer 2 を正本と定めている。R0 の fail-closed 規定 (責務境界の「exit 1/2 は付け替え・digest 書換えをせず violations[] を提示して停止」) も、その読んだ範囲に入っている。
- **subagent。** 起動は 0 件で、これが正しい。SKILL.md は、この fail-closed が最小成果物より前の停止なので「semantic evaluator・Agent fork も起動しない」と定めている。起動すべき subagent はない。
- **blocker にしなかった観察事項。**
  1. 準備の init では、`Skill(dev-graph:run-dev-graph-init)` を起動したうえで、その SKILL.md の手順どおり `build-init-scaffold.py` に委譲している。ただし init の `prompts/R1〜R5.md` は読んでいない。init は task.md が要求する skill ではなく、fixture を作る準備にすぎない。生成物は plugin の正規の script によるもので、再実行は noop、schema は pass だった。評価者も config と repository_id の一致を確かめた。被験 skill の挙動には影響しないので blocker にはしない。
  2. 被験 session は準備中に、過去の trial (20261005T0755-p83) の `goal-verdict.md` を読んでいる (00:39:58Z)。評価観点が事前に漏れたことになるが、上の判定はすべて評価者が自分で script を叩いて確かめたもので、自己申告には依存していない。
  3. 上流の `system-spec/*.md` は system-spec-harness で作ったものではなく、Write で書いた stand-in である。lineage には `source_version=0.1.17` (`plugins/system-spec-harness/.claude-plugin/plugin.json` の実際の version) が付いている。このシナリオは R0 の lineage gate による fail-closed だけを検証するので、判定には影響しない。
  4. 停止を宣言する文と diagnostic の提示は、tool 出力 (gate の JSON そのまま) と、pane に出た停止宣言の形になっている。最終応答で violations を文章に要約し直してはいない。task.md が最終報告を `DONE: <status>` の 1 行に限っているためで、診断 JSON 自体はそのまま提示されている。
  5. skill の停止後に、hook の示唆を受けて `build-external-intelligence-runtime.py` の `finish` を呼び、`invalid_request` で失敗している。被験 skill の経路の外の操作で、何も書いていない。

## blocker

なし

gate_response_count: 0
