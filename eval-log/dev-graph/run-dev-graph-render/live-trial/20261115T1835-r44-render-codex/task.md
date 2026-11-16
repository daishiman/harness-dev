# Codex native実走: dev-graph:run-dev-graph-render

$dev-graph:run-dev-graph-render --repo-root /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx --output /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/.dev-graph/render/index.html

この run は scenario render-feature-progress-receipt-positive-fixture-standard-v3-codex-v1 の充足を確認するものです。
1. the generated HTML has zero external resource references and draws features, tasks, and edges as inline SVG
2. LT-FEATURE-001 progress X/Y matches the graph, Y equals the registration receipt expected_count, and the child task set equals the receipt node_ids
3. the render is invoked with the registration receipt and its target corresponds to the receipt source_digest
4. two consecutive renders produce identical output digests

## ホスト別の主張
これはCodexのnative $skill適用・native subagent・正規CLI・成果物を観測する試行。ClaudeのSkill tool、Claude Stop hookやplugin hookの動作を証明したとは扱わない。source SKILLの本文を改変せず読み、ホスト呼出し構文だけをnativeへ写す。

## sourceの実Readと書込境界
各native適用の最初に、注入されたSKILL.mdの実在path（初回は /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/providers/plugins/dev-graph/skills/run-dev-graph-render/SKILL.md）を、単独catの `tools.exec_command({cmd:"cat <literal absolute SKILL.md>",login:false,max_output_tokens:40000})` で全文Readする。outer execにも冒頭pragma `// @exec: {"max_output_tokens":40000}` を明示する。まとめcat・途中sed・shaだけ・注入本文だけをReadの代わりにしない。login:falseでユーザーstartup出力を混ぜず、内外max40000で全文を途中省略させない。以降のシェルCLIもlogin:falseで呼ぶ。PATH/ZDOTDIR/.zlogin自体は変更しない。必要責務promptも責務の出力前に読むが、無関係な全promptを実行する新条件は課さない。
writer/validatorはこのsourcecopyの正規scriptだけ。native source rootは /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/providers/plugins 内。project .agents/skills はreadonly sourceへのsymlinkで本文を変更しない。actorの書込は /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx と /Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-render/live-trial/20261115T1835-r44-render-codex/out/status.json だけ。control/provider/source/旧fixture/旧証跡/userconfig/trust/auth/cache/PATH/HOME/CODEX_HOMEを変更しない。依存CLIごとのPLUGIN_ROOT/CLAUDE_PROJECT_DIRはC24に束縛したrootをprocess環境へ明示する。Pythonは `/usr/bin/arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -B` を明示しPATHを変更しない。

## 実成果物→実選択→独立監査
main contextだけでsource出力契約の最小実成果物を作り、最小guardを通す。実在path・bytes SHA-256・開き方をassistant通常本文で提示し、現状のまま受け取る accept-as-is か、診断する diagnose かの二択を尋ねる。tool_resultだけでは提示扱いにしない。
続けて /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/artifact-choice-request.json へ次の5fieldsだけを書く。
{"kind":"artifact-delivery-choice","state":"waiting_user_choice","target_skill":"<実際のqualified skill>","invocation_id":"<このnative呼出し固有ID>","artifacts":[{"path":"<FX内実在絶対path>","sha256":"<bytes hex64>"}]}
checkpointを書いた後、そのturnの最後のassistant通常本文へ実path・digest・開き方・二択（accept-as-is / diagnose）のすべてを載せてturnを終える。tool前コメントだけに置いて最後を「選択待ち」の一言で終えない。最終DONE/out markerはまだ書かない。controllerが本文と現物を照合し、本物の次user turnでdiagnoseを返す。それを受けてからcanonical選択記録を保存し、sourceが要求するnative subagent/auditor/semantic evaluatorを初めて起動する。pre-choiceのAgentは禁止。先に起動してから記録を作って順序を取り繕わない。
診断の所見を示した後に、artifact_delivery の改善の段で改善の深さを選ぶことになったら、この task が事前に指定した `standard` を使う。深さは改善の段でだけ使い、初回の選択 (accept-as-is / diagnose) の記録には書かない。深さの質問で turn を終えない。
これは既知fixture選択だけの対話例外で、人間への追加質問・未知UIgateへの応答・外部mutation承認を許さない。未知gateは停止し具体的に報告する。

## 本題と入力
registration receiptを実renderの--receiptに渡し、source_digest/子task集合/expected_countとHTMLを照合する。異なる出力pathへの正規renderを2回実行しbyte digest一致を観測する。旧HTMLは入力に含まれていない。
このrunのブラウザ前提は事前に非LLMで起動確認済みの既存 `/Users/dm/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell` （bytes SHA-256は /Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-render/live-trial/20261115T1835-r44-render-codex/controller-fixture-provenance.json のbrowser_runtime参照）だけを利用する。追加インストール/ネットワークDLをしない。ブラウザ起動は `--single-process --headless=new --no-sandbox --disable-background-networking --disable-component-update --no-first-run --disable-crash-reporter --disable-breakpad --user-data-dir=/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/.native-tmp/browser-profile --dump-dom --screenshot=/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/eval-log/render-browser.png --window-size=1400,1000 file://<今回の実render HTML絶対path>` を使う。これはブラウザのプロセス構成で、Codex workspace-write/ネットワーク遮断/書込範囲はそのまま。コマンド環境のMAC_CHROMIUM_TMPDIRだけ `/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/.native-tmp` へ指定し、driver既定のTMPDIR/TMPPREFIXを保つ。AF_UNIX許可追加やouter sandbox解除をしない。DOMと実screenshotのSVG/進捗X/Yを確認し、起動・表示未達を静的検査でPASSにしない。
準備担当からのinputメモ: LT-FEATURE-001と一部doneのexact-13子taskを持つ入力fixtureです。registration receiptは/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/.dev-graph/state/package-registration-receipt-LT-FEATURE-001.json。render-graph-html.pyには必ず--receiptで渡してください。子task集合/node_ids、Y=expected_count、source_digestへの対応を実際に照合し、2回描画のdigest一致と外部resource参照0を確認してください。過去のrender出力はseedから除外済みです。

## 後続native適用
- 後続の別native適用はない。
各後続操作に到達したら、必要な実入力fileをFX内で用意し、/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/codex/cases/run-dev-graph-render/fx/native-operation-request.jsonへ次を保存してturnを終える。
{"kind":"native-operation","state":"waiting_operation","operation_id":"<上記のid>","target_skill":"<上記qualified target>","args":"<上記のargsをbytes一致で>"}
後続を自分でtoolへ読み替えて完了済みにせず、controllerの実user native適用を待つ。続くnative適用でも冒頭の単独cat全文Read・必要責務prompt・artifact提示/実選択順序を守る。全体の本題を終えるまで中間stageからout marker/DONEを出さない。

## 最終完了マーカー
成功/失敗/中断の最終時だけ、/Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-render/live-trial/20261115T1835-r44-render-codex/out/status.jsonへ {"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-receipt-positive-fixture-standard-v3-codex-v1"} を1回Writeし、最後に `DONE: <status>` と1行報告する。部分的完了、期待結果の自己申告、未実走をPASSにしない。sourceが求めるgoal/progress/intermediateは各ownerのFX/eval-logへ残す。source正規gateや独立評価を自作driverで代用しない。外部（本物のBeads・GitHub・Projects・Notion）への接続・書き込み0、plugin install0。予算はwall 900秒、tokens 3000000。延長・clock resetをしない。
