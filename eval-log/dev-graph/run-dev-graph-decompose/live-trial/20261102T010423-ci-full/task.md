# タスク: dev-graph:run-dev-graph-decompose の実走

この run は scenario decompose-macro-promotion-gate-beads-fixture-standard-v3 の充足を確認するものです。
1. the macro feature+architecture DAG including the existing nodes is acyclic and contains no task-granularity node
2. every new node is a draft preview and no feature is registered directly through a plain C02 add
3. the binding=beads projection preview through C28 bd-bridge.py targets only confirmed/pass/readiness-complete nodes and 0 pre-evaluation draft nodes
4. the original graph digest is unchanged and Beads, GitHub, and Projects writes are 0

fixtureはaccepted render seedを新しいrepoへ移植しrekeyしたもの。ARCH-LT-001、LT-FEATURE-001とexact-13 package/registration receiptがある。init不要。最初にC11を確認する。graph/content/config/receipt/README/toolsは準備のために書き換えない。
Beadsへの投影はC28 bd-bridge.pyのdry-runだけを使い、その呼出しには必ず DEV_GRAPH_BD=/Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/decompose/fixture/tools/fake-bd.py を付ける。既定bdや実Beadsを呼ばず、fake adapterを直接呼んでprojectionに代えない。fake adapterの呼出し記録はfixture/fake-bd-calls.jsonlに残る。
featureの適用/previewはC02単一writerを通し、plain addで直登録しない。Macro flowの独立auditorはAgent toolで実際に呼び出す。責務promptは出力前に読む。自作driver/build/検査コードでskillやauditorを代替しない。PARTIALをPASSにしない。

## 必須の実行順序（Skill内部の監査にも適用）

standardはこの隔離試行について事前指定済み。追加の人間への質問は不要だが、以下の順序は省略しない。

1. 下記のSkillを呼び、まずmain contextだけで最小のmacro draftとC02 dry-run previewをfixture内に作る。この段階でAgent・独立監査・semantic evaluatorを起動しない。
2. 実在する最小成果物のpathとbytesのdigestを、assistantメッセージで提示する。
3. この試行で事前指定したstandardをcanonical artifact-delivery選択記録へ保存し、次の評価段階へ遷移したことを確認する。
4. ここまで終えてから、SkillのMacro flowに従って独立auditor/Agentと後続検証を実行する。

Agent起動前にpath+digest提示と選択記録が揃わなければ、順序を飛ばして進まずFAILとして終了する。最終状態が合っていても必須順序の違反をPASSにしない。実repo/外部accountへの承認ではない。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "graph 実値 render (LT-FEATURE-001) の上に、render 結果を前回の render と比べる差分 feature と、その差分を要約して読み手に示す要約 feature を足す。差分 feature は LT-FEATURE-001 に依存し、要約 feature は差分 feature に依存する。共有の architecture は既存の ARCH-LT-001 を使う。新しい node の tracker_binding は beads。 --repo-root /Users/dm/dev/dev/個人開発/harness/.build/ci-full/20261102T010423-ci-full/decompose/fixture --dry-run"})

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:
1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20261102T010423-ci-full/out/status.json に完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-promotion-gate-beads-fixture-standard-v3"} と実際の終端状態を記録する。
2. 「DONE: <status>」と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/にはstatus.json以外を書かない。中間成果物・検証結果・goal-seek証跡はfixture内へ保存する。
- 書込先はこの新fixtureと本runの証跡dirだけ。root/source/plugin/settings/trust/PATH/permissions、旧fixture、旧公開証跡を変更しない。
- 実在Beads/GitHub/Projectsや外部サービスへの接続・mutation、外部公開、pluginのinstallを行わない。
- 未登録SkillをReadや直接script実行で代替しない。Unknown skillはFAILで終了する。Skillのロードだけを実行済みと見なさず、ロードされた手順のcanonical writer/validator/Agentを実行する。
- private project settingsのsandbox/PreToolUse guardを維持する。書込許可は新fixtureと新workdirだけ、外部サービスtool/CLIは拒否される。PATH/ZDOTDIRは変更されていない。拒否やgateを回避しない。
- scenario予算はwall 1200秒、tokens 5000000。pollとverdictの両方で同じscenario契約を強制し、延長しない。
