# タスク: dev-graph:run-dev-graph-node の実走

この fixture は正規経路で dev-graph 初期化済みです。開始前の削除・reset・`rm`・
手書き graph 初期化は禁止し、現在の fixture に対する冪等な正規 C02 経路だけを使用してください。

### 準備

被験 skill が受け取る `--input` 用の mixed artifacts 候補ファイルを 1 つ作ってください。
issue / task / specification / architecture / document の 5 kind を 1 件ずつ含め、
specification は API 変更を伴う内容にしてください。この候補ファイルは scratchpad
(`/private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-node` の外) に置き、fixture へは直接書かないこと。
形状は `plugins/dev-graph/schemas/` と `plugins/dev-graph/templates/template-contract.json`、
および被験 skill の SKILL.md / prompts から導くこと。

### 本題

Skill({skill: "dev-graph:run-dev-graph-node", args: "add --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/live-trial-fixtures/gm-node --input <作成した候補ファイル>"})

### 検証

- 5 kind それぞれの frontmatter / path / template metadata が schema と一致すること
- architecture は subtype、specification は API contract overlay が反映されていること
- issue だけ本文を追記して同じ呼出しで連続更新し、graph_node_id と path が不変であること
- feature らしい通常入力の直接 add が C14 で fail-closed し、`features/` 直登録が 0 件であること
- 最終 graph が C11 (`validate-graph-schema.py`) を通ること


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------HarnessHub/512b21d9-0b24-4985-b1b8-d75bd17d8ecf/scratchpad/wt-guard/eval-log/dev-graph/run-dev-graph-node/live-trial/20260904T0700-gm3/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C02-OUT1-positive-mixed-artifacts"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。** 自分で書いた実装で
  成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content への書込みは必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) を通すこと。
  直接の file write や手書き JSON の graph 組み立てで代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 auditor / verifier subagent の起動を要求している場合は
  Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。
