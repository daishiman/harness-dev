# タスク: dev-graph:run-dev-graph-init の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-init --hook-source plugin"})

処理が終了したら同じ引数の2回目を実行し、6 content rootとsystem-spec、repo-local config/state/cache/locks/templatesがrepo内だけに存在し、2回目の変更が0であることを確認してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-init/live-trial/20260713T081000-r2/out/status.json` に完了マーカーを1ファイルだけWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"init-idempotence"}`
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。中間成果物はfixture repo内またはtrial workdir直下へ置くこと。
