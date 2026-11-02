# 再開用：実成果物の提示とfixture user選択

現状は週次上限によるBLOCKED。追加liveを起動しない。本資料は未実行の再開案であり、今回のPASS、承認、再実走の証拠ではない。source、旧FAIL、旧runのtask/receiptを変更しない。

## taskへの適用

decompose-task-template.mdとnode-task-template.mdの`{{FX}}`/`{{WORK}}`を、新しい隔離fixtureと新しいrun証跡dirへ展開する。元のscenario_id・required_observations・Skill argsの意味・予算を保つ。C14は全体3回目、C02は2回目という親指定の反復履歴を引き継ぎ、追加の自動再試行を予約しない。

未起動のrequirements/schedule/status/syncにもcommon-choice-task-fragment.mdを使える。既存taskにある「standard事前指定」「追加質問不要」の該当文を二段階対話へ**置換**し、矛盾する両方の指示を残さない。各scenario固有の観測・入力・literal Skill呼出しはそのまま保持する。syncのexternal mutation challengeと本選択は別kindとして識別する。

## 二段階の順序

1. 被験assistantがsourceどおりmainで最小実成果物を作る。C02の成功add/updateでは登録現物＋revision/digest receiptが出力契約であり、previewだけを代用しない。C14 dry-runの現物はmacro draftとC02 previewである。
2. assistantの通常本文で現物path・bytes SHA-256・開き方を提示する。tool_resultや自己申告JSONは本文提示の代わりにならない。
3. 被験側はWORK直下のartifact-choice-request.jsonへ待機通知を書き、通常assistant本文で四択を尋ねてturnを終える。out/status.jsonや最終DONEを書かない。requestには承認済み・評価PASS・canonical receiptを含めない。
4. controllerが下のread-only確認を満たしたときだけ、本物のfixture userの新しいturnとして`standard`を送る。
5. 被験assistantが実際のuser返答を受けてからsourceのcanonical選択記録を保存し、初めて後続Agent/独立検証を開始する。controllerは選択記録を書かず、状態遷移や達成を代行しない。

## checkpointの形

```json
{"kind":"artifact-delivery-choice","target_skill":"dev-graph:run-dev-graph-node","invocation_id":"c02-add-1","artifacts":[{"path":"<FX内の実在する絶対path>","sha256":"<bytesのhex64>"}],"state":"waiting_user_choice"}
```

invocation_idはSkill呼出しごとに一意。C02 updateはaddとは別idにする。statusの正規準備init/nodeなど、nested Skillがsource上この選択へ到達した場合も対象を区別する。失敗/拒否でartifact_presentedに到達しないoperationに、無理にrequestやstandard選択を作らない。通常feature-add拒否も必ず新しいSkill呼出しで実行するが、期待された拒否を成功artifactに変えない。

## controllerのread-only precondition

- source/loaded closure pin、session UUID、owner PID、fixture realpathが既存manifest/stateと一致している。
- requestは上のkind/stateで、target_skillはこのtrialの実際のSkill呼出しに対応する現行loaded providerのもの。正本にartifact_deliveryの提示→選択→semantic_evaluator_startedが宣言されている。
- request idは未応答で、保存したrequestのSHAとinvocation idを記録できる。以前のturn/別Skillのrequestを再利用しない。
- canonical live-trial-status.pyによる**IDLE_TURN_COMPLETEかつpending=[]**を確認する。最新の実user promptより後の現在のturnのassistant text blockに、requestに列挙した実path・digest・開き方・深度選択を尋ねる本文が存在する。過去全turnから同じ文字列を拾って成立扱いにしない。
- 各pathはFX内の実在する通常fileで、symlinkの解決先もFX内。読み直したbytes SHA-256がrequestとassistant本文の両方に一致する。検査後に変わったら再確認し、未確認のまま送信しない。
- source契約に反するpre-choice Agentが既に始まっていれば、返信して帳尻を合わせない。今回の提示がまだ無い、本文と実物が違う、通常の質問、分類の確認、trust/permissionのUI、未知gateには自動返信しない。

