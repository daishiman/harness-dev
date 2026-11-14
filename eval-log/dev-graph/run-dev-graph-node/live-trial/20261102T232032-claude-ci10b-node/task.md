# タスク: dev-graph:run-dev-graph-node の実走 (scenario C02-OUT1-positive-mixed-artifacts-r2)

この run は scenario C02-OUT1-positive-mixed-artifacts-r2 の充足を確認するものです。
scenario required_observations（正本の逐語）:
1. all five artifacts are routed to canonical kind paths
2. frontmatter kind and stored path agree after a consecutive update
3. no feature is created outside the C14 macro-feature contract

fixture (dev-graph を初期化済みの git repo。graph は node 0 件):
`/private/tmp/harness-claude-ci10-20261102/cases/node/fx`

この session の cwd は fixture `/private/tmp/harness-claude-ci10-20261102/cases/node/fx` です。業務パスは絶対パスを使ってください。plugin は同じ fixture の plugins/ にある trial 開始時点の写しを、boot が --plugin-dir で pin します。その写しも harness 作業ツリーも編集しないでください。

### 準備

fixture は orchestrator が trial の前に `build-init-scaffold.py --hook-source plugin` で初期化し、commit してあります。この trial では init を再実行しないでください。

入力 batch `/private/tmp/harness-claude-ci10-20261102/cases/node/fx/mixed-artifacts.json` には、issue / task / specification / architecture / document の artifact が 1 件ずつ、計 5 件入っています (全件 `tracker_binding=none`。feature は入っていません)。この file も commit 済みです。`artifacts[]` は書き換えないでください。

### 本題 1: 5 kind の一括 add

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /private/tmp/harness-claude-ci10-20261102/cases/node/fx --input /private/tmp/harness-claude-ci10-20261102/cases/node/fx/mixed-artifacts.json"})

ロードした SKILL と責務 prompt に従い、R2 の preview (`--dry-run`) を経て、C02 単一 writer の apply まで到達してください。
apply の入力は R3 の入力契約に従い、preview の `graph_revision_before` を `expected_graph_revision` として入れたものにします。`artifacts[]` は mixed-artifacts.json と同じにし、fixture の中の別 file (`/private/tmp/harness-claude-ci10-20261102/cases/node/fx/mixed-artifacts.apply.json`) に置いてください。

### 本題 2: 連続 update

本題 1 で登録した 5 node すべてについて、本文の末尾に新しい H2 section を 1 つ追記するだけの update 入力 (`updates[]` の `append_sections`) を fixture の中に作り、同じ skill を実際にもう一度呼び出して apply まで到達してください (staging 上の編集で終わらせないこと)。

Skill({skill: "dev-graph:run-dev-graph-node", args: "update --repo-root /private/tmp/harness-claude-ci10-20261102/cases/node/fx --input <fixture の中の update 入力 JSON の絶対パス>"})

### 本題 3: feature の直接 add が C14 で fail-closed すること

`artifact_kind: "feature"` を含む通常の add 入力を fixture の中に作り、同じ skill を通して実際に C02 単一 writer へ投入してください。投入せずに「`features/` が空である」ことを確かめるだけでは検証になりません。

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /private/tmp/harness-claude-ci10-20261102/cases/node/fx --input <fixture の中の feature 入力 JSON の絶対パス>"})

skill に渡す args の flag は、本題 1〜3 のどれでも `--repo-root` と `--input` だけにしてください (preview の `--dry-run` は skill の手順の中で writer に付けるもので、skill の args には付けません)。

### 検証

- 5 件すべてが kind ごとの正規 root (`issues/`・`tasks/`・`specs/`・`architecture/`・`docs/`) の `<root>/<slug>.md` に置かれ、`graph_node_id` が `<kind の prefix>-<slug>` であること
- 本題 1 と本題 2 の apply が実際に起きたこと (それぞれの receipt と graph_revision の増加で示すこと)
- 連続 update の後も、5 file それぞれの frontmatter の `artifact_kind`・`graph_node_id`・`file_path` が graph の値と一致し、`graph_node_id` と `file_path` が update の前後で不変であること
- 既存の本文が全置換されず、追記した section だけが増えていること
- feature の直接 add が拒否されたこと (エラー出力そのものを証跡として残すこと)。拒否の後も `features/` 直下の file と graph の feature node が 0 件で、graph が壊れていないこと
- 最終 graph が `plugins/dev-graph/scripts/validate-graph-schema.py` を exit 0 で通ること

status 判定の規則:
- 本題 1・本題 2・本題 3 をすべて実際に実行し、上の 3 observations が得られたときだけ `PASS`。
- どれかが実行できなかった場合は、理由を問わず `FAIL` を書くこと。「実行しなかったが結果は自明」は PASS の根拠にならない。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- 成果物を生成する自作スクリプトを書かないこと。
- graph / content への書込みは必ず C02 単一 writer (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`、preview は `--dry-run`) を通すこと。直接の file write や手書きの graph 編集で代替しないこと。
- SKILL.md が要求する独立 verifier は Agent tool で実際に起動すること (`dev-graph:dev-graph-integrity-auditor`)。自分で書いた検査コードによる自己判定で代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- external mutation guard の preview は発行しないこと (この trial は local graph だけを扱う)。もし Bash が pending guard context で塞がれたら、迂回せずその事実を報告して FAIL を書くこと。
- ゴールシーク配線は skill の定める `$DEV_GRAPH_ROOT/eval-log/run-dev-graph-node-goal-spec.json`、`run-dev-graph-node-progress.json`、`run-dev-graph-node-intermediate.jsonl` に保存する。`DEV_GRAPH_ROOT` は fixture `/private/tmp/harness-claude-ci10-20261102/cases/node/fx` とし、harness 作業ツリーへは書かない。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-node/live-trial/20261102T232032-claude-ci10b-node/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容: {"status": "PASS|FAIL|ERROR", "scenario": "C02-OUT1-positive-mixed-artifacts-r2"}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は fixture 側へ)。

追加の試行境界: 書込先は上記の隔離 fixture と本 run の証跡 dir のみ。作業 repo の source/settings/plugin/install/release/Git/Beads を変更しない。実在 GitHub/Beads/外部サービスへの接続・mutation は禁止。boot が pin した plugin 以外を代用しない。

隔離 fixture の事前回答契約: artifact_delivery の選択は standard。fixture 内成果物を提示してから、この予め指定済みの standard を記録して正規の後続検証へ進める。これは本 repo や外部アカウントの承認ではない。Skill tool が Unknown skill になった場合、直ちに status.json を FAIL で終了し、Read で真似る、または直接 script へ代替しない。

実行の意味: Skill tool は手順を現在 context へロードする。ロード成功だけで writer が実行済みになったとは扱わず、ロードされた SKILL と各責務 prompt に従って canonical writer/validator/必須 Agent を実行し、実成果を作って検証する。

外部公開は禁止: Artifact tool / Claude.ai publish / 外部 artifact 作成は使わない。実成果物は fixture 内ローカル file と、上で指定した status.json のみ。
