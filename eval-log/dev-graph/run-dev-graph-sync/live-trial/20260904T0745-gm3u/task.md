# タスク: dev-graph:run-dev-graph-sync の実走 (gate 応答あり・第3版)

fixture `/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync`
は準備完了済みです (C02 単一 writer 経由の seed node 登録、adapter fixture `github-adapter.json`)。
external write は 1 件も適用されていません。
**削除・reset・再初期化はせず、この状態のまま本題へ進んでください。**

### 本題

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync --binding github --adapter-fixture /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-sync/github-adapter.json --repeat 2"})

**実在の GitHub へは絶対に接続しないこと。** remote は必ず adapter fixture だけを使うこと。

### external mutation guard の gate 手順 (最重要・厳守)

confirmation receipt は実在の人間の UserPromptSubmit でしか作れないため、あなたには作れません。
**オペレーターが作ります。** 受け渡しはファイル経由で行います。

作業ディレクトリ (以下 `<GD>`):
`/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-sync/live-trial/20260904T0745-gm3u`

**手順 1: preview を出したら即座に challenge をファイルへ Write する**

`<GD>/gate-request.json` へ Write tool で次を書く (Bash は使わない):

```json
{"challenge": "<24桁の challenge>", "preview_receipt_id": "<preview receipt id>", "issued_at_iso": "<現在時刻>"}
```

同時に `GATE-CHALLENGE: <24桁>` を 1 行出力する。

**手順 2: `<GD>/gate-response.json` を Read tool だけで待つ**

- Read が失敗する (ファイルが無い) のは **正常な待機**であり、エラーでも失敗でもない。
- **最低 400 回**繰り返すこと。オペレーターの応答には人間の入力が挟まるため、
  **10 分以上かかるのが普通**である。3 分程度で諦めるのは重大な手順違反とみなす。
- **Bash による待機・polling は絶対に行わないこと** — preview 発行後は pending guard context により
  canonical guard 呼出し以外の Bash が塞がれるため、Bash で待つと自分自身を詰ませる。
- 待機中に preview を `cancel` してはならない。

**手順 3: preview が TTL (15分) 切れになった場合**

`authorize` が expired で失敗したら、**諦めずに preview を再発行**し、
新しい challenge で `<GD>/gate-request.json` を Write し直して手順 2 に戻る。
これを **最大 3 サイクル**繰り返してよい。

**手順 4: gate-response.json が読めたら**

その `confirmation_receipt_path` を使って `authorize` → `execute` と canonical guard 経路で進める。
guard 呼出しは shell 演算子を一切含まない単一コマンドで書くこと
(`&&` や `$PWD` 展開を混ぜると malformed として弾かれる)。

confirmation receipt の自作・hook-confirm への stdin 偽造・guard を迂回した直接実行はいずれも禁止。
3 サイクル使い切っても応答が無い場合のみ、迂回せず FAIL を記録すること。
gate 以外では人間に質問せず自走してください。

### 検証

- 1 回目が期待どおりの import / export を適用すること (**export が実際に apply されるまで到達すること**)
- 2 回目の imports / exports の changes がともに 0 件であること (冪等)
- stable ID と snapshot が不変であること
- 3-way の base が保持されていること

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. `<GD>/out/status.json` に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C03-OUT1-positive-second-sync-zero"}`
2. `DONE: <status>` と1行だけ報告する。

**status 判定の規則 (厳守):**
- 1 回目の export が実際に apply され、かつ 2 回目が changes 0 件だったときだけ `PASS`。
- gate 未成立で 1 回目が未適用のまま終わった場合は `FAIL`。
  「前提が成立しないので 2 回目を省略した」は PASS の根拠にならない。

制約:
- gate 待機以外では人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。**
- graph / content への書込みは必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) を通すこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 verifier subagent の起動を要求している場合は Agent tool で実際に起動すること。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書くこと。
