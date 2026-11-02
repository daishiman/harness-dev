# タスク: dev-graph:run-dev-graph-node のfresh再試行候補

この run は scenario C02-OUT1-positive-mixed-artifacts-r2 の充足を確認するものです。
1. all five artifacts are routed to canonical kind paths
2. frontmatter kind and stored path agree after a consecutive update
3. no feature is created outside the C14 macro-feature contract

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


fixtureは正規C01初期化済みのgraph revision0/node0件から始め、initを再実行しない。mixed-artifacts.jsonの5kind入力はbytes不変、全件tracker_binding=none。artifacts[]を書き換えない。

本題は次の**3つの独立したSkill呼出し**を順に行う。最初のSkillをロードした後に、外側からwriter scriptだけを叩いて2/3を代替しない。各呼出しで適用されるpromptをその責務の出力前に読む。addのR1-classify/R2-previewはsource responsibility_refsとprompt_required:true、およびClassification and write 2/R1・preview規約に接地する。updateで不要な再分類質問など、sourceにない追加条件は課さない。

### 本題1: 5kind add

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root {{FX}} --input {{FX}}/mixed-artifacts.json"})

sourceのR1/R2 preview→R3 canonical writerを実行する。apply用JSONは同じartifacts[]を保ち、previewのgraph_revision_beforeをexpected_graph_revisionへ入れた別fileにする。C02のPurpose & Output Contractの最小実成果物はatomic登録済みtyped nodesとreceiptであり、dry-run previewだけを成功成果物へ代替しない。実登録現物/receiptを上の二段階対話で提示し、実user standard後に正本のbaseline・receipt鎖・独立verifier規約を守って後続処理を行う。pre-choice commitをpost-choice writer_receiptsへ加えず、baselineを後から取り直さない。

### 本題2: consecutive update（新しいSkill呼出し）

本題1完了後、5node全てのgraph_node_idを保持し、末尾へH2を1つだけ追記するupdates[].append_sections入力を{{FX}}/eval-log/inputs/consecutive-update.jsonへ作る。graph/contentは直接編集しない。

Skill({skill: "dev-graph:run-dev-graph-node", args: "update --repo-root {{FX}} --input {{FX}}/eval-log/inputs/consecutive-update.json"})

このSkill自身が正規preview/CAS/applyを実行する。id/path/kindと既存本文の保全を検証する。sourceのartifact_presentedへ到達したら、このupdate呼出しの現物を改めて提示し、新しいinvocation_idで実user standardを待つ。初回addへの選択をupdateの選択として流用しない。

### 本題3: 通常feature-add拒否（新しいSkill呼出し）

macro contractを持たないartifact_kind=featureの通常add入力を{{FX}}/eval-log/inputs/plain-feature-add.jsonへ作る。C14 macroを付けて成功する入力へ変更しない。

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root {{FX}} --input {{FX}}/eval-log/inputs/plain-feature-add.json"})

Skill内の正規C02経路でfeature_requires_c14_macro_contract等のfail-closed拒否とwrite0を実測する。features/が空という結果だけでは代替しない。sourceどおりpreview段階で拒否されたなら、無理にapplyやstandard評価へ進まず拒否をそのまま保存する。拒否後のC11とgraph不変を確認する。これはscenarioが求める負例であり、拒否を成功登録や評価PASSに偽装しない。

3つの実Skill呼出しと各本題の実結果が揃ったときだけtrial全体のtask statusをPASSにできる。独立のgoal評価は後でfresh evaluatorが判定する。

## 終了と制約

全本題が終了（成功/失敗/中断）してから、{{WORK}}/out/status.jsonに完了マーカーを1ファイルだけWriteする。内容は {"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts-r2"} と実際の終端状態。最終応答は「DONE: <status>」の1行だけにする。中間のartifact提示や選択待ちは最終応答ではない。

- 途中で人間に質問せず最後まで自走すること。ただし上記の、実成果物提示後の**既知のfixture artifact_delivery選択**だけは例外として実際の返信を待つ。これはsourceの選択gateに対するfixture userの回答であり、人間の新しい判断、外部公開、実サービスmutation、権限/trust変更の承認を意味しない。
- skillの手順に忠実に従い、人手の追加判断・省略をしない。未知gate・分類閾値未達・permission/trust・Unknown Skillをこのstandardで処理せず、必要なら事実を報告して停止する。
- out/にはstatus.json以外を書かない。中間生成物はfixture/eval-log等、上の待機通知はWORK直下へ置く。
- source/plugin/共有runner/設定/trust/PATH/permissions、旧fixture・過去証跡を変更しない。private sandbox/guardを維持し、拒否を迂回しない。
- graph/contentの書込は各Skillが指定するC02単一writerだけ。被験Skillの責務を自作driverや直接script呼出しで代替しない。Skill内部が正本のwriter/validatorを呼ぶことはsourceどおり行う。
- 実在Beads/GitHub/Projectsや外部サービスへ接続・mutationせず、install・公開しない。許されたfixture内fake adapterだけを使う。
- scenarioのrequired_observations・args・予算を変更せず、未実施をPASSにしない。待機時間を含むwall/tokenを同じpoll stateで計測し、延長/resetしない。

scenario上限: wall 1200秒、tokens 5000000。
