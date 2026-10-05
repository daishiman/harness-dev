# goal-verdict: dev-graph:run-dev-graph-status (20261005T0803-p83c)

VERDICT: FAIL

## 根拠

対象 id: `task-lt-task-001` (writer が slug `lt-task-001` から割り当てた id)。fixture は read-only の操作だけで確認し、複製はしていない。

### 検証 1: 出力の status / closed_at / depends_on が graph の実値と一致すること → 未確認 (出力が存在しない)

- graph の実値 (`python3` で `.dev-graph/state/graph.json` を読み取りのみ):
  - `graph_revision=2`
  - `task-lt-task-001`: `status=closed`、`closed_at=2026-10-04T23:05:20.692954Z`、`depends_on=["task-lt-task-000"]`、dependents は `task-lt-task-002`、`file_path=tasks/lt-task-001.md`、`tracker_binding=none`、`github_linkage=null`、`beads_linkage=null`
  - depends_on の参照切れ 0 件。準備段階の前提 (depends_on を持ち、closed_at に意味がある) は満たしている。
- 被験 session の出力: transcript.jsonl から assistant の text/thinking ブロックを全件抽出し、`closed_at` / `depends_on` / `dependents` を含むものを探した。該当は準備段階の 1 行 (`Now close task-lt-task-001 via update so closed_at is set.`) だけだった。status skill を起動したあとの assistant 発話は次の 3 つしかない。
  - `R1 query: {graph_node_id: "task-lt-task-001"}, ...`
  - `Report built from the graph snapshot. Post-run digest and side-effect check:`
  - `DONE: PASS`
- pane.txt の終了画面にも report 本文はない。graph.json を `Read` しただけ (`Read 1 file`) で、SKILL.md の Purpose & Output Contract が定める検索 report (`graph_node_id/artifact_kind/project_id/domain/tags/file_path/status/closed_at/depends_on/dependents/parent_feature/feature_package_id/tracker_binding/linkage`) は一度も出力されていない。
- SKILL.md の Pre-choice 節が求める「現物 path・digest・開き方の提示」と「accept-as-is/light/standard/detailed の記録」も、status skill では行われていない。
- 比べる出力がないため、この項目は一致を確認できない。

### 検証 2: C11 (`validate-graph-schema.py`) が exit 0 であること → 確認済み

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <FIXTURE>/.dev-graph/state/graph.json --repo-root <FIXTURE>` を実行した結果は exit=0、`valid=true`、`graph_validation={status: pass, violation_count: 0}`、`violations=[]`。
- 被験 session の transcript にも同じコマンドの `exit=0` が残っている。
- C24 `resolve-repo-context.py --repo-root <FIXTURE> --mode read` は exit 0。`repo_root` と `content_roots.repository` はどちらも fixture の realpath で、`repository_id=local:sha256:004324ba...feb1`。

### 検証 3: 被験 skill 実行の前後で graph digest が不変であること → 確認済み

- 被験 session は status skill の起動後、実行前と実行後に同じ手順で digest を取っている。手順は「`config.json`・`state/`・6 つの content root の全ファイルの sha256 を並べ、その一覧の sha256 を取る」。結果は前後とも `a71768932c5bcaebb762939cd03efd74861a546c8796fa1cfa63e102e3944f85`。
- 同じ手順を現在の fixture で再計算した (path は repo 相対)。結果は `a71768932c5bcaebb762939cd03efd74861a546c8796fa1cfa63e102e3944f85` で一致した。
- mtime: graph.json と tasks/lt-task-001.md の最終更新は 08:05:21 (= 23:05:21Z)。status skill の起動 (Skill 呼び出し 23:05:23.158Z) より前なので、skill 実行中に graph/content/config は書かれていない。

### 検証 4: GitHub / Beads への write が 0 件であること → 確認済み

- transcript の Bash 18 件を走査した。`gh` / `bd` / `gh-bridge.py` / `bd-bridge.py` / `git push` / `git commit` の呼び出しは 0 件。
- fixture: `.beads` は存在しない。`git log --all` は `a9d20fb init` の 1 件だけ。`git config --local` に remote の設定はない。config の `github.enabled=false`、全ノードで `tracker_binding=none`。

## 経路制約

- Skill 起動: `dev-graph:run-dev-graph-init` (23:04:30Z)、`dev-graph:run-dev-graph-node` (23:04:41Z)、`dev-graph:run-dev-graph-status` (23:05:23Z) の 3 つとも Skill tool で起動されている。args は task.md の指定どおり。
- graph への書込みの経路:
  - graph/content/receipt はすべて C02 writer の `build-graph-node.py` が書いている。add で revision 0→1、update で `status=closed` にして 1→2。receipt は `node-r000001-add.json` と `node-r000002-update.json`。どちらも `--dry-run` で preview してから `expected_graph_revision` を渡して apply している。
  - Write tool の書込みは 2 件だけ: `.dev-graph/cache/node-add-input.json` (writer の入力 JSON。node SKILL.md が定める `--input <repo 内 JSON>` 経路) と `out/status.json`。
  - python の 1 行コードと `echo >` で書き換えたのも writer の入力 JSON (`node-add-input.json` / `node-update-input.json`) だけ。graph/config を直接書いた箇所はない。
- 代行: 被験 skill の責務を代わりに実行する自作 script は書いていない。status の検索は graph.json を `Read` しただけで、report は生成されていない。
- subagent: Agent tool の起動は 0 回。3 つの skill とも `pre_choice_forbidden` に subagent が含まれ、Agent による fork は light/standard/detailed を選んだ後の段階でだけ要求される。今回は要求されておらず、この点は違反ではない。
- 責務 prompt を読んだか (task.md の経路制約「責務 prompt は、その責務の出力を作る前に必ず読むこと」):
  - run-dev-graph-init: `prompts/R1-elicit.md`〜`R5-hooks.md` を一度も読まずに `build-init-scaffold.py` を実行し、init の成果物を作っている (Read は 1 回で対象は graph.json、Bash でも init prompts を開いていない)。**違反**。
  - run-dev-graph-node: `prompts/*.md` を cat で全文読んでから入力 JSON を作っている。適合。
  - run-dev-graph-status: `sed -n '/## Layer 2/,/## Layer 4/p'` で Layer 2〜3 だけを抜き出して読んでいる。Layer 5 の完了チェックリストと「出力指示」は読んでいない。部分読みで不完全。

## blocker

1. 被験 skill の成果物 (status report) が出力されていない。status/closed_at/depends_on を含む検索 report が会話にも画面にも存在しない。検証 1 は比べる対象がなく未確認であり、description が約束する「依存・tombstone・completion 状態を確認できる」成果も出ていない。SKILL.md の Pre-choice 節が求める現物の提示と選択の記録もない。
2. 経路制約違反: run-dev-graph-init の責務 prompt (R1〜R5) を読まずに init の成果物を作った。status skill の責務 prompt も Layer 2〜3 しか読んでいない。
3. 被験 session の自己申告 `out/status.json` は `PASS` だが、1 の理由で実態と合わない。

gate_response_count: 0
