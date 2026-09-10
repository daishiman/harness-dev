# タスク: dev-graph:run-dev-graph-schedule 正経路の実走

fixture repoのconfirmed/pass/readiness-complete active taskを使用して以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /Users/dm/orca/workspaces/harness/ジャーナル作成/eval-log/dev-graph/live-trial-fixtures/r8-schedule --max-parallel 4"})

ready-setには全依存済みtaskだけが入り、blocked/draft/unconfirmed/evaluation非pass/readiness非completeが0、batch内resource_scope重複が0、suggested_branchとworktree claim commandが一意であることを検証してください。

1. `/Users/dm/orca/workspaces/harness/ジャーナル作成/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20260818T004500-r12/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set"}` をWriteする。
2. `DONE: <status>` と1行だけ報告する。

途中で人間に質問せず最後まで自走し、skillの手順を省略しないこと。out/に中間成果物を書かないこと。

fixture repo は git init 済みの空リポジトリです。dev-graph の初期化 (C01) と graph 準備も、手作業でなく skill の正規経路で行ってください。
