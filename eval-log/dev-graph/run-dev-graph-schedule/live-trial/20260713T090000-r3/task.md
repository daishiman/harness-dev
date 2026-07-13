# タスク: dev-graph:run-dev-graph-schedule 正経路の実走

fixture repoのconfirmed/pass/readiness-complete active taskを使用して以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-schedule --max-parallel 4"})

ready-setには全依存済みtaskだけが入り、blocked/draft/unconfirmed/evaluation非pass/readiness非completeが0、batch内resource_scope重複が0、suggested_branchとworktree claim commandが一意であることを検証してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
