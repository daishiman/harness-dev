# タスク: dev-graph:run-dev-graph-render の実走

fixture repo `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render/` にあるC11 schema PASS済みcanonical graphと対応するregistration receiptをそのまま使用し、graphの新規作成・追加登録・書き換えをしないでください。

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render/.dev-graph/render/index.html"})

次を検証してください: 生成HTMLの外部script/link/http(s)/protocol-relative参照0、inline SVGのfeature/task/edge表示、`LT-FEATURE-001` の子task進捗 `X/Y` とreceiptの13件との一致、Xがparent_featureから導出されること、source_digest対応、同一入力の2回renderが同一digestになること。skillのchecklistがPARTIALならPASSにしないでください。scenario IDは `render-feature-progress-positive` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260820T162826-ci41/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
