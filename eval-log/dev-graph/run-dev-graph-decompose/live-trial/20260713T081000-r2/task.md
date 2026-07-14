# タスク: dev-graph:run-dev-graph-decompose の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "認証付きTODO APIをarchitecture、認証feature、TODO featureへ分解する。TODOは認証に依存。全nodeはtracker_binding=none、draft previewのみ --repo-root /Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/live-trial-fixtures/r2-decompose --dry-run"})

処理が終了したら、外部tracker writeが0で、previewがfeature/architecture/機能間依存だけを含むことを確認してください。成功・期待どおりのfail-closed・予期しない失敗を区別してください。

1. `/Users/dm/dev/dev/個人開発/harness/.worktrees/task-20260712-134250-wt-7/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20260713T081000-r2/out/status.json` に完了マーカーを1ファイルだけWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"decompose-dry-run"}`
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。中間成果物はfixture repo内またはtrial workdir直下へ置くこと。
