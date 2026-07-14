# タスク: dev-graph:run-dev-graph-sync 二回収束の正経路実走

fixture repoにtracker_binding=githubのconfirmed/pass/readiness-complete taskと、1件のimport・1件のexport、安定したtimestamps/IDs/aliases/snapshotsを持つ決定論 `github-adapter.json` を準備してください。外部writeは常にfixture adapter内へ閉じ、同じ状態で以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-sync --binding github --adapter-fixture /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-sync/github-adapter.json --repeat 2"})

1回目が期待するimport/exportを適用し、2回目のimports/exports changesがともに0、stable IDs/snapshots不変、3-way base保持であることを検証してください。remote fixture以外のGitHubへ接続しないでください。scenario IDは `C03-OUT1-positive-second-sync-zero` です。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"sync-positive-two-pass-convergence"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
