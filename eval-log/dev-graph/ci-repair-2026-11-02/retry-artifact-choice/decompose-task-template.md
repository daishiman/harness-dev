# タスク: dev-graph:run-dev-graph-decompose のfresh再試行候補

この run は scenario decompose-macro-promotion-gate-beads-fixture-standard-v3 の充足を確認するものです。
1. the macro feature+architecture DAG including the existing nodes is acyclic and contains no task-granularity node
2. every new node is a draft preview and no feature is registered directly through a plain C02 add
3. the binding=beads projection preview through C28 bd-bridge.py targets only confirmed/pass/readiness-complete nodes and 0 pre-evaluation draft nodes
4. the original graph digest is unchanged and Beads, GitHub, and Projects writes are 0

## artifact_delivery の二段階のfixture対話

このtaskでは改善深度をまだ選択していません。各Skillのsourceにあるartifact_deliveryの順序に従います。

1. main contextでPurpose & Output Contractの最小実成果物を作り、sourceが許す最小guardだけを実行する。ここではAgent/独立auditor/semantic evaluator/改善loopを開始しない。
2. **assistantの通常本文**に、実在する成果物の絶対path・そのbytesのSHA-256（sha256:付きまたはhex64）・開き方を具体的な実値で提示する。Bash stdoutやReadのtool_resultに実値があるだけでは提示にならない。「提示済み」という自己記録や予定だけでも代替できない。
3. 提示後、{{WORK}}/artifact-choice-request.jsonへ次の待機通知を保存する。これはfixture対話の輸送情報で、承認receiptや達成判定ではない。invocation_idは今回のSkill呼出しごとに一意にする。同じrequestを複数回送信させない。

```json
{"kind":"artifact-delivery-choice","target_skill":"<現在のplugin:skill>","invocation_id":"<このSkill呼出しの一意ID>","artifacts":[{"path":"<提示した実在するFX内の絶対path>","sha256":"<そのbytesのhex64>"}],"state":"waiting_user_choice"}
```

4. assistantの通常本文で「この成果物をaccept-as-is / light / standard / detailedのどれで進めますか」と尋ね、このturnを終えてfixture userの返答を待つ。これは最終DONEではなく中間の現物提示である。out/status.jsonをここで書かない。controllerは提示した本文・現物の一致をread-onlyで確認し、実際の新しいuser turnとして `standard` と返信する。自分でuserの返信を仮定・捏造したり、返信前にstandard選択を保存したりしない。
5. **実際に届いたuserのstandardの後**に、Skill正本に従ってcanonicalな選択記録とsemantic_evaluator_startedへの遷移を記録し、適用される後続のAgent/独立検証・改善を実行する。最初のtaskでstandardが選ばれたと解釈しない。

sourceどおり最小成果物に到達せず拒否/失敗したoperationに、成功artifactやstandard選択を作らない。新しいgateをsourceの全operationへ一律に追加する条件ではない。実際にartifact_presentedへ到達した呼出しだけがこの選択を待つ。


fixtureはaccepted render seedを新Git repoへ移植/rekeyしたもの。ARCH-LT-001、LT-FEATURE-001とexact13 package/registration receiptがある。init不要。graph/content/config/receipt/README/toolsを準備のために書き換えない。

今回適用するMacro flow 1/2はR1-elicit/R2-planの責務で、source frontmatterの両responsibilityはprompt_required:trueである。macro brief/planを生成する前に、ロードした正本skillのprompts/R1-elicit.mdとR2-plan.mdをReadする。他の責務も、その出力を作る前に適用されるpromptを読む。pre-choiceでpromptをReadすることはAgentを早期起動することではない。全責務の不要な実行やdry-runでのsystem-dev-planner起動を新たに要求しない。

まず次のSkillを実際に呼ぶ。最小成果物はmainで作るmacro draftとC02 dry-run previewであり、graph登録結果ではない。draft/previewの実path・bytes digest・開き方を上の二段階対話で提示する。実user standardを受けるまでAgentを起動しない。以後はMacro flowの正規Agent/独立auditorを実行する。

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "graph 実値 render (LT-FEATURE-001) の上に、render 結果を前回の render と比べる差分 feature と、その差分を要約して読み手に示す要約 feature を足す。差分 feature は LT-FEATURE-001 に依存し、要約 feature は差分 feature に依存する。共有の architecture は既存の ARCH-LT-001 を使う。新しい node の tracker_binding は beads。 --repo-root {{FX}} --dry-run"})

Beads投影はC28 bd-bridge.pyのdry-runだけを使い、DEV_GRAPH_BD={{FX}}/tools/fake-bd.pyを指定する。既定bd/実Beadsやfake adapterの直接呼出しで代替しない。新featureはdraft previewだけで、plain C02 addによる直登録をしない。4観測と最初のgraph digest不変・外部writes0を実測し、PARTIALをPASSにしない。

## 終了と制約

全本題が終了（成功/失敗/中断）してから、{{WORK}}/out/status.jsonに完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-promotion-gate-beads-fixture-standard-v3"} と実際の終端状態。最終応答は「DONE: <status>」の1行だけにする。中間のartifact提示や選択待ちは最終応答ではない。

- 途中で人間に質問せず最後まで自走すること。ただし上記の、実成果物提示後の**既知のfixture artifact_delivery選択**だけは例外として実際の返信を待つ。これはsourceの選択gateに対するfixture userの回答であり、人間の新しい判断、外部公開、実サービスmutation、権限/trust変更の承認を意味しない。
- skillの手順に忠実に従い、人手の追加判断・省略をしない。未知gate・分類閾値未達・permission/trust・Unknown Skillをこのstandardで処理せず、必要なら事実を報告して停止する。
- out/にはstatus.json以外を書かない。中間生成物はfixture/eval-log等、上の待機通知はWORK直下へ置く。
- source/plugin/共有runner/設定/trust/PATH/permissions、旧fixture・過去証跡を変更しない。private sandbox/guardを維持し、拒否を迂回しない。
- graph/contentの書込は各Skillが指定するC02単一writerだけ。被験Skillの責務を自作driverや直接script呼出しで代替しない。Skill内部が正本のwriter/validatorを呼ぶことはsourceどおり行う。
- 実在Beads/GitHub/Projectsや外部サービスへ接続・mutationせず、install・公開しない。許されたfixture内fake adapterだけを使う。
- scenarioのrequired_observations・args・予算を変更せず、未実施をPASSにしない。待機時間を含むwall/tokenを同じpoll stateで計測し、延長/resetしない。

scenario上限: wall 1200秒、tokens 5000000。
