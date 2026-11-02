# タスク: dev-graph:run-dev-graph-init の実走

この run は scenario C01-OUT1-positive-idempotence-fixture-standard-v2 の充足を確認するものです。
1. after the first init the six content roots, the routing policy, and the graph store exist and the initial graph passes C11
2. a second init with the same arguments plans 0 changes and preserves user edits
3. the repo config stores no absolute path, token, or node ID and the plugin hook source is used

同じ引数でinitを2回実行する。初回の6 content roots・routing policy・graph storeとC11を確認後、fixture内の利用者用READMEに無害な追記をして保存し、2回目の計画が0 changesかつ追記が保全されることを証跡化する。初期fixtureはREADMEを1件commitしたplain git repoでdev-graph stateは無い。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-fix-live/20261102T000242-ci-fix2/init/fixture --hook-source plugin"})

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-init/live-trial/20261102T000242-ci-fix2/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C01-OUT1-positive-idempotence-fixture-standard-v2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・検証結果・goal-seek証跡はfixture内へ保存する。
- 書込先はこの新fixtureと本runの証跡dirだけ。root/source/plugin/settings/trust/PATH/permissions、旧fixture、旧公開証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、pluginのinstallを行わない。
- 未登録SkillをReadや直接script実行で代替しない。Unknown skillはFAILで終了する。Skillのロードだけを実行済みと見なさず、ロードされた手順のcanonical writer/validator/Agentを実行する。
- artifact_deliveryはstandardを事前指定する。fixture内成果物を提示してからこの指定を記録し後続検証へ進む。実repoや外部accountの承認を意味しない。
- private project settingsのsandbox/PreToolUse guardを維持する。書込許可は新fixtureと新workdirだけ、外部サービスtool/CLIは拒否される。PATH/ZDOTDIRは変更されていない。拒否やgateを回避しない。
- scenario予算はwall 900秒、tokens 4000000。pollとverdictの両方で同じscenario契約を強制し、延長しない。
