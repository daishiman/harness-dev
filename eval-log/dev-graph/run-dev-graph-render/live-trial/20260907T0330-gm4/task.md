# タスク: dev-graph:run-dev-graph-render の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-render`
は素の git repo であり dev-graph 未初期化です。まず正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-render --hook-source plugin"})

その後、以下を行ってください。

render 対象となる canonical graph を **正規経路だけで** 用意してください。
`LT-FEATURE-001` という feature と、その配下の exact-13 task package (P01..P13) を
C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で登録し、
registration receipt を残してください。一部の task は完了状態にして進捗が
`X/13` の形で意味を持つようにしてください。
準備が終わったら graph が C11 (`validate-graph-schema.py`) を通ることを確認してください。

### 本題

準備した graph に対して被験 skill を実行します。**この段階以降、graph の作成・追加・
書き換えは一切禁止**です。

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4-render/.dev-graph/render/index.html"})

### 検証

- 外部 resource 参照が 0 件で、feature / task / edge が inline SVG で描かれていること
- `LT-FEATURE-001` の `X/13` と parent_feature 由来の実数が graph 実値と一致すること
- source_digest が graph と対応していること
- 2 回 render して出力 digest が一致すること (決定論)
- checklist が PARTIAL なら PASS にしないこと


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260907T0330-gm4/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}`
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
