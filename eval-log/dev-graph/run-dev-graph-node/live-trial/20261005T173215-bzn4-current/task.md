# タスク: dev-graph:run-dev-graph-node の実走

fixture (空の git repo。dev-graph 未初期化):
`/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-node`

### 準備

まず fixture を dev-graph の正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-node --hook-source plugin"})

次に C02 単一 writer 経由で 5 kind (issue / task / specification / architecture / document) の node を
それぞれ 1 件以上登録してください。全 node は `tracker_binding=none` とします。

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root <fixture> --input <入力ファイル>"})

### 本題 1: 冪等な連続更新

登録済みの issue node 1 件について、**本文に 1 section を追記するだけ**の入力を作り、
C02 単一 writer を **実際にもう一度呼び出して** graph へ適用してください (staging 上の
編集で終わらせず、apply まで到達すること)。

検証:
- apply が実際に発生したこと (receipt と graph_revision の増加で示すこと)
- 対象 issue の `graph_node_id` と `file_path` が **更新前後で不変**であること
- 既存本文が全置換されず、追記した section だけが増えていること
- 他 4 kind の node が無変更であること

### 本題 2: feature の直接 add が C14 で fail-closed すること

`artifact_kind: "feature"` を含む通常入力を作り、**実際に C02 単一 writer へ投入**してください。
投入せずに「`features/` が空である」ことを確認するだけでは検証になりません。

検証:
- 投入が **拒否された**こと (エラー出力そのものを証跡として残すこと)
- 拒否後も `features/` 直登録が 0 件で、graph が壊れていないこと

### 本題 3: 最終確認

- 最終 graph が `plugins/dev-graph/scripts/validate-graph-schema.py` を exit 0 で通ること

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-node/live-trial/20261005T173215-bzn4-current/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts-fixture-standard-v2"}`
2. `DONE: <status>` と1行だけ報告する。

**status 判定の規則 (厳守):**
- 本題 1 と本題 2 の **両方を実際に実行し**、期待どおりの結果が得られたときだけ `PASS`。
- どちらかが実行できなかった場合は、理由を問わず `FAIL` を書くこと。
  「実行しなかったが結果は自明」は PASS の根拠にならない。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。
- **被験 skill の責務を代行する自作スクリプトを書かないこと。**
- graph / content への書込みは必ず C02 単一 writer を通すこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
  これは被験 skill だけでなく、準備で起動する init にも適用する (準備だからといって省略しない)。
- external mutation guard の preview は **発行しないこと** (この trial は local graph だけを扱う)。
  もし Bash が pending guard context で塞がれたら、迂回せずその事実を報告して FAIL を書くこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。
