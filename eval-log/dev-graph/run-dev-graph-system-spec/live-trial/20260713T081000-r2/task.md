# タスク: dev-graph:run-dev-graph-system-spec の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-system-spec --resume"})

これはcontract-negative試験です。system_spec content rootがrepo外symlinkであることをC24 containmentで検出し、system-spec-harness呼出し0、C02 import 0、fallback生成0で停止すればPASSです。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20260713T081000-r2/out/status.json` に完了マーカーを1ファイルだけWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"system-spec-containment"}`
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。中間成果物はfixture repo内またはtrial workdir直下へ置くこと。
