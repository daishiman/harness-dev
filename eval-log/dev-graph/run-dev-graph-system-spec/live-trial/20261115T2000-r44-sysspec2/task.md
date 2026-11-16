# タスク: dev-graph:run-dev-graph-system-spec の実走 (scenario C19-OUT1-positive-system-spec-lineage-r2)

この run は scenario C19-OUT1-positive-system-spec-lineage-r2 の充足を確認するものです。
scenario required_observations（正本の逐語）:
1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

開始時に fixture の `/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2/fx/CLAUDE.local.md` を Read し、各独立 Agent/Skill が同じ既存契約を受信することを守る (cwd が fixture ではないので自動では読み込まれない。各 Agent への指示にもこの絶対 path の Read を含める)。

fixture repo-root (以下 `<FX>`) は
`/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2/fx`
です。git の commit は空の "fixture: canonical resume inputs" が 1 つあるだけです。dev-graph は正規 builder で初期化済みで、graph.nodes は空です。入力は未追跡の `system-spec/` の state・出典資料・compiled 章です。`fetched-references.json` と `retrieval-evidence/` は、この trial の直前に同じ日の正規の doc-fetch で取り直した再開入力である。評価 report、PASS 結果、登録結果、取込 payload、監査台帳の行は種として置いていません。compiled 章は再開入力であり、今回の compile・evaluator・登録の証拠に代用しないでください。入力を準備のために書き換えず、変えるのは skill の正規 writer だけです。fixture の作り方は `/Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261115T2000-r44-sysspec2/fixture-provenance.json` に記録してあります。

この session の cwd は信頼済みの harness worktree `/Users/dm/orca/workspaces/harness/harness-creatorの改善` です。業務の読み書きは fixture `<FX>` の絶対パスだけを使ってください。plugin は boot が harness worktree の `plugins/` (dev-graph・system-spec-harness・skill-governance-adapters) を `--plugin-dir` で pin しています。fixture に plugin の写しはありません。plugin の script・SKILL.md・責務 prompt は `/Users/dm/orca/workspaces/harness/harness-creatorの改善/plugins/<plugin>/` の絶対 path で読み、呼び出してください。harness 作業ツリー、settings、plugin 本文は編集しないでください。

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-system-spec", args: "--repo-root /private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2/fx --resume"})

system-spec-harness の pin された entrypoint の preflight を通し、elicit の resume、必要なときだけ doc-fetch、compile、completeness evaluator (実際の Agent) を、正規の Skill の経路で実行してください。公式文書の取得と照合は WebFetch で行い、次の 5 host への https の読み取り (GET) だけが許可されています: www.postgresql.org・react.dev・fastapi.tiangolo.com・www.typescriptlang.org・kubernetes.io。WebSearch・ほかの host・認証が要る先・Bash のネットワーク CLI は使えません。正規の flow がそれ以外の外部取得を必須とするなら、迂回せずに FAIL にしてください。
compile された章と新しい evaluator の evidence ができた後でだけ、C02 の Skill で specification と architecture を confirmed・pass・readiness complete として登録してください。

この scenario (C19-OUT1-positive-system-spec-lineage-r2) で確かめる観測です。すべてを実測で満たさなければ PASS にしないでください:

1. the declared system-spec-harness plugin is loaded and its canonical flow completes
2. the imported specification and architecture retain source lineage and evaluator evidence
3. registration occurs only through C02 and no duplicate elicitation or compile logic appears in dev-graph

経路に関する絶対制約 (違反した時点でこの trial は無効):
- 成果物を生成する自作スクリプトを書かないこと。
- spec-state・fetched-references・compile の成果は system-spec-harness の正規 writer で、graph と content は C02 単一 writer (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) で作ること。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が要求する独立 Agent は Agent tool で実際に別 context として起動すること。手書きの evaluator PASS で代替しないこと。
- 実行できないと判断した場合は、代替実装で回避せず、status.json に FAIL を書き、何が実行不能だったかを報告すること。

foundation と各セルの承認内容は、fixture の qa_log と approval_log に明示済みです。ほかに意思決定が要るなら、承認を勝手に作らず FAIL にしてください。

監査 fork 台帳の注記: Claude の監査 fork 台帳は、この session の環境変数 `SYSTEM_SPEC_AUDIT_FORK_LEDGER` が指す `/Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261115T2000-r44-sysspec2/fork-ledger/audit-fork-ledger.jsonl` です (本 run の証跡 dir。書くのは system-spec-harness の hook だけ)。`aggregate-completeness.py` はこの環境変数から台帳を解決します。`--fork-ledger` を明示する場合はこの絶対 path をそのまま使い、fixture 内の `eval-log/system-spec-harness/audit-fork-ledger.jsonl` へ付け替えないでください。台帳を手書き・複写・補正しないでください。

ネットワークの注記: WebFetch による上の 5 host への https の読み取り (GET) だけは許可されています。それ以外は使わないでください。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/orca/workspaces/harness/harness-creatorの改善/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261115T2000-r44-sysspec2/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status":"PASS|FAIL|ERROR","scenario":"C19-OUT1-positive-system-spec-lineage-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は fixture 側へ)。
- hook に止められた操作は、別 file への移し替え・interpreter の変更・文字列の組み替えなど、形を変えて再試行しないこと。止められたら理由を読み、正規の道具 (Write / Edit の道具、または skill が定める script) で同じ記録を書けるかを考える。書けなければ、そこで止めて status.json を FAIL にし、止めた操作と理由を報告すること。

追加の試行境界: 書込先は上記の隔離 fixture と本 run の証跡 dir のみ (証跡 dir へは out/status.json と、hook が書く監査 fork 台帳だけ)。作業 repo の source/settings/plugin/install/release/Git/Beads を変更しない。実在 GitHub/Beads/Notion/外部サービスへの接続・mutation は禁止 (bd・gh などの外部書込コマンドを実行しない)。外部書込の確認用 preview も作らない・提示しない。boot が pin した plugin 以外を代用しない。

隔離 fixture の事前回答契約: artifact_delivery の選択は、各 run Skill (C19 自身、C02、system-spec-harness の各 run Skill) で次のとおり事前に指定済み。初回の選択 (accept-as-is / diagnose の 2 択) は `diagnose`。診断の所見の後に改善の深さを聞かれたら `standard`。fixture 内の最小の実成果物の現物 path・digest・開き方を提示してから、この指定済みの選択を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。

実行の意味: Skill tool は手順を現在 context へロードする。ロード成功だけで writer が実行済みになったとは扱わず、ロードされた SKILL と各責務 prompt に従って canonical writer/validator/必須 Agent を実行し、実成果を作って検証する。

外部公開は禁止: Artifact tool / Claude.ai publish / 外部 artifact 作成は使わない。実成果物は fixture 内ローカル file と、上で指定した status.json のみ。

資源予算: wall 3300 秒、tokens 23000000。延長しない。
