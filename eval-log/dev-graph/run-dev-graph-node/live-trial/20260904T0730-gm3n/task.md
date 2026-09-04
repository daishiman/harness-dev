# タスク: dev-graph:run-dev-graph-node の実走 (第2版・冪等更新と C14 を必ず実施)

fixture:
`/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-node`

この fixture には既に 5 kind (issue / task / specification / architecture / document) の node が
正規経路で登録済みです。**削除・reset・`rm`・手書き graph 初期化は禁止**。現在の状態に対する
冪等な正規 C02 経路だけを使ってください。

前回の走行では、以下の 2 項目が **一度も実行されないまま** PASS が申告されました。
今回はこの 2 項目が本題です。**必ず実際に呼び出して、結果を証跡で示してください。**

### 本題 1: 冪等な連続更新 (最優先・最初にやること)

既存の issue node 1 件について、**本文に 1 section を追記するだけ**の入力を作り、
C02 単一 writer を **実際にもう一度呼び出して** graph へ適用してください (staging 上の
編集で終わらせず、apply まで到達すること)。

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root <fixture> --input <追記用の入力ファイル>"})

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

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-node/live-trial/20260904T0730-gm3n/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts"}`
2. `DONE: <status>` と1行だけ報告する。

**status 判定の規則 (厳守):**
- 本題 1 と本題 2 の **両方を実際に実行し**、期待どおりの結果が得られたときだけ `PASS`。
- どちらかが実行できなかった場合は、理由を問わず `FAIL` を書くこと。
  「実行しなかったが結果は自明」は PASS の根拠にならない。

制約:
- 途中で人間に質問せず最後まで自走すること。
- out/ には status.json 以外を書かないこと。
- **被験 skill の責務を代行する自作スクリプトを書かないこと。**
- graph / content への書込みは必ず C02 単一 writer を通すこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- external mutation guard の preview は **発行しないこと** (この trial は local graph だけを扱う)。
  もし Bash が pending guard context で塞がれたら、迂回せずその事実を報告して FAIL を書くこと。
