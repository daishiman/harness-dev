# タスク: dev-graph:run-dev-graph-sync の実走

## 必須の実行順序（Skill内部の監査にも適用）
standardはこの隔離試行について事前指定済み。追加質問は不要だが、順序は省略しない。
まずmain contextだけで最小成果物/previewを作成する→実在するpathとbytes digestをassistantメッセージで提示する→canonical artifact-deliveryへstandardを記録する→その後でsemantic evaluator/auditor/Agentを起動する。
Agent前に提示と選択記録が揃わなければ、最終状態が合っていてもFAILとして止める。責務の依存順・fixture境界を守る。

この run は scenario C03-OUT1-positive-second-sync-zero-r2 の充足を確認するものです。
1. the first sync applies the expected import and export
2. the second sync reports imports changes=0 and exports changes=0
3. stable IDs and snapshots are unchanged on the second run

remoteは/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture/github-adapter.jsonを読む/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture/tools/fake-gh.pyだけです。DEV_GRAPH_GHはcontrollerがprivate環境へ固定します。実GitHub/bare ghへ接続せず、同じargsでSkillを2回呼んでください。1回目のimport/export適用、2回目の双方changes=0およびIssue/Projects plannerのconverged=true/unresolved_count=0、stable IDs/snapshots不変を実reportで確認してください。既存canonical external mutation guardをpreview→実UserPromptSubmit reply→authorize→executeの順で通し、receiptを自作しないでください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-sync", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture を同じ入力で 2 回続けて実行する (remote は DEV_GRAPH_GH=/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture/tools/fake-gh.py が読む fixture 内 github-adapter.json だけ)"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C03-OUT1-positive-second-sync-zero-r2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 1200秒/tokens 7000000。poll/verdict両方で強制し延長しない。

## sync固有の既知fixture contractual gate
このcaseは実CLIをfixture root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixtureで起動し、そこでUserPromptSubmit hookを発火させる。preview/authorize/executeの--project-rootは同じ /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture に固定する。別cwdの確認を偽装しない。
remoteはDEV_GRAPH_GH=/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/sync/fixture/tools/fake-gh.pyとfixture内github-adapter.jsonだけ。実GitHubへ接続しない。
正規preview後、challenge/preview_receipt_id/project_rootを /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261102T010423-ci-full/gate-request.jsonへWriteし、assistantでGATE-CHALLENGE: <challenge>を提示して返信を待つ。
controllerは実preview/nonce/対象/digestを検証して、このcaseに事前承認されたCONFIRM EXTERNAL MUTATION <challenge>だけを実UIへ返信する。これはfixture自動入力であり実accountの承認ではない。
実UserPromptSubmit hookが発行したconfirmation receiptだけを利用する。receipt/署名/許可状態の自作・編集やhook-confirm stdin偽装は禁止。新replyのhook出力のcanonical confirmation_receipt_pathをReadしauthorize/executeへ進む。待機中にBash pollingやpreview cancelをしない。scope不一致や未知gateはFAIL。
「途中で人間に質問せず」はこの明示fixture gate待機を除く。実GitHub/Beadsやユーザーtrust/権限を必要としたら迂回せず止める。
