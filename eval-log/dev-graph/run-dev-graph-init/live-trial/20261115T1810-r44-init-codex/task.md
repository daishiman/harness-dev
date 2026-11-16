# Codex native実走: dev-graph:run-dev-graph-init

$dev-graph:run-dev-graph-init --repo-root /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-init/fx --hook-source plugin

この run は scenario C01-OUT1-positive-idempotence-fixture-standard-v2-codex-v1 の充足を確認するものです (RUN_ID 20261115T1810-r44-init-codex)。
1. after the first init the six content roots, the routing policy, and the graph store exist and the initial graph passes C11
2. a second init with the same arguments plans 0 changes and preserves user edits
3. the repo config stores no absolute path, token, or node ID and the plugin hook source is used

## ホスト別の主張
これはCodexのnative $skill適用・native subagent・正規CLI・成果物を観測する試行。ClaudeのSkill tool、Claude Stop hookやplugin hookの動作を証明したとは扱わない。source SKILLの本文を改変せず読み、ホスト呼出し構文だけをnativeへ写す。

## sourceの実Readと書込境界
各native適用の最初に、注入されたSKILL.mdの実在path（初回は /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/providers/plugins/dev-graph/skills/run-dev-graph-init/SKILL.md）を、単独catの `tools.exec_command({cmd:"cat <literal absolute SKILL.md>",login:false,max_output_tokens:40000})` で全文Readする。outer execにも冒頭pragma `// @exec: {"max_output_tokens":40000}` を明示する。まとめcat・途中sed・shaだけ・注入本文だけをReadの代わりにしない。login:falseでユーザーstartup出力を混ぜず、内外max40000で全文を途中省略させない。以降のシェルCLIもlogin:falseで呼ぶ。PATH/ZDOTDIR/.zlogin自体は変更しない。必要責務promptも責務の出力前に読むが、無関係な全promptを実行する新条件は課さない。
writer/validatorはこのsourcecopyの正規scriptだけ。native source rootは /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/providers/plugins 内。project .agents/skills はreadonly sourceへのsymlinkで本文を変更しない。actorの書込は /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-init/fx と /Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-init/live-trial/20261115T1810-r44-init-codex/out/status.json だけ。control/provider/source/旧fixture/旧証跡/userconfig/trust/auth/cache/PATH/HOME/CODEX_HOMEを変更しない。依存CLIごとのPLUGIN_ROOT/CLAUDE_PROJECT_DIRはC24に束縛したrootをprocess環境へ明示する。Pythonは `/usr/bin/arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -B` を明示しPATHを変更しない。

## 実成果物→実選択→独立監査
main contextだけでsource出力契約の最小実成果物を作り、最小guardを通す。実在path・bytes SHA-256・開き方をassistant通常本文で提示し、accept-as-is/diagnoseの二択（現状で試すか、診断するか）を尋ねる。tool_resultだけでは提示扱いにしない。
続けて /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-init/fx/artifact-choice-request.json へ次の5fieldsだけを書く。
{"kind":"artifact-delivery-choice","state":"waiting_user_choice","target_skill":"<実際のqualified skill>","invocation_id":"<このnative呼出し固有ID>","artifacts":[{"path":"<FX内実在絶対path>","sha256":"<bytes hex64>"}]}
checkpointを書いた後、そのturnの最後のassistant通常本文へ実path・digest・開き方・二択（accept-as-is / diagnose）のすべてを載せてturnを終える。tool前コメントだけに置いて最後を「選択待ち」の一言で終えない。最終DONE/out markerはまだ書かない。controllerが本文と現物を照合し、本物の次user turnでdiagnoseを返す。それを受けてからcanonical選択記録を保存し、sourceが要求するnative subagent/auditor/semantic evaluatorを初めて起動する。pre-choiceのAgentは禁止。先に起動してから記録を作って順序を取り繕わない。
診断の所見を示した後に、artifact_delivery の改善の段で改善の深さを選ぶことになったら、この task が事前に指定した `standard` を使う。深さは改善の段でだけ使い、初回の選択 (accept-as-is / diagnose) の記録には書かない。深さの質問で turn を終えない。
これは既知fixture選択だけの対話例外で、人間への追加質問・未知UIgateへの応答・外部mutation承認を許さない。未知gateは停止し具体的に報告する。

## 本題と入力
入力はREADMEを1件commitしたplain Gitのみでdev-graph state無し。初回native initで6 content roots/routing policy/graph storeを作りC11を検証する。利用者READMEへ無害な追記をして初回後bytesを保存し、native-operation-requestで同じargsのinit-secondを本当にnative再適用する。2回目の計画0changesとREADME追記保全を実測する。repo configに絶対path/token/node IDが無く、hook source指定pluginが保存されることを確認する。これはplugin source選択/configの観測で、Claude Stop/実native hook配達の証明ではない。
準備担当からのinputメモ: 

## 後続native適用
- `init-second`: target=`dev-graph:run-dev-graph-init` args=`--repo-root /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-init/fx --hook-source plugin`
各後続操作に到達したら、必要な実入力fileをFX内で用意し、/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-init/fx/native-operation-request.jsonへ次を保存してturnを終える。
{"kind":"native-operation","state":"waiting_operation","operation_id":"<上記のid>","target_skill":"<上記qualified target>","args":"<上記のargsをbytes一致で>"}
後続を自分でtoolへ読み替えて完了済みにせず、controllerの実user native適用を待つ。続くnative適用でも冒頭の単独cat全文Read・必要責務prompt・artifact提示/実選択順序を守る。全体の本題を終えるまで中間stageからout marker/DONEを出さない。

## 最終完了マーカー
成功/失敗/中断の最終時だけ、/Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-init/live-trial/20261115T1810-r44-init-codex/out/status.jsonへ {"status":"PASS|FAIL|ERROR","scenario":"C01-OUT1-positive-idempotence-fixture-standard-v2-codex-v1"} を1回Writeし、最後に `DONE: <status>` と1行報告する。部分的完了、期待結果の自己申告、未実走をPASSにしない。sourceが求めるgoal/progress/intermediateは各ownerのFX/eval-logへ残す。source正規gateや独立評価を自作driverで代用しない。外部（本物のBeads/GitHub/Projects/Notion）への接続・書き込みは0、plugin installは0。予算はwall 900秒、tokens 4000000。延長・clock resetをしない。
