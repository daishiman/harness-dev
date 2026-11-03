# Codex native実走: dev-graph:run-dev-graph-decompose

$dev-graph:run-dev-graph-decompose graph 実値 render (LT-FEATURE-001) の上に、render 結果を前回の render と比べる差分 feature と、その差分を要約して読み手に示す要約 feature を足す。差分 feature は LT-FEATURE-001 に依存し、要約 feature は差分 feature に依存する。共有の architecture は既存の ARCH-LT-001 を使う。新しい node の tracker_binding は beads。 --repo-root /private/tmp/harness-pr89-codex-20261104/cases/decompose/fx --dry-run

この run は scenario decompose-macro-promotion-gate-beads-fixture-standard-v3-codex-v1 の充足を確認するものです。
1. the macro feature+architecture DAG including the existing nodes is acyclic and contains no task-granularity node
2. every new node is a draft preview and no feature is registered directly through a plain C02 add
3. the binding=beads projection preview through C28 bd-bridge.py targets only confirmed/pass/readiness-complete nodes and 0 pre-evaluation draft nodes
4. the original graph digest is unchanged and Beads, GitHub, and Projects writes are 0

## ホスト別の主張
これはCodexのnative $skill適用・native subagent・正規CLI・成果物を観測する試行。ClaudeのSkill tool、Claude Stop hookやplugin hookの動作を証明したとは扱わない。source SKILLの本文を改変せず読み、ホスト呼出し構文だけをnativeへ写す。

## sourceの実Readと書込境界
各native適用の最初に、注入されたSKILL.mdの実在path（初回は /private/tmp/harness-pr89-codex-20261104/providers/plugins/dev-graph/skills/run-dev-graph-decompose/SKILL.md）を、単独catの `tools.exec_command({cmd:"cat <literal absolute SKILL.md>",login:false,max_output_tokens:40000})` で全文Readする。outer execにも冒頭pragma `// @exec: {"max_output_tokens":40000}` を明示する。まとめcat・途中sed・shaだけ・注入本文だけをReadの代わりにしない。login:falseでユーザーstartup出力を混ぜず、内外max40000で全文を途中省略させない。以降のシェルCLIもlogin:falseで呼ぶ。PATH/ZDOTDIR/.zlogin自体は変更しない。必要責務promptも責務の出力前に読むが、無関係な全promptを実行する新条件は課さない。
writer/validatorはこのsourcecopyの正規scriptだけ。native source rootは /private/tmp/harness-pr89-codex-20261104/providers/plugins 内。project .agents/skills はreadonly sourceへのsymlinkで本文を変更しない。actorの書込は /private/tmp/harness-pr89-codex-20261104/cases/decompose/fx と /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20261104T061800-pr89-decompose/out/status.json だけ。control/provider/source/旧fixture/旧証跡/userconfig/trust/auth/cache/PATH/HOME/CODEX_HOMEを変更しない。依存CLIごとのPLUGIN_ROOT/CLAUDE_PROJECT_DIRはC24に束縛したrootをprocess環境へ明示する。Pythonは `/usr/bin/arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -B` を明示しPATHを変更しない。

## 実成果物→実選択→独立監査
main contextだけでsource出力契約の最小実成果物を作り、最小guardを通す。実在path・bytes SHA-256・開き方をassistant通常本文で提示し、accept-as-is/light/standard/detailedの四択を尋ねる。tool_resultだけでは提示扱いにしない。
続けて /private/tmp/harness-pr89-codex-20261104/cases/decompose/fx/artifact-choice-request.json へ次の5fieldsだけを書く。
{"kind":"artifact-delivery-choice","state":"waiting_user_choice","target_skill":"<実際のqualified skill>","invocation_id":"<このnative呼出し固有ID>","artifacts":[{"path":"<FX内実在絶対path>","sha256":"<bytes hex64>"}]}
checkpointを書いた後、そのturnの最後のassistant通常本文へ実path・digest・開き方・四択のすべてを載せてturnを終える。tool前コメントだけに置いて最後を「選択待ち」の一言で終えない。最終DONE/out markerはまだ書かない。controllerが本文と現物を照合し、本物の次user turnでstandardを返す。それを受けてからcanonical選択記録を保存し、sourceが要求するnative subagent/auditor/semantic evaluatorを初めて起動する。pre-choiceのAgentは禁止。先に起動してから記録を作って順序を取り繕わない。
これは既知fixture選択だけの対話例外で、人間への追加質問・未知UIgateへの応答・外部mutation承認を許さない。未知gateは停止し具体的に報告する。

## 本題と入力
既存ARCH-LT-001/LT-FEATURE-001とexact-13 packageは入力。自然文をmacro feature2件だけへ分解し、tasks粒度へ落とさない。R1-elicit/R2-plan/R3-decompose/R6-dryrunの適用責務promptを出力前に読む。
C02単一writerのdry-run previewとC28 bd-bridge.py --op create --dry-run --planned-previewで実投影previewを作る。各C28 CLIへ必ず DEV_GRAPH_BD=/private/tmp/harness-pr89-codex-20261104/cases/decompose/fx/tools/fake-bd.py を明示し、default bdやfakeを直接呼ぶ抜け道を使わない。既存graph/content/receiptは不変。Agentによる独立DAG監査は実artifact提示と実standard応答の後だけ。
準備担当からのinputメモ: render seedをrekeyして移植したmacro入力。beads mode/fake-bdは準備条件のみ。

## 後続native適用
- 後続の別native適用はない。
各後続操作に到達したら、必要な実入力fileをFX内で用意し、/private/tmp/harness-pr89-codex-20261104/cases/decompose/fx/native-operation-request.jsonへ次を保存してturnを終える。
{"kind":"native-operation","state":"waiting_operation","operation_id":"<上記のid>","target_skill":"<上記qualified target>","args":"<上記のargsをbytes一致で>"}
後続を自分でtoolへ読み替えて完了済みにせず、controllerの実user native適用を待つ。続くnative適用でも冒頭の単独cat全文Read・必要責務prompt・artifact提示/実選択順序を守る。全体の本題を終えるまで中間stageからout marker/DONEを出さない。

## 最終完了マーカー
成功/失敗/中断の最終時だけ、/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-decompose/live-trial/20261104T061800-pr89-decompose/out/status.jsonへ {"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-promotion-gate-beads-fixture-standard-v3-codex-v1"} を1回Writeし、最後に `DONE: <status>` と1行報告する。部分的完了、期待結果の自己申告、未実走をPASSにしない。sourceが求めるgoal/progress/intermediateは各ownerのFX/eval-logへ残す。source正規gateや独立評価を自作driverで代用しない。外部Beads/GitHub/Projects接続・mutation0、plugin install0。予算はwall 1200秒、tokens 5000000。延長・clock resetをしない。
