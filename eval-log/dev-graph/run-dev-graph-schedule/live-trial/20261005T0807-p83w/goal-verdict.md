# goal-verdict: dev-graph:run-dev-graph-schedule (20261005T0807-p83w)

VERDICT: PASS

## 根拠

fixture は `eval-log/dev-graph/live-trial-fixtures/p83w-schedule` (以下 F)、plugin script は `plugins/dev-graph/scripts` (以下 P)。被験 session の自己申告 (`out/status.json` = PASS) は使わず、以下をすべて evaluator が自分で叩いて確かめた。fixture を書き換える操作も、別の場所への複製もしていない。

### 前提の確認 (C24 と graph の健全性)

- `python3 P/resolve-repo-context.py --mode read --repo-root F` → exit 0。`repo_root` と `content_roots.repository` はどちらも F の realpath で一致した。`repository_id` は `local:sha256:a2e37dcb…800f` (config.json の値と一致)。git common dir は `gm4b-schedule/.git`。
- `python3 P/validate-graph-schema.py --repo-root F --graph F/.dev-graph/state/graph.json` → `valid=true`、violations 0、graph_validation pass。node は 13 件。readiness が incomplete なのは `task-draft-idea` と `task-readiness-incomplete-ui` の 2 件。
- node は 13 件すべて `tracker_binding=none`。SKILL の規則「github/none は local graph から算出する」に従うと、`--ready-source self` を使うのが正しい。被験 session も self を使った。

### 検証 1: ready-set に全依存済み task だけが入ること → 一致

- `python3 P/schedule-graph.py --graph F/.dev-graph/state/graph.json --ready-source self --leases <gm4b-schedule/.git/dev-graph/leases.json>` を再実行した。出力の sha256 は `782a126c…6036` で、被験 session の scratchpad にある `schedule.json` と同じバイト列だった。
- graph から eligible な task を独自の python で算出した。条件は status=active、confirmed、pass、readiness complete で、推移的な depends_on をすべてたどって done であることも確かめた。期待集合は次の 5 件。
  - `task-api-orders` / `task-api-users` / `task-api-users-cache` / `task-cache-warmup` / `task-docs-runbook`
- schedule の `ready_set.tasks` はこの 5 件と完全に一致した (`features=[]`)。各 task の推移依存は `task-base-schema` か `task-base-auth` で、どちらも done。`task-docs-runbook` は依存を持たない。
- 依存が未解決の `task-api-users-e2e` は除外されている。依存先の `task-api-users` が active のままだからで、正しい。

### 検証 2: blocked / draft / unconfirmed / evaluation 非 pass / readiness 非 complete が ready-set に 0 件 → 0 件

- ready-set 5 件を分類ごとに数えた結果は、blocked 0、draft 0、unconfirmed 0、eval_non_pass 0、readiness_non_complete 0、依存未充足 0。
- 除外された node と理由は次のとおり。
  - `task-release-gate`: blocked。
  - `task-draft-idea`: draft、pending、incomplete。
  - `task-unconfirmed-migration`: draft で未確認、pending。
  - `task-eval-failed-report`: evaluation=fail。
  - `task-readiness-incomplete-ui`: pending、incomplete。
  - `task-base-schema` と `task-base-auth`: done。
- 上の除外はどれも ready-set に入っていない。

### 検証 3: batch 内の resource_scope 重複 0 件 → 0 件

- tasks batch 0 は `[task-api-orders, task-api-users, task-cache-warmup, task-docs-runbook]` の 4 件で、上限の max-parallel 4 以内。scope は `src/api/orders/`、`src/api/users/`、`src/cache/`、`docs/runbook/` で互いに重ならない。
- tasks batch 1 は `[task-api-users-cache]` の 1 件。scope は `src/api/users/` と `src/cache/`。batch 0 の users と cache-warmup の両方と重なるので、別 batch に分けたのは正しい。
- 全 batch の全ペアについて、完全一致に加えて prefix の包含まで調べた。重複ペアは 0 件。
- batch の構成員は ready-set と同じ集合で、重複はない。feature と task が同じ batch に混ざることもない (feature 候補は 0 件)。
- `conflicts=[]`、`unmapped=[]`。lease store (`leases.json`) は存在しないので active lease は 0 件で、lease による除外も無い。

