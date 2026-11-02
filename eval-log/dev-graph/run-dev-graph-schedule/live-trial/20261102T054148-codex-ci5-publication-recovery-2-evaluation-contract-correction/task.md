# Codex native実走: dev-graph:run-dev-graph-schedule

$dev-graph:run-dev-graph-schedule --repo-root /private/tmp/harness-codex-ci5-20261102/cases/schedule/fx --max-parallel 4

この run は scenario schedule-positive-ready-set-fixture-standard-v2-codex-v1 の充足を確認するものです。
1. every recommended task has all depends_on satisfied (ready)
2. blocked, draft, unconfirmed, evaluation non-pass, and readiness non-complete tasks appear 0 times in the ready-set
3. no resource_scope overlaps inside a parallel batch and the active lease is respected
4. suggested_branch and the worktree claim command are unique per recommended task

## ホスト別の主張
これはCodexのnative $skill適用・native subagent・正規CLI・成果物を観測する試行。ClaudeのSkill tool、Claude Stop hookやplugin hookの動作を証明したとは扱わない。source SKILLの本文を改変せず読み、ホスト呼出し構文だけをnativeへ写す。

## sourceの実Readと書込境界
各native適用の最初に、注入されたSKILL.mdの実在path（初回は /private/tmp/harness-codex-ci5-20261102/providers/plugins/dev-graph/skills/run-dev-graph-schedule/SKILL.md）を、単独catの `tools.exec_command({cmd:"cat <literal absolute SKILL.md>",login:false,max_output_tokens:40000})` で全文Readする。outer execにも冒頭pragma `// @exec: {"max_output_tokens":40000}` を明示する。まとめcat・途中sed・shaだけ・注入本文だけをReadの代わりにしない。login:falseでユーザーstartup出力を混ぜず、内外max40000で全文を途中省略させない。以降のシェルCLIもlogin:falseで呼ぶ。PATH/ZDOTDIR/.zlogin自体は変更しない。必要責務promptも責務の出力前に読むが、無関係な全promptを実行する新条件は課さない。
writer/validatorはこのsourcecopyの正規scriptだけ。native source rootは /private/tmp/harness-codex-ci5-20261102/providers/plugins 内。project .agents/skills はreadonly sourceへのsymlinkで本文を変更しない。actorの書込は /private/tmp/harness-codex-ci5-20261102/cases/schedule/fx と /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20261102T054148-codex-ci5/out/status.json だけ。control/provider/source/旧fixture/旧証跡/userconfig/trust/auth/cache/PATH/HOME/CODEX_HOMEを変更しない。依存CLIごとのPLUGIN_ROOT/CLAUDE_PROJECT_DIRはC24に束縛したrootをprocess環境へ明示する。Pythonは `/usr/bin/arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -B` を明示しPATHを変更しない。

## 実成果物→実選択→独立監査
main contextだけでsource出力契約の最小実成果物を作り、最小guardを通す。実在path・bytes SHA-256・開き方をassistant通常本文で提示し、accept-as-is/light/standard/detailedの四択を尋ねる。tool_resultだけでは提示扱いにしない。
各native invocation/operationのrequest.artifactsに載せる全件について、最終assistant本文にもliteral absolute pathと同一bytes SHA-256を必ず一致提示する。10件なら短い10行表にする。最小usable入口index/manifest1件で選択を求める場合は、request.artifactsもその実在1件に合わせる。他の生成必須成果物を省略せず、入口から各章へ到達できるリンクと正規guardを維持する。manifestへのリンクだけでrequest内の他9件のpath/digestを提示したとは扱わない。
続けて /private/tmp/harness-codex-ci5-20261102/cases/schedule/fx/artifact-choice-request.json へ次の5fieldsだけを書く。
{"kind":"artifact-delivery-choice","state":"waiting_user_choice","target_skill":"<実際のqualified skill>","invocation_id":"<このnative呼出し固有ID>","artifacts":[{"path":"<FX内実在絶対path>","sha256":"<bytes hex64>"}]}
checkpointを書いた後、そのturnの最後のassistant通常本文へ実path・digest・開き方・四択のすべてを載せてturnを終える。tool前コメントだけに置いて最後を「選択待ち」の一言で終えない。最終DONE/out markerはまだ書かない。controllerが本文と現物を照合し、本物の次user turnでstandardを返す。それを受けてからcanonical選択記録を保存し、sourceが要求するnative subagent/auditor/semantic evaluatorを初めて起動する。pre-choiceのAgentは禁止。先に起動してから記録を作って順序を取り繕わない。
これは既知fixture選択だけの対話例外で、人間への追加質問・未知UIgateへの応答・外部mutation承認を許さない。未知gateは停止し具体的に報告する。

## 本題と入力
controllerが起動直前に正規lease CLIでtask-api-usersをclaimする。active leaseを無視したり、graphを書き換えてready-setを作らない。各除外理由・resource_scope・一意branch/claim commandを実reportに保存する。
準備担当からのinputメモ: ready/blocked/draft/unconfirmed/evaluation-non-pass/readiness-non-completeを混ぜた入力です。controllerが起動直前にtask-api-usersのactive leaseを正規CLIで作成します。そのleaseを含めたready-set・resource_scope非重複・一意branch/claim commandを実測してください。入力graphを書き換えてready条件を作らないでください。

## 後続native適用
- 後続の別native適用はない。
各後続操作に到達したら、必要な実入力fileをFX内で用意し、/private/tmp/harness-codex-ci5-20261102/cases/schedule/fx/native-operation-request.jsonへ次を保存してturnを終える。
{"kind":"native-operation","state":"waiting_operation","operation_id":"<上記のid>","target_skill":"<上記qualified target>","args":"<上記のargsをbytes一致で>"}
後続を自分でtoolへ読み替えて完了済みにせず、controllerの実user native適用を待つ。続くnative適用でも冒頭の単独cat全文Read・必要責務prompt・artifact提示/実選択順序を守る。全体の本題を終えるまで中間stageからout marker/DONEを出さない。

## 最終完了マーカー
成功/失敗/中断の最終時だけ、/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-schedule/live-trial/20261102T054148-codex-ci5/out/status.jsonへ {"status":"PASS|FAIL|ERROR","scenario":"schedule-positive-ready-set-fixture-standard-v2-codex-v1"} を1回Writeし、最後に `DONE: <status>` と1行報告する。部分的完了、期待結果の自己申告、未実走をPASSにしない。sourceが求めるgoal/progress/intermediateは各ownerのFX/eval-logへ残す。source正規gateや独立評価を自作driverで代用しない。外部Beads/GitHub/Projects接続・mutation0、plugin install0。予算はwall 1200秒、tokens 5000000。延長・clock resetをしない。
