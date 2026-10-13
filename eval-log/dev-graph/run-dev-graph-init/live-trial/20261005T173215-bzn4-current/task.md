# タスク: dev-graph:run-dev-graph-init の実走

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T173215-bzn4-current-init --hook-source plugin"})

同じ引数でもう一度実行し、6 content root、repo-local config/state/templates、plugin hook sourceが揃い、2回目の planned change が0で利用者編集を上書きしないことを確認してください。configにabsolute pathやtoken/node IDが保存されず、初期graphがC11を通ることも検証してください。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-init/live-trial/20261005T173215-bzn4-current/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"init-positive-idempotence"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止し、tracker_binding=noneを維持する。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。