checkpointの書込みだけをprecondition充足と見なさない。これらは送信先と既存sourceの順序を確かめる観測であり、新しいgoal評価やartifact品質PASSではない。

## canonical送信と実測証跡

既存backendの`send_line(session, 'standard')`（CLIなら`live-trial-backend.py send-line SESSION standard`）を使用する。これは短い固定gate応答の既存例外であり、権限UIへのキー操作ではない。tool_result、UserPromptSubmit payload、approval/署名/confirmation receiptを自作して返答を偽装しない。

送信前後のtranscriptを回収し、実際のuser eventに`standard`が記録され、assistant現物提示より後に到達したことを確認する。controllerはrequest SHA・invocation id・target skill・session UUID・assistant提示event識別子・各artifact path/SHA・送信時刻・実user event識別子を実測ログへappendする。送信未確認や送信errorは応答成功として数えず、未達として残す。同じrequestへ二重送信しない。

既存のcontractual-gates.jsonにkindごとの実送信履歴を保持し、finalizerへ実際のgate-response-countとgate-kind=contractualを渡す。main targetはいずれもallowed-toolsにAskUserQuestionを宣言しており、正規verdictのgate_contract_evidence検査を通す。回数を予定値で埋めず、単なる救済nudgeをcontractualに付け替えない。proof trialならgate応答によるFAIL規則もそのまま維持する。

通常本文の選択待ちはcanonical status上ではIDLEであり、AskUserQuestion/ExitPlanModeがpendingのGATEとは異なる。既存runnerのsync既知gate検査と同じく、**既知requestのprecondition検査をpollの前/短いtick間に行う**。一般のSTALLを選択gateとして再分類したり、既存STALLを無かったことにしたりしない。既にSTALLへ到達したら既存規則の状態を保持し、手動でPASSへ回復させない。

AskUserQuestionが実際にpendingになった場合は、通常入力欄へのsend-lineをそのTUIに流用しない。そのtoolの問い・選択肢・UIを別途確認し、未知UIのキー操作を推測しない。本候補はsourceが特定toolを要求しないartifact深度選択を、通常assistant本文→実user turnで行う形である。

## C02複数呼出しと証跡保持

transcriptの実Skill呼出しはadd→update→通常feature-addの3回必要。writerの連続呼出しだけでは満たさない。各成功呼出しの現物提示・実user選択・後続Agentは、そのinvocationに結び付ける。canonical goal/progress/intermediateが次のSkill呼出しで更新される場合、controllerは次の呼出し前の実ファイルをread-onlyで別名保存して履歴を保持できる。値を修正したり現在のcanonical fileへ書き戻したりしない。

## source根拠と限界

- C14 SKILL.md:99-123、C02 SKILL.md:74-98：artifact_delivery状態機械とpre/post-choice契約。
- C02 SKILL.md:107付近：atomic登録されたtyped node/packageとrevision/digest receiptという出力契約。pre-choice receipt/baselineの規約も保持する。
- C14 SKILL.md:25-31のprompt_required:true、Macro flow1/2、prompts/R1-elicit.mdのmacro brief出力契約、R2-plan.mdのmacro計画出力契約：今回適用するR1/R2を、その責務の出力前にReadする根拠。pre-choice Readを禁止されたforkと混同しない。
- C02 responsibility_refs/prompt_required、Classification and write、R1-classify/R2-preview：適用される分類・previewの事前Read。全prompt/不要責務を無条件で実行する新条件は付けない。
- live-trial task-template.md：no-human、終了後の最終DONE、outにはstatusだけ。今回の既知fixture選択だけを明示例外にし、最終DONEと中間提示を区別する。
- live-trial SKILL.md:307-315：contractual/rescueの区別、frontmatterによる接地、proofの例外。source/verdictは変更しない。

候補の成立は実走で未確認。fresh evaluatorが新transcriptを独立に判定するまでPASSではない。旧FAILとそのhashは保持する。追加起動は親/controllerの再開判断後だけとし、週次上限・予算・反復上限を回避しない。
