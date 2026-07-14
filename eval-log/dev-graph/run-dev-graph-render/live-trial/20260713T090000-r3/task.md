# タスク: dev-graph:run-dev-graph-render 正経路の実走

fixture repoのcanonical graphへ、confirmed/pass/readiness-complete feature 1件とdone task 1件・active task 1件をC02/C11契約に従って準備し、登録receiptの expected_count/applied_count/source_digest を保持してください。次に以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-render --output /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r3-render/.dev-graph/render/index.html"})

生成HTMLに外部script/linkが0、inline SVGにfeature/task/edgeが表示され、feature進捗が1/2、表示対象digestがreceipt source_digestに対応し、追加runtime依存がないことを検証してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T090000-r3/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。
