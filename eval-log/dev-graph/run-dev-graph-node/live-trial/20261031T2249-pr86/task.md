# タスク: dev-graph:run-dev-graph-node の実走

fixture (dev-graph を初期化済みの git repo。graph は revision 0・node 0 件):
`/private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx`

### 準備

fixture は orchestrator が trial の前に `run-dev-graph-init` の正規 script (`build-init-scaffold.py --hook-source plugin`) で初期化し、commit してあります。この trial では init を再実行しないでください。

入力 batch `/private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx/mixed-artifacts.json` には、issue / task / specification / architecture / document の artifact が 1 件ずつ、計 5 件入っています (全件 `tracker_binding=none`。feature は入っていません)。この file も commit 済みです。`artifacts[]` は書き換えないでください。

### 本題 1: 5 kind の一括 add

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx --input /private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx/mixed-artifacts.json"})

ロードした SKILL と責務 prompt に従い、R2 の preview (`--dry-run`) を経て、C02 単一 writer の apply まで到達してください。
apply の入力は R3 の入力契約に従い、preview の `graph_revision_before` を `expected_graph_revision` として入れたものにします。`artifacts[]` は mixed-artifacts.json と同じにし、fixture の中の別 file (例: `/private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx/mixed-artifacts.apply.json`) に置いてください。

### 本題 2: 連続 update

本題 1 で登録した 5 node すべてについて、**本文の末尾に新しい H2 section を 1 つ追記するだけ**の update 入力 (`updates[]` の `append_sections`) を fixture の中に作り、
同じ skill を **実際にもう一度呼び出して** apply まで到達してください (staging 上の編集で終わらせないこと)。

Skill({skill: "dev-graph:run-dev-graph-node", args: "update --repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx --input <fixture の中の update 入力 JSON>"})

### 本題 3: feature の直接 add が C14 で fail-closed すること

`artifact_kind: "feature"` を含む通常の add 入力を fixture の中に作り、同じ skill を通して **実際に C02 単一 writer へ投入**してください。
投入せずに「`features/` が空である」ことを確かめるだけでは検証になりません。

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/node86/fx --input <fixture の中の feature 入力 JSON>"})

skill に渡す args の flag は、本題 1〜3 のどれでも `--repo-root` と `--input` だけにしてください (preview の `--dry-run` は skill の手順の中で writer に付けるもので、skill の args には付けません)。

### 検証

- 5 件すべてが kind ごとの正規 root (`issues/`・`tasks/`・`specs/`・`architecture/`・`docs/`) の `<root>/<slug>.md` に置かれ、`graph_node_id` が `<kind の prefix>-<slug>` であること
- 本題 1 と本題 2 の apply が実際に起きたこと (それぞれの receipt と graph_revision の増加で示すこと)
- 連続 update の後も、5 file それぞれの frontmatter の `artifact_kind`・`graph_node_id`・`file_path` が graph の値と一致し、`graph_node_id` と `file_path` が **update の前後で不変**であること
- 既存の本文が全置換されず、追記した section だけが増えていること
- feature の直接 add が **拒否された**こと (エラー出力そのものを証跡として残すこと)。拒否の後も `features/` 直下の file と graph の feature node が 0 件で、graph が壊れていないこと
- 最終 graph が `plugins/dev-graph/scripts/validate-graph-schema.py` を exit 0 で通ること

**status 判定の規則 (厳守):**
- 本題 1・本題 2・本題 3 を **すべて実際に実行し**、期待どおりの結果が得られたときだけ `PASS`。
- どれかが実行できなかった場合は、理由を問わず `FAIL` を書くこと。
  「実行しなかったが結果は自明」は PASS の根拠にならない。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **成果物を生成する自作スクリプトを書かないこと。** driver / build / guard の類を自分で
  実装して成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content への書込みは必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`、preview は `--dry-run`) を通すこと。
  直接の file write や手書きの graph 編集で代替しないこと。
- SKILL.md が要求する独立 verifier は Agent tool で実際に起動すること
  (`dev-graph-integrity-auditor`)。自分で書いた検査コードによる自己判定で代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
  読まずに出力 shape を発明しないこと。
- external mutation guard の preview は **発行しないこと** (この trial は local graph だけを扱う)。
  もし Bash が pending guard context で塞がれたら、迂回せずその事実を報告して FAIL を書くこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/node86/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts-r2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/node86` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。

scenario required_observations（正本の逐語）:
1. all five artifacts are routed to canonical kind paths
2. frontmatter kind and stored path agree after a consecutive update
3. no feature is created outside the C14 macro-feature contract
