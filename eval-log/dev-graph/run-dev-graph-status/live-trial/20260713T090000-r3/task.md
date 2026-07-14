# タスク: dev-graph:run-dev-graph-status 正経路の実走

実行前のcanonical graph digestを保存して以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-status", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-status --id LT-TASK-001"})

出力のstatus/closed_at/depends_onがgraph実値と一致し、C11 exit0、実行後graph digest不変、GitHub/Beads write 0であることを検証してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-status/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"status-positive-read-only"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
