# タスク: dev-graph:run-dev-graph-render の実走

### 準備

fixture `/private/tmp/claude-501/pr86-ci-live/lt/runs/render86/fx`
は、前回 run (20260907T0500-gm4b) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の状態 (追跡ファイル・`.dev-graph/`・content) を、この run のためにその場で git init した新しい repo へ写したものです。写した config と receipt の repository_id は新しい repo から導出した値へ置き換えてあり、C24 を通ります (前回の render 出力 `.dev-graph/render` は除いてあります)。
初期化済みで、`LT-FEATURE-001` という feature、その配下の exact-13 task package (P01..P13) と
registration receipt を持ち、一部の task は完了状態です。
registration receipt は `/private/tmp/claude-501/pr86-ci-live/lt/runs/render86/fx/.dev-graph/state/package-registration-receipt-LT-FEATURE-001.json` にあります。

前回の状態を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は package 配下の task の更新を
`package_member_requires_register_package` で拒否し、`register-package.py` も status=active の task しか受け付けないため、
task を完了状態にして `X/13` に意味を持たせる経路が今の正規経路にはありません。
この trial では graph を作り直さず、この fixture をそのまま render の入力にしてください。
まず graph が C11 (`validate-graph-schema.py`) を通ることを確認してください。

### 本題

準備した graph に対して被験 skill を実行します。**この段階以降、graph の作成・追加・
書き換えは一切禁止**です。

Skill({skill: "dev-graph:run-dev-graph-render", args: "--repo-root /private/tmp/claude-501/pr86-ci-live/lt/runs/render86/fx --output /private/tmp/claude-501/pr86-ci-live/lt/runs/render86/fx/.dev-graph/render/index.html"})

registration receipt は、SKILL.md の手順に従って `render-graph-html.py` の `--receipt` で渡してください。receipt を外して描く経路は使わないでください。

### 検証

- 外部 resource 参照が 0 件で、feature / task / edge が inline SVG で描かれていること
- `LT-FEATURE-001` の `X/13` と parent_feature 由来の実数が graph 実値と一致すること
- registration receipt を `--receipt` で渡して描画し、`X/13` の Y が receipt の `expected_count` と、
  子 task の集合が receipt の `node_ids` と一致し、表示対象が receipt の `source_digest` に対応すること
  (HTML 上への digest 表示は要求されていない。表示を根拠に FAIL としないこと)
- 2 回 render して出力 digest が一致すること (決定論)
- checklist が PARTIAL なら PASS にしないこと


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/pr86-ci-live/lt/runs/render86/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"render-feature-progress-receipt-positive-fixture-standard-v3"}`
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

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/pr86-ci-live/lt/runs/render86` の内側だけが許可され、外部ネットワークは遮断、gh/bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。

ブラウザの注記 (この run の環境): この sandbox では、AF_UNIX の socket の bind と connect が `/private/tmp/lt86/cr` の下だけで許されています (環境変数 `MAC_CHROMIUM_TMPDIR` がこの dir を指しています)。外部ネットワークは前と同じく全部遮断です。使えるブラウザは `/private/tmp/claude-501/pr86-ci-live/lt/runs/render86/browser/chrome-headless-shell-mac-arm64/chrome-headless-shell` です (Playwright の chromium_headless_shell-1243 を写したもの)。この sandbox では Chrome を複数 process で起動すると、mach の登録 (bootstrap_check_in) が拒否されて落ちます。そのため `--single-process --headless=new` を付けて起動してください。`--user-data-dir` と出力は `/private/tmp/claude-501/pr86-ci-live/lt/runs/render86` の内側に置いてください。ほかのブラウザや driver を install しないでください。

scenario required_observations（正本の逐語）:
1. the generated HTML has zero external resource references and draws features, tasks, and edges as inline SVG
2. LT-FEATURE-001 progress X/Y matches the graph, Y equals the registration receipt expected_count, and the child task set equals the receipt node_ids
3. the render is invoked with the registration receipt and its target corresponds to the receipt source_digest
4. two consecutive renders produce identical output digests
