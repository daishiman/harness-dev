# タスク: dev-graph:run-dev-graph-status の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-status", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-status --id LT-TASK-001 --kind task --status active --tag safe"})

処理が終了したらAND検索でLT-TASK-001だけが返り、identity/kind/status/depends_on/linkageがfixture一致し、graph/config/content digestが不変であることを確認してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-status/live-trial/20260713T081000-r2/out/status.json` に完了マーカーを1ファイルだけWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"status-read-only"}`
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。中間成果物はfixture repo内またはtrial workdir直下へ置くこと。
