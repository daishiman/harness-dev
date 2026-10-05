# goal-verdict: dev-graph:run-dev-graph-system-spec (20261005T0755-p83)

VERDICT: PASS

## 根拠

判定の基準は task.md の「検証」4 項目と、SKILL.md「Resume と lineage gate」(L105-112) と R0-context.md の責務境界である。SKILL.md と R0-context.md は、lineage gate が exit 1/2 のとき `violations[]` を提示して停止し、artifact_delivery を `artifact_created` に留め、semantic evaluator と Agent fork を起動しないことを要求している。被験 session の自己申告 (`out/status.json` の PASS) は判定に使っていない。以下はすべて評価者が自分で実行して確かめた結果である。

### 1. lineage 断絶を検出し、診断を付けて fail-closed したか → 確認済み

- 断絶が本当に起きていることを fixture で確かめた。`python3 plugins/dev-graph/scripts/validate-source-lineage.py --repo-root <FIXTURE>` は exit=1 で、`status=fail`、`checked=2` を返した。violations は次の 2 件。
  - `spec-todo-backend`: `lineage_digest_mismatch`。`system-spec/backend.md` の source_digest `fe9e3371…` に対し、現物の sha256 は `cab422c5…` だった。
  - `arch-todo-infrastructure`: `lineage_source_missing`。`system-spec/infrastructure.md` が存在しない。
- 断絶の作り方が SKILL.md L110 の想定 (取込元の削除・移動・編集) と合っていることも確かめた。`system-spec/backend.md` は C02 登録 (22:52:25Z) の後、22:52:32Z に Edit で書き換えられている。`archive/infrastructure.md` の sha256 は登録時の digest `e3eb81b8…` と一致するので、登録後に元ファイルを mv したものと分かる。
- 被験 skill の実行内容を transcript で確かめた。Skill 呼出しは #23 (22:52:38Z) で、その直後の #24 で R0 を実行している。中身は `resolve-repo-context.py --mode write` による C24 receipt の取得と、`validate-source-lineage.py --repo-root <FIXTURE>` の実行である。gate の出力は `lineage_gate_exit=1` で、上の 2 件と同じ node/code/detail の violations[] がそのまま出ている。これが診断にあたる。
- その後の動きは #25 (graph の schema と revision の確認、読取りのみ) と #26 (status.json の Write) の 2 手だけだった。R1-preflight、R2-delegate (system-spec-harness の Skill 呼出し)、R3-import (C02 呼出し)、Agent fork、AskUserQuestion はどれも 0 件で、R0 で停止している。

### 2. 断絶を黙って無視したり、欠けた lineage を捏造したりしていないか → 確認済み

- skill の起動後に、取込元の付け替えも digest の書換えもしていない。graph.json の 2 node の source_lineage は、C02 入力と同じ `fe9e3371…` と `e3eb81b8…` のままである。`system-spec/backend.md` の mtime は 22:52:32Z で、skill 起動 (22:52:38Z) より前である。`system-spec/infrastructure.md` は今も存在せず、元に戻されていない。
- skill 起動後の tool_use は Bash 3 件と Write 1 件 (out/status.json) だけで、Edit、mv、C02 呼出しは 0 件だった。

### 3. 部分的な成功を成功扱いしていないか → 確認済み

- import report も、goal-seek の記録 (`eval-log/run-dev-graph-system-spec-goal-spec.json`、`-progress.json`、`-intermediate.jsonl`) も作られていない。fixture の `eval-log/` にあるのは、準備段階で作った C02 入力の `node-add-spec-arch.json` だけである。
- 2 node は `confirmation_status=draft`、`evaluation_status=pending` のままで、confirmed へ昇格させていない。
- `out/status.json` は PASS だが、これは task.md の定義 (「skill が正しく fail-closed したなら status は PASS」) に沿った scenario 単位の判定である。skill の import が成功したとは主張していない。

