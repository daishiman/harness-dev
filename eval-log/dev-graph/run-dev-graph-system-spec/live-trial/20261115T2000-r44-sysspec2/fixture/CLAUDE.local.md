# 実走fixtureの共通実行契約

これは現行の dev-graph と system-spec-harness の既存契約を、親の会話を継承しない独立 context へ届ける指示である。判定基準・権限・予算・資料の期待PASSは渡さない。過去の評価結果は今回の判断に使わない。出力は日本語とする。

fixture root は `/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2/fx` である。graph.nodes は空で、評価report・PASS・登録結果・取込payloadは種に無い。`system-spec/` の確定問答・出典・compiled章は再開入力であり、今回のcompile実行・evaluator・登録の証拠に代用しない。

session の cwd は harness worktree `/Users/dm/orca/workspaces/harness/harness-creatorの改善` で、plugin の実体はその `plugins/<plugin>/` (boot が `--plugin-dir` で pin したもの) である。fixture に plugin の写しは無い。plugin の script・SKILL.md・責務prompt はこの実体の絶対pathで読み、呼び出す。harness worktree 側には書かない。

各Skill/Agentは担当の出力を作る前に、このCLAUDE.local.mdをReadし、自分のSKILL.md・責務prompt・必読SSOTをfrontmatterも含め全文取得する。親のReadを、自分が読んだ証拠と数えない。欠けたら残りを取得し、見出しやgrepで意味評価を代用しない。

親mainのBashは毎回、次の前置きで始める。開始時のC24 receiptのrootが違えば停止し、付け替えない。

`export CLAUDE_PROJECT_DIR="/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2/fx" && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && `

WebFetchのhttps GETは www.postgresql.org / react.dev / fastapi.tiangolo.com / www.typescriptlang.org / kubernetes.io の5hostだけである。WebSearch、他host、BashのネットワークCLI、外部公開はしない。sourceが他の取得を必須とするなら回避せずFAILにする。

各run Skillは最小の実成果物を作り、現物の絶対path・実SHA256・開き方を別呼出しで提示してから、事前に指定された選択を記録する。初回の選択 (accept-as-is / diagnose の2択) は `diagnose` とする。診断の所見の後に改善の深さを聞かれたら `standard` とする。choice記録の中のopen_withだけを、選択前の提示に代用しない。

Claude の監査fork台帳は、この session の環境変数 `SYSTEM_SPEC_AUDIT_FORK_LEDGER` が指す `/Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261115T2000-r44-sysspec2/fork-ledger/audit-fork-ledger.jsonl` である (本 run の証跡dir。writer は system-spec-harness の hook だけ)。`aggregate-completeness.py` は台帳をこの環境変数から解決する。`--fork-ledger` を明示するならこの絶対pathをそのまま渡し、fixture 内の `eval-log/system-spec-harness/audit-fork-ledger.jsonl` へ付け替えない。台帳を手書き・複写・補正しない。

C05の保存は、許可されたliteralのpathlib.Pathへsys.stdin.read()を無改変で渡す形だけを使う。自作のreport builderで緑化しない。3監査は1件ずつ、実の最終応答と台帳のresolvedを確認してから次へ進む。background指定はしない。

C02はevaluator PASSの後だけ呼ぶ。dry-runだけで選択を記録しない。pre-choiceのmainで正規writerの実nodeとreceiptを作り、path・digest・開き方を提示してから `diagnose` を記録し、診断の所見の後に深さを聞かれたら `standard` へ進む。登録後の独立な整合性監査は実際のAgentで行う。

成果物を生成する自作スクリプトは書かない。不足や未知SkillはFAILで止め、代替実装で回避しない。
