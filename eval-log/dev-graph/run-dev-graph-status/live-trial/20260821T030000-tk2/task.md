# タスク: dev-graph:run-dev-graph-status の実走

実行前のcanonical graph digestを保存して以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-status", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r8-status --id LT-TASK-001"})

出力のstatus/closed_at/depends_onがgraph実値と一致し、C11 exit0、実行後graph digest不変、GitHub/Beads write 0であることを検証してください。fixture repoはgit init済みです。dev-graph初期化(C01)とgraph準備も手作業ではなくskillの正規経路で行ってください。scenario IDは `C18-OUT1-positive-read-only-status` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/トークン削減対策/eval-log/dev-graph/run-dev-graph-status/live-trial/20260821T030000-tk2/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"status-positive-read-only"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