### 4. graph が壊れた状態で残っていないか → 確認済み

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <FIXTURE>/.dev-graph/state/graph.json --repo-root <FIXTURE>` は exit=0 で、`valid=true`、`graph_validation.status=pass`、`violation_count=0` だった。
- graph の canonical digest を `build-graph-node.py::_canonical_digest` と同じ方式で計算すると `sha256:3bbc9d8a…c0be` になった。これは C02 receipt `node-r000001-add.json` の `graph_digest_after` と一致する。graph_revision は 1 で、receipt は init と node-r000001-add の 2 件だけだった。graph.json の mtime (22:52:25Z) は skill 起動より前なので、skill は graph に何も書いていない。
- `resolve-repo-context.py --repo-root <FIXTURE> --mode read` は exit=0 だった。repository_id は `local:sha256:d44373da…` で、`.dev-graph/config.json` の repository_id と一致する。`content_roots.system_spec` は fixture 内にある。

## 経路制約

- **被験 skill の起動**: `Skill({skill:"dev-graph:run-dev-graph-system-spec", args:"--repo-root <FIXTURE>"})` は 2 回呼ばれている。1 回目の #3 は fixture を作る前で、SKILL.md を読むために load しただけで手順は実行していない。2 回目の #23 は準備が終わった後で、host は "already loaded; instructions unchanged" と返し、args も正しかった。R0 は #23 の後に実行されている。
- **C02 単一 writer**: `Skill({skill:"dev-graph:run-dev-graph-node", args:"add --repo-root <FIXTURE> --input eval-log/node-add-spec-arch.json"})` が #14 で起動されている。その skill の手順のとおり、R0 から R4 の prompts (Layer 2) を読み (#15)、C24 write receipt を取り、`build-graph-node.py add --dry-run` で preview して (#18、#19、graph_revision_before=0)、`expected_graph_revision=0` を付けて apply した (#20、status=applied、applied_count=2)。登録直後の lineage gate は exit 0 だった。
- **graph / config / content への直接書込み**: なかった。Write の対象は 4 件で、`system-spec/backend.md` と `system-spec/infrastructure.md` (上流取込元の stand-in)、C02 入力 JSON、`out/status.json` である。Edit は `system-spec/backend.md` の 1 件で、断絶を作るための上流側の編集である。`.dev-graph/state/graph.json`、`config.json`、receipts、`specs/`、`architecture/` には Write、Edit、redirect のどれでも書いていない。#20 の heredoc が書き換えたのは C02 入力 JSON (expected_graph_revision を付けただけ) で、graph ではない。
- **責務の代行**: なかった。R0 の決定的な gate は plugin の `validate-source-lineage.py` と `resolve-repo-context.py` で行っている。#24 の inline python は C24 receipt の realpath を比べて表示するだけの読取りで、成果物を作っていない。
- **責務 prompt を先に読んだか**: 読んでいる。#11 で `skills/run-dev-graph-system-spec/prompts/*.md` を全部読んでから R0 を実行した。
- **subagent**: 起動は 0 件で、これが正しい。SKILL.md L111 は、この fail-closed が最小成果物より前の停止なので「semantic evaluator・Agent fork も起動しない」と定めている。起動すべき subagent は無い。
- **blocker にしなかった観察事項**:
  1. fixture の init は `Skill(dev-graph:run-dev-graph-init)` を通さず、C01 の実装本体 `build-init-scaffold.py` を Bash で直接実行している (#7)。task.md は init skill の起動を要求していない。script は plugin が持つ正規の実装で、自作 script でも手書き JSON でもないため、blocker にはしない。
  2. 被験 session は準備中に、過去 trial (20261004T1020-f11) の `verdict.json` と `goal-verdict.md` を読んでいる (#9、#10)。評価観点が事前に漏れたことになるが、上の判定はすべて評価者が自分で script を叩いて確かめたもので、自己申告には依存していない。
  3. C02 入力の `imported_at` は `2026-10-05T08:00:00Z` で、実際の登録時刻 (2026-10-04T22:52Z) より後の時刻を手で書いている。fixture のデータの品質の問題で、被験 skill の挙動とは関係しない。

## blocker

なし

gate_response_count: 0
