# goal-verdict: dev-graph:run-dev-graph-schedule (20261005T1500-p83m)

VERDICT: PASS

## 根拠

fixture は `eval-log/dev-graph/live-trial-fixtures/p83m-schedule` (以下 F)、plugin script は `plugins/dev-graph/scripts` (以下 P) と表記する。被験 session の自己申告 (`out/status.json` = PASS) は判定に使っていない。以下はすべて evaluator が自分でコマンドを実行して確かめた。fixture を書き換える操作も、別の場所への複製もしていない。evaluator の検証の前後で F の `.dev-graph/`、`tasks/`、`eval-log/` と git common dir の `dev-graph/` の sha256 を採取し、diff が空であることも確認した。

### 前提: C24 / C11 / graph の健全性

- `python3 P/resolve-repo-context.py --repo-root F --config F/.dev-graph/config.json --mode read` は exit 0 だった。`repo_root` と `content_roots.repository` はどちらも F の realpath で一致した。`repository_id=local:sha256:a2e37dcb…800f` は config.json の値と同じ。git common dir は `gm4b-schedule/.git`。
- `python3 P/validate-graph-schema.py --graph F/.dev-graph/state/graph.json --repo-root F` は exit 0 で、`valid=true`、violations 0、graph_validation pass だった。node は 13 件あり、readiness が incomplete なのは `task-draft-idea` と `task-readiness-incomplete-ui` の 2 件。
- graph.json、config.json、init-receipt.json、tasks/*.md の sha256 は元の fixture `gm4b-schedule` と一致した (graph.json は `b2f40bab…`)。mtime も 2026-09-07 のまま。被験 session は graph と content を変更していない。
- node は 13 件すべて `tracker_binding=none` で、`beads_linkage=null`。config の `execution_tracker.mode=beads` は repo 単位の mode であり、node の binding ではない (run-dev-graph-node SKILL.md と register-package.py の規約による)。SKILL 手順 2 の「github/none は local graph から算出する」に従えば `--ready-source self` が正しい。被験 session も self を使った。
- C27 の lease: `gm4b-schedule/.git/dev-graph/` には空の `leases.lock` しかなく、`leases.json` は存在しない。つまり active lease は 0 件。被験 session が `manage-worktree-lease.py --op list` で取った snapshot も `leases=[]`、`events=[]` だった。

### 検証 1: ready-set に全依存済み task だけが入ること → 一致

- 次のコマンドを evaluator が再実行した: `python3 P/schedule-graph.py --graph F/.dev-graph/state/graph.json --ready-source self --leases gm4b-schedule/.git/dev-graph/leases.json`。exit 0 で、出力の sha256 は `782a126cd54e…6036` だった。これは被験 session の scratchpad にある `schedule.json` の sha256 とバイト単位で一致する。
- graph.json から、schedule-graph.py を使わずに独自の python で期待集合を求めた。条件は status=active、confirmation_status=confirmed、evaluation_status=pass、implementation_readiness.status=complete で、推移的にたどった depends_on がすべて done であること。結果は `task-api-orders`、`task-api-users`、`task-api-users-cache`、`task-cache-warmup`、`task-docs-runbook` の 5 件になった。
- schedule の `ready_set.tasks` はこの 5 件と完全に一致した (`features=[]`)。推移依存は `task-base-schema` か `task-base-auth` のどちらかで、両方とも done。`task-docs-runbook` には依存が無い。
- 依存が未解決の `task-api-users-e2e` は ready-set から除外されている。依存先の `task-api-users` が active のままなので、この除外は正しい。

### 検証 2: blocked / draft / unconfirmed / evaluation 非 pass / readiness 非 complete が ready-set に 0 件 → 0 件

- 同じ python で ready-set 内を数えた。blocked 0、draft 0、unconfirmed 0、eval_not_pass 0、readiness_not_complete 0、unmet_deps 0 だった。
- 除外された側の内訳は次のとおり。
  - `task-release-gate`: blocked
  - `task-draft-idea`: draft、unconfirmed、readiness incomplete
  - `task-unconfirmed-migration`: draft、unconfirmed
  - `task-eval-failed-report`: evaluation=fail
  - `task-readiness-incomplete-ui`: evaluation pending、readiness incomplete
  - `task-api-users-e2e`: 依存が未解決
  - `task-base-*`: すでに done

### 検証 3: batch 内の resource_scope 重複が 0 件 → 0 件

- `batches.tasks` は 2 つで、どちらも max_parallel=4 以下だった。
  - batch 1 (4 件): `task-api-orders`、`task-api-users`、`task-cache-warmup`、`task-docs-runbook`
  - batch 2 (1 件): `task-api-users-cache`
- 各 batch 内の全ペアについて、resource_scope の完全一致と path-prefix 包含の両方を調べた。重複ペアは 0 件だった。
- 重なりを持つのは `task-api-users-cache` だけで、`task-api-users` と `src/api/users/` を、`task-cache-warmup` と `src/cache/` を共有している。この task は別 batch に分離されている。
- ready-set の 5 件は、batch 全体にちょうど 1 回ずつ現れる。feature は 0 件なので、feature と task が同じ batch に混ざることは無い。`conflicts=[]`。

### 検証 4: suggested_branch と worktree claim command が一意であること → 一意

- `assignment_hints` は 5 件で、graph_node_id の集合は ready-set の task と一致した。
- `suggested_branch` は 5 件すべてが `devgraph/<graph_node_id>` の形で、すべて異なる (unique 5/5)。
- `claim_command` は 5 件すべてが `/dev-graph worktree claim <id> --branch devgraph/<id> --session-id <session>` の形で、すべて異なる (unique 5/5)。この形は `plugins/dev-graph/commands/dev-graph.md` に載っている公開 CLI 形式 `worktree claim <id> --branch <name> --session-id <session>` と同じ。

### read-only 契約とゴールシーク記録

- 被験 session は schedule の実行前後で graph、config、init-receipt、lease store、`bd list --json` の digest を採っていた。scratchpad の `pre.txt` と `post.txt` を evaluator が diff したところ、差分は無かった。
- `$DEV_GRAPH_ROOT/eval-log/` に goal-spec、intermediate (2 行)、progress が書かれている。SKILL.md の「ゴールシーク検証」スクリプトを evaluator が再実行すると、hash 一致と必須キーの充足を確かめて OK になった。`drift_signal` は 2 行とも false。

## 経路制約

- **Skill の起動**: transcript [37] で `Skill({skill:"dev-graph:run-dev-graph-schedule", args:"--repo-root …/p83m-schedule --max-parallel 4"})` が呼ばれ、"Launching skill" が返っている。graph や content を書き換える場面は無かったので、run-dev-graph-node を起動していないことは問題にならない。
- **使われた tool**: 被験 session が使ったのは Bash 12 回、Skill 1 回、Agent 1 回だけだった。Write、Edit、MultiEdit は 0 回。したがって `config.json`、`state/graph.json`、`state/init-receipt.json` に直接書き込んだ事実は無い。staging、lock、atomic replace、receipt を自作した痕跡も無い。
- **代行の有無**: ready-set と batch の算出は plugin の `schedule-graph.py` が行っている。C24 は `resolve-repo-context.py`、C11 は `validate-graph-schema.py`、C27 は `manage-worktree-lease.py --op list` で、いずれも plugin script を呼んでいる。session 自身が書いた python は graph の閲覧と goal-seek 記録の書き出しだけで、skill の責務を代わりに実行してはいない。
- **独立 verifier (C17)**: transcript [94] で `Agent(subagent_type="dev-graph:dev-graph-parallel-safety-verifier")` が実際に起動されている。subagent の meta (`agent-a7a2246d622af691a.meta.json`) には `agentType=dev-graph:dev-graph-parallel-safety-verifier` と記録されている。subagent が呼んだ tool は read-only の Bash だけで、ready-set を独自に再計算し、`verdict=match`、`mismatches=[]` を返した。session はこの verdict を受け取ってから完了にしており、自己判定で verifier の代わりをしてはいない。
- **artifact-delivery の choice**: task が質問を禁じているので、session は `standard` を自分で選んだ。thinking [93] にその判断があり、verifier の起動より前に決めている。選択は goal-spec の `choice` に記録された。ただし goal-spec への記録は verifier の起動 ([94]) より後の [104] だった。記録の順序がずれただけで、判断そのものは起動前に済んでいるため、blocker とはしない。
- **R-id の fork**: R1 から R3 は、軽い決定論の処理として main context で実行された。prompt-common-layers の Layer 5.1 は「重い判断または独立検証は Agent で fork する」と定めており、独立検証にあたる C17 は fork されている。
- **出力先**: `out/` にあるのは `status.json` だけ。fixture に書かれたのは、SKILL.md が指定する `eval-log/run-dev-graph-schedule-*.json(l)` の 3 ファイルだけだった。

## blocker

なし

gate_response_count: 0
