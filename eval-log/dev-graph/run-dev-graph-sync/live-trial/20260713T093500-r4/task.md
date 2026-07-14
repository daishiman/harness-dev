# R4: sync two-pass convergence under current closure

Invoke `Skill({skill:"dev-graph:run-dev-graph-sync",args:"--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-sync --adapter-fixture github-adapter.json"})`. First add one new deterministic remote update to the adapter fixture, then execute two real sync loops through the loaded skill. Loop 1 must apply the update; loop 2 must report total changes 0 with stable IDs and preserved three-way base. Validate C11 exit 0 and save both loop receipts in the fixture.

On real success only, write `{"status":"PASS","scenario":"sync-current-closure-two-pass"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
