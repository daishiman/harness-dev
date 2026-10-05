# タスク: dev-graph:run-dev-graph-render の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83b-render`
は、前回 run (20260907T0500-gm4b) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の複製です (前回の render 出力 `.dev-graph/render` は除いてあります)。
初期化済みで、`LT-FEATURE-001` という feature、その配下の exact-13 task package (P01..P13) と
registration receipt を持ち、一部の task は完了状態です。

複製を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は package 配下の task の更新を
`package_member_requires_register_package` で拒否し、`register-package.py` も status=active の task しか受け付けないため、
task を完了状態にして `X/13` に意味を持たせる経路が今の正規経路にはありません。
この trial では graph を作り直さず、この fixture をそのまま render の入力にしてください。
まず graph が C11 (`validate-graph-schema.py`) を通ることを確認してください。

### 本題

準備した graph に対して被験 skill を実行します。**この段階以降、graph の作成・追加・
書き換えは一切禁止**です。

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83b-render --output /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83b-render/.dev-graph/render/index.html"})

### 検証

- 外部 resource 参照が 0 件で、feature / task / edge が inline SVG で描かれていること
- `LT-FEATURE-001` の `X/13` と parent_feature 由来の実数が graph 実値と一致すること
- registration receipt の `applied_count/expected_count` と `source_digest` が
  表示内容および graph 実値と**一致**すること (HTML 上への digest 表示は要求されていない。
  表示を根拠に FAIL としないこと)
- 2 回 render して出力 digest が一致すること (決定論)
- checklist が PARTIAL なら PASS にしないこと


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-render/live-trial/20261005T0806-p83b/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-positive"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。** 自分で書いた実装で
  成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content を書き換えないこと。`config.json` / `state/graph.json` / receipt を Write tool で直接書き換えないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 auditor / verifier subagent の起動を要求している場合は
  Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。