### 検証 4: suggested_branch と worktree claim command の一意性 → 一意

- `assignment_hints` は 5 件で、graph_node_id は ready tasks と一致した。
- suggested_branch は 5 件とも `devgraph/<graph_node_id>` の形で、重複は 0。
- claim_command は 5 件とも `/dev-graph worktree claim <id> --branch devgraph/<id> --session-id <session>` の形で、重複は 0。これは `commands/dev-graph.md` の公開表 (`worktree claim <id> --branch <name> --session-id <session>`) の形と一致する。

### graph / content / config / lease を書き換えていないこと

- `graph.json` の sha256 は `b2f40bab…b8b8`、`config.json` は `a959e492…2fe3`、`init-receipt.json` は `4338e2cf…bb12`。3 つとも元 fixture `gm4b-schedule` と同じ値で、mtime も 2026-09-07 のまま。
- `tasks/*.md` は 13 件とも `cmp` で元 fixture とバイト単位で一致した。
- evaluator 自身のコマンドの前後でも、graph の digest は変わっていない。
- lease の ledger (`leases.json` / `events.json`) は実行の前も後も存在しない。実行中に増えたのは空の `leases.lock` 1 つだけで、`manage-worktree-lease.py --op list` が flock を取るために作ったもの。コード上、`list` は lock を取った直後に ledger へ書かずに return するので、lease の状態は変わっていない。
- fixture に新しく増えたのは `eval-log/run-dev-graph-schedule-{goal-spec.json,progress.json,intermediate.jsonl}` だけ。これは SKILL の「ゴールシーク配線」が `$DEV_GRAPH_ROOT/eval-log/` に書くよう要求している記録で、graph や content ではない。SKILL のゴールシーク検証 snippet を evaluator が再実行すると OK (2 行、goal hash 一致)。

## 経路制約

- Skill の起動: transcript [36] で `Skill({skill:"dev-graph:run-dev-graph-schedule", args:"--repo-root …/p83w-schedule --max-parallel 4"})` を実行し、"Launching skill" が返っている。graph の書換えは必要なかったので、run-dev-graph-node を起動していなくても問題ない。
- 使われたツールは `Skill`、`Bash`、`Agent` の 3 種類だけ。Write / Edit は一度も呼ばれていないので、`config.json`、`state/graph.json`、`state/init-receipt.json` に直接書いた事実は無い。graph の書換え経路 (staging、lock、atomic replace、receipt) を自作した痕跡も無い。
- ready-set の算出は plugin の `schedule-graph.py` で行っている。自作 script で代行してはいない。session は graph を python で読んで一覧を出したが、これは read-only の確認で、算出結果は script の出力と同じ。
- 独立 verifier: transcript [91] で `Agent(subagent_type="dev-graph:dev-graph-parallel-safety-verifier")` (C17) を実際に起動した。subagent の meta と transcript で確かめると、agentType は一致し、tool use は read-only の Bash 2 回だけ。結果は verdict PASS で、mismatches と batch_overlaps はどちらも空。自己判定で代わりにした事実は無い。
- artifact-delivery の choice: task が質問を禁じているので、session は `light` を自分で記録し、C17 verifier を走らせた。SKILL 手順 5 (verifier が不一致なら推薦しない) と task の verifier 起動要件の両方を満たすための選択なので、省略や逸脱ではない。R1 から R3 は pre-choice の main context で完了していた。post-choice の時点で未達の responsibility は無かったので、R-id の fork は起きていない (SKILL は「未達 responsibility を fork」と定めている)。
- `out/` に書かれたのは `status.json` だけ。最後に `build-external-intelligence-runtime.py` を呼んで invalid_request で失敗しているが、fixture にも成果にも影響しない。

## blocker

なし

gate_response_count: 0
