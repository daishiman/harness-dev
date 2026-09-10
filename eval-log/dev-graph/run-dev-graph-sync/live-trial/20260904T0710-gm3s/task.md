# タスク: dev-graph:run-dev-graph-sync の実走 (gate 応答あり)

fixture `/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync`
は前回の走行で準備が完了しています (C02 単一 writer 経由の seed node 登録、adapter fixture
`github-adapter.json` の作成まで)。external write は 1 件も適用されていません。
**削除・reset・再初期化はせず、この状態のまま本題へ進んでください。**

### 本題

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync --binding github --adapter-fixture /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync/github-adapter.json --repeat 2"})

**実在の GitHub へは絶対に接続しないこと。** remote は必ず adapter fixture だけを使うこと。

### external mutation guard の gate について (重要)

この skill は export 適用時に external mutation guard の confirmation を要求します。
confirmation receipt は**実在の人間の UserPromptSubmit イベント**でしか作れないため、
あなた自身では作れません。**オペレーターが応答します。**

guard の preview を発行して challenge を得たら、次の形式で **1 行だけ**出力し、
そこで応答を待ってください (これは「人間への質問」ではなく、契約上の正規 gate です):

```
GATE-CHALLENGE: <challenge の 24 桁>
```

オペレーターが `CONFIRM EXTERNAL MUTATION <challenge>` を送ると confirmation receipt が
封緘されるので、その後 `authorize` → `execute` と正規経路で進めてください。
confirmation receipt の自作・hook-confirm への stdin 偽造・guard を迂回した直接実行は
いずれも禁止です。gate 以外では人間に質問せず自走してください。

### 検証

- 1 回目が期待どおりの import / export を適用すること
- 2 回目の imports / exports の changes がともに 0 件であること (冪等)
- stable ID と snapshot が不変であること
- 3-way の base が保持されていること

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260904T0710-gm3s/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C03-OUT1-positive-second-sync-zero"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- gate 応答待ち以外では人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。**
- graph / content への書込みは必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) を通すこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 verifier subagent の起動を要求している場合は Agent tool で実際に起動すること。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書くこと。
