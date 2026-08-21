# タスク: dev-graph:run-dev-graph-sync の実走

fixture repoにtracker_binding=githubのconfirmed/pass/readiness-complete taskと1件のimport・1件のexport、安定したtimestamps/IDs/aliases/snapshotsを持つ決定論 `github-adapter.json` を準備してください。外部writeは常にfixture adapter内へ閉じ、同じ状態で以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-sync --binding github --adapter-fixture /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/r5-sync/github-adapter.json --repeat 2"})

1回目が期待するimport/exportを適用し、2回目のimports/exports changesがともに0、stable IDs/snapshots不変、3-way base保持であることを検証してください。remote fixture以外のGitHubへ接続しないでください。scenario IDは `C03-OUT1-positive-second-sync-zero` です。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/トークン削減対策/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260821T030000-tk2/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"sync-positive-two-pass-convergence"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **同期処理を実装する自作スクリプト (driver の類) を書かないこと。** 自作すれば、
  検証されるのは skill ではなくあなたのコードになる。3-way diff・conflict 分類・
  authority 適用・snapshot 更新・applied 集計は skill の責務経路で行うこと。
- 外部 mutation は SKILL.md の
  "Canonical external mutation receipt flow (mandatory)" を必ず通すこと
  (preview → confirmation → authorization → execute)。mutation argv の直接実行や
  auto-approval flag による迂回は禁止。receipt ファイルが残らない mutation は不正とみなす。
- remote 状態の読み取りは C12 (`gh-bridge.py`) を通すこと。
  `github-adapter.json` を直接 load して比較しないこと。
  bridge に必要な op が存在しない場合は、自前で読み取らず、その旨を FAIL として報告すること。
- SKILL.md の「ゴールシーク配線」が未達責務の fork を要求する場合は、
  Agent tool で実際に分離 context を起動すること。
- progress / goal-spec の判定値は測定結果から導出すること。
  `status: "PASS"` や evidence 文言をハードコードして書き出さないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。
