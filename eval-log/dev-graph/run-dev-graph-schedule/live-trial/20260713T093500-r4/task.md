# R4: schedule current-closure proof

Invoke `Skill({skill:"dev-graph:run-dev-graph-schedule",args:"--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-schedule"})`. Compute the real ready set from dependencies, leases, tracker binding and resource scopes; verify no blocked/conflicting task is scheduled and preserve a machine-readable receipt. C11 must remain exit 0.

On real success only, write `{"status":"PASS","scenario":"schedule-current-closure-ready-set"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20260713T093500-r4/out/status.json`; otherwise FAIL. End `DONE: <status>`.
