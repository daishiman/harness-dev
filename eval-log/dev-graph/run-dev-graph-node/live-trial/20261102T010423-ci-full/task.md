# タスク: dev-graph:run-dev-graph-node の実走

この run は scenario C02-OUT1-positive-mixed-artifacts-r2 の充足を確認するものです。
1. all five artifacts are routed to canonical kind paths
2. frontmatter kind and stored path agree after a consecutive update
3. no feature is created outside the C14 macro-feature contract

fixtureは試行前に正規build-init-scaffold.py --hook-source pluginで初期化済み。graph revision 0/node 0件から始める。initを再実行しない。mixed-artifacts.jsonは受理済みの5kind(issue/task/specification/architecture/document)入力をbytes不変で移植したもの。全件tracker_binding=none。artifacts[]を書き換えない。
本題1: 下記SkillのaddをR1/R2 preview→R3 canonical writer applyまで実行する。apply用JSONは同じartifacts[]を保ち、preview graph_revision_beforeをexpected_graph_revisionへ入れた別fileとしてfixture内に置く。
本題2: 5nodeすべてへH2 sectionを1つだけ末尾追記するupdates[].append_sections入力を作り、同じSkillを実際にupdate --repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/node/fixture --input <fixture内update JSON>で再度呼びapplyする。graph_node_id/file_pathの不変と本文保全を検証する。
本題3: artifact_kind=featureを含む通常add入力をfixture内に作り、同じSkillをaddで実際にC02へ投入してC14のfail-closed拒否を確かめる。features/が空というだけで代替しない。拒否後C11を確認する。
Skill argsのflagは--repo-root/--inputだけ。preview用--dry-runはSkill内部でwriterに渡す。3本題すべてを実行できた場合だけtask statusをPASSにできる。
graph/content書込はC02単一writerだけ。自作driver/build/検査で代替せず、責務promptを出力前に読み、必要な独立verifierは実Agentを使う。external mutation guard previewは不要なので発行しない。pending guardやUnknown Skillを回避せずFAILで止める。
各Skill内部の監査にも必須順序を適用する。まずmain contextだけで最小成果物/previewを作成し、実path+bytes digestをassistantメッセージで提示する→事前指定済みstandardをcanonical artifact-delivery選択記録へ保存する→ここまで完了してからAgent/独立auditor/semantic evaluatorを起動する。standard事前指定は提示と選択記録の順序を免除しない。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/node/fixture --input /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/node/fixture/mixed-artifacts.json"})

処理が終了 (成功/失敗/中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-node/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts-r2"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・goal-seek証跡はfixture内eval-log等へ保存する。
- 書込は新fixtureと本run証跡dirだけ。source/plugin/settings/trust/PATH/permissions、旧fixture/過去証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、plugin installを行わない。fixture内fake adapterだけを明示する。
- private sandbox/guardを維持する。PATH/ZDOTDIRは継承のまま。未知gate/拒否を回避しない。未登録SkillをReadやscriptで代替しない。
- artifact_deliveryはstandard事前指定だが、必ず実成果物のpath+digest提示→canonical standard記録→独立評価/Agentの順に実行する。
- scenario予算はwall 1200秒/tokens 5000000。poll/verdict両方で強制し延長しない。
