# R4: run-dev-graph-init current-closure proof

Invoke `Skill({skill:"dev-graph:run-dev-graph-init",args:"--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r4-init"})` and follow the loaded skill. Run the real initialization twice against this already-initialized Git repository. Prove both passes are idempotent: required directories/config/state remain valid, no canonical file content changes on the second pass, and C11 exits 0. Store receipts in the fixture, not in `out/`.

Only after those checks pass, write `{"status":"PASS","scenario":"init-current-closure-idempotence"}` to `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-init/live-trial/20260713T093500-r4/out/status.json`. Otherwise write FAIL with the same scenario. End with `DONE: <status>`.
