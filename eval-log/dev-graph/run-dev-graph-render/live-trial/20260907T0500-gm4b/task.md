# タスク: dev-graph:run-dev-graph-render の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-render`
は素の git repo であり dev-graph 未初期化です。まず正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-render --hook-source plugin"})

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

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/gm4b-render/.dev-graph/render/index.html"})

### 検証

- 外部 resource 参照が 0 件で、feature / task / edge が inline SVG で描かれていること
- `LT-FEATURE-001` の `X/13` と parent_feature 由来の実数が graph 実値と一致すること
- registration receipt の `applied_count/expected_count` と `source_digest` が
  表示内容および graph 実値と**一致**すること (HTML 上への digest 表示は要求されていない。
  表示を根拠に FAIL としないこと)
- 2 回 render して出力 digest が一致すること (決定論)
- checklist が PARTIAL なら PASS にしないこと


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20260907T0500-gm4b/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **graph / content への書込みは必ず `Skill({skill: "dev-graph:run-dev-graph-node", ...})` を
  起動し、その SKILL.md / prompts が定める手順の中で行うこと。** skill を起動せずに
  自分で staging 生成 / lock 取得 / atomic replace / receipt 作成を書くのは経路違反であり、
  この trial を無効にする (skill を「読んで真似る」のではなく「起動して従う」こと)。
- **`.dev-graph/` の初期化も `Skill({skill: "dev-graph:run-dev-graph-init", ...})` を起動して
  行うこと。** `config.json` / `state/graph.json` / `state/init-receipt.json` を Write tool で
  直接作らないこと。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書き、
  何がどう実行不能だったかを報告すること。
