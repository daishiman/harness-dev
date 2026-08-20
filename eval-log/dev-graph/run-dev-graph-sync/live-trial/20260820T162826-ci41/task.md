# タスク: dev-graph:run-dev-graph-sync の実走

fixture repoにtracker_binding=githubのconfirmed/pass/readiness-complete taskと1件のimport・1件のexport、安定したtimestamps/IDs/aliases/snapshotsを持つ決定論 `github-adapter.json` を準備してください。外部writeは常にfixture adapter内へ閉じ、同じ状態で以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-sync --binding github --adapter-fixture /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-sync/github-adapter.json --repeat 2"})

1回目が期待するimport/exportを適用し、2回目のimports/exports changesがともに0、stable IDs/snapshots不変、3-way base保持であることを検証してください。remote fixture以外のGitHubへ接続しないでください。scenario IDは `C03-OUT1-positive-second-sync-zero` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260820T162826-ci41/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"sync-positive-two-pass-convergence"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
