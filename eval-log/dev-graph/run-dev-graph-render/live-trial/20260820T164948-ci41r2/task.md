# タスク: dev-graph:run-dev-graph-render の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r10-render/.dev-graph/render/index.html"})

C11 PASS済みcanonical graphとregistration receiptをそのまま使い、graphの作成・追加・書き換えを禁止します。外部resource参照0、inline SVGのfeature/task/edge、`LT-FEATURE-001` の `X/13`とparent_feature由来実数、source_digest対応、2回renderの決定論digest一致を検証してください。checklistがPARTIALならPASSにしないでください。scenario IDは `render-feature-progress-positive` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260820T164948-ci41r2/out/status.json に完了マーカー1ファイルだけをWriteする。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skillの手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かないこと。
