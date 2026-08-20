# タスク: dev-graph:run-dev-graph-decompose の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "認証付きTODO APIをarchitecture、認証feature、TODO featureへマクロ分解する。TODOは認証に依存。全nodeはtracker_binding=none。 --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-decompose --dry-run"})

feature+architecture DAGが循環なし、task粒度混入なし、全node draft preview、外部write 0、原graph digest不変であることを検証してください。featureを通常C02 addとして直登録していないことも確認してください。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20260820T162826-ci41/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
