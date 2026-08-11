# タスク: dev-graph:run-dev-graph-render 正経路の実走

fixture repo `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r9-render/` には、**既に C11 schema PASS 済みの canonical graph** (`.dev-graph/state/graph.json`, 16 node = feature 4 / task 11 / architecture 1) が投入済みです。graph の新規作成・追加登録・書き換えは一切不要です。入力 graph はそのまま使ってください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r9-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r9-render/.dev-graph/render/index.html"})

そのうえで、生成 HTML について次を検証してください:

1. 外部 `script` / `link` 参照が 0 件で、http(s):// および protocol-relative (`//`) の外部リソース参照も 0 件であること (単一ファイルで完結し、追加 runtime 依存がないこと)。
2. inline SVG に feature ノードと task ノードと edge が描画されていること。
3. 表示される進捗が入力 graph の実体と一致すること (自分で `graph.json` を集計して突き合わせる)。
4. renderer が記録する入力 digest が `graph.json` の sha256 と一致すること。
5. 同一入力でもう一度 render して、出力 digest が 1 回目と一致すること (決定論)。

完了後:

1. `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260812T090000-r9/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}` を Write する。
2. `DONE: <status>` と 1 行だけ報告する。

途中で人間に質問せず最後まで自走し、skill の手順 (responsibilities の prompt 読込を含む) を省略しないこと。out/ に中間成果物を書かないこと。skill の checklist が PARTIAL のまま残る場合は status を PASS にしないこと。
