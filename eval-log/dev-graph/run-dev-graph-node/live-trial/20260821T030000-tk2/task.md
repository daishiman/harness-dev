# タスク: dev-graph:run-dev-graph-node の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-node --input /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-node/mixed-artifacts.json"})

fixtureは既に正規経路で初期化済みです。開始前の削除・reset・`rm`・手書きgraph初期化は禁止し、現在のfixtureに対する冪等な正規C02経路だけを使用してください。issueだけ本文追記後に同じ呼出しで連続更新し、graph_node_id/path不変を確認してください。featureらしい通常入力の直接addはC14でfail-closed、features/直登録0であることを確認し、最終graphをC11で検証してください。5 kindのfrontmatter/path、architecture subtype、API specification必須sectionを機械確認します。scenario IDは `C02-OUT1-positive-mixed-artifacts` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:
1. /Users/dm/orca/workspaces/harness/トークン削減対策/eval-log/dev-graph/run-dev-graph-node/live-trial/20260821T030000-tk2/out/status.json に完了マーカー1ファイルだけをWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"node-five-artifact-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。
