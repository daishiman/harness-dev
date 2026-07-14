# タスク: dev-graph:run-dev-graph-init 正経路の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-init --hook-source plugin"})

同じ引数でもう一度実行し、6 content root、repo-local config/state/templates、plugin hook source が揃い、2回目の planned change が0で利用者編集を上書きしないことを確認してください。configにabsolute pathやtoken/node IDが保存されず、初期graphがC11を通ることも検証してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-init/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"init-positive-idempotence"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
