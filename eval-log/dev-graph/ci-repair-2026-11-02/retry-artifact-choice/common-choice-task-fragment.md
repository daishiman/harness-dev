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
