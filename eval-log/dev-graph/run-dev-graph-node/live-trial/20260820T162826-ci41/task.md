# タスク: dev-graph:run-dev-graph-node の実走

fixture repo内 `mixed-artifacts.json` の、内容から一意に分類できる issue、task、specification(API変更を含む)、architecture(backend+security)、document の5入力を使用してください。次にdry-runではなくC02の正規経路で登録してください:

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-node --input /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-node/mixed-artifacts.json"})

その後batch内issueだけ本文を追記して同じ呼出しで連続更新し、graph_node_idと正規pathが不変であることを確認してください。さらにfeatureらしい通常入力の直接addはC14 package契約なしとしてfail-closedになり、features/へ直登録されないことを確認してください。最終graphをC11で検証し、5 kindのfrontmatter/path、architecture subtype、API specificationの必須section、直接feature登録0件を機械確認してください。scenario IDは `C02-OUT1-positive-mixed-artifacts` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-node/live-trial/20260820T162826-ci41/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"node-five-artifact-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
