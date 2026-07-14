# タスク: dev-graph:run-dev-graph-render の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7 --output eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T071500-r1/render.html。入力は eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T071500-r1/fixture-graph.json を使う。外部script/link/CDNなし、SVGとfeature progress 1/2を確認する"})

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T071500-r1/out/status.json に完了マーカーを1ファイルだけ Write する。内容:
   {"status":"PASS|FAIL|ERROR","rendered_html":"eval-log/dev-graph/run-dev-graph-render/live-trial/20260713T071500-r1/render.html"}
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
