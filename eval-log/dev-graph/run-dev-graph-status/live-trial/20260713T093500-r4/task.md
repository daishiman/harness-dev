# R4: status current-closure read-only proof

Invoke `Skill({skill:"dev-graph:run-dev-graph-status",args:"--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-status"})`. Snapshot canonical graph/config bytes before and after, emit the real status summary, and prove the command is read-only with identical hashes. C11 must exit 0.

On real success only, write `{"status":"PASS","scenario":"status-current-closure-read-only"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-status/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
