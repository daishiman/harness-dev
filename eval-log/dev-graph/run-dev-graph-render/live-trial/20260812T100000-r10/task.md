# タスク: dev-graph:run-dev-graph-render 正経路の実走

fixture repo `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render/` には、**C11 schema PASS 済みの canonical graph** (`.dev-graph/state/graph.json`, 17 node = feature 1 / task 13 / specification 1 / architecture 1 / document 1) と、対応する registration receipt (`.dev-graph/state/lt-feature-001-registration-receipt.json`, `applied_count=13` / `expected_count=13` / `source_digest`) が既に投入済みです。graph の新規作成・追加登録・書き換えは一切不要で、**禁止**します。入力 graph と receipt はそのまま使ってください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render/.dev-graph/render/index.html"})

そのうえで、criteria OUT1 に対応する次を検証してください:

1. 生成 HTML に外部 `script` / `link` 参照が 0 件で、`http(s)://` および protocol-relative (`//`) の外部リソース参照も 0 件であること (単一ファイルで完結し、追加 runtime 依存なしにブラウザで開けること)。
2. ブラウザで開いた際に inline SVG のグラフが描画され、feature ノード・task ノード・edge が表示されること。
3. feature `LT-FEATURE-001` の子 task 進捗が `X/Y` 形式で表示され、分母 `Y` が registration receipt の `applied_count` / `expected_count` (ともに 13) と一致すること。
4. 分子 `X` が `graph.json` 上で `parent_feature=LT-FEATURE-001` かつ完了状態の task 実数と一致すること。手入力値や定数ではなく `parent_feature` から導出されていることを `render-graph-html.py` の実装でも確認すること。
5. 表示対象が receipt の `source_digest` に対応すること (renderer の記録する入力 digest と `graph.json` / receipt の digest を突き合わせる)。
6. 同一入力でもう一度 render して出力 digest が 1 回目と一致すること (決定論)。

完了後:

1. `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260812T100000-r10/out/status.json` だけに `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}` を Write する。
2. `DONE: <status>` と 1 行だけ報告する。

途中で人間に質問せず最後まで自走し、skill の手順 (responsibilities の prompt 読込を含む) を省略しないこと。out/ に中間成果物を書かないこと。skill の checklist が PARTIAL のまま残る場合は status を PASS にしないこと。
