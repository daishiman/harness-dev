# タスク: dev-graph:run-dev-graph-schedule の実走

fixture repoのconfirmed/pass/readiness-complete active taskを使用して以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r8-schedule --max-parallel 4"})

ready-setには全依存済みtaskだけが入り、blocked/draft/unconfirmed/evaluation非pass/readiness非completeが0、batch内resource_scope重複が0、suggested_branchとworktree claim commandが一意であることを検証してください。fixture repoはgit init済みです。dev-graph初期化(C01)とgraph準備も手作業ではなくskillの正規経路で行ってください。scenario IDは `schedule-positive-ready-set` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/トークン削減対策/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20260821T030000-tk2/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
