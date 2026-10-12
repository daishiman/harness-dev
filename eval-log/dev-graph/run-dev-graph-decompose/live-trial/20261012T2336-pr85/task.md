# タスク: dev-graph:run-dev-graph-decompose の実走 (binding=beads)

### 準備

fixture `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/decompose4/fx` (以下 `<FX>`)
は、前回 run (20260907T0500-gm4b) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の状態 (追跡ファイル・`.dev-graph/`・content) を、この run のためにその場で git init した新しい repo へ写したものです。写した config と receipt の repository_id は新しい repo から導出した値へ置き換えてあり、C24 を通ります (前回の render 出力 `.dev-graph/render` は除いてあります)。
初期化済みです (init は不要)。config の `execution_tracker.mode` は `beads` です。graph には architecture `ARCH-LT-001`、feature `LT-FEATURE-001`、その配下の exact-13 task package (P01..P13) があり、package の registration receipt は `<FX>/.dev-graph/state/package-registration-receipt-LT-FEATURE-001.json` にあります。
まず graph が C11 (`validate-graph-schema.py`) を通ることを確認してください。

Beads の代わり: この fixture の Beads は `<FX>/tools/fake-bd.py` だけです。使い方は `<FX>/README.md` を読んで確かめてください。
この環境の bd の既定 (PATH 上の `bd` と環境変数 `DEV_GRAPH_BD` の既定値) は stub で、呼ぶと exit 4 で落ちます。
`bd-bridge.py` を呼ぶときは `DEV_GRAPH_BD=<FX>/tools/fake-bd.py` を付けてください。
**fixture の入力 (graph・content・config・receipt・README・tools) を準備のために書き換えないこと。**

### 本題

以下を実行してください:

Skill({skill: "dev-graph:run-dev-graph-decompose", args: "graph 実値 render (LT-FEATURE-001) の上に、render 結果を前回の render と比べる差分 feature と、その差分を要約して読み手に示す要約 feature を足す。差分 feature は LT-FEATURE-001 に依存し、要約 feature は差分 feature に依存する。共有の architecture は既存の ARCH-LT-001 を使う。新しい node の tracker_binding は beads。 --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/decompose4/fx --dry-run"})

### 検証

- 既存の node を含む feature+architecture の DAG が循環なしで、task 粒度の混入が無いこと
- 新しい node がすべて draft の preview であり、feature を通常の C02 add として直登録していないこと
- binding=beads の投影の preview (C28 `bd-bridge.py` の dry-run) で、起票の対象が confirmed/pass/readiness complete の node だけであること。評価前の draft の node の起票の対象が 0 件であること
- local graph・Beads・GitHub・Projects への write が 0 件であること (Beads は `<FX>/fake-bd-calls.jsonl` で確かめられる)。原 graph の digest が不変であること
- checklist が PARTIAL なら PASS にしないこと

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/decompose4/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"decompose-macro-promotion-gate-beads-fixture-standard-v3"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **成果物を生成する自作スクリプトを書かないこと。** driver / build / guard の類を自分で
  実装して成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content の生成と適用は必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`、preview は `--dry-run`) を通すこと。
  直接の file write や手書き JSON 組み立てで代替しないこと。
- Beads への投影は C28 (`bd-bridge.py`) を通すこと。bd や `tools/fake-bd.py` を直接呼んで投影の結果に代えないこと。
- SKILL.md の Macro flow が要求する独立 auditor は Agent tool で実際に起動すること
  (`dev-graph-integrity-auditor`)。自分で書いた検査コードによる自己判定で代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
  読まずに出力 shape を発明しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/decompose4` の内側だけが許可され、外部ネットワークは遮断、gh と既定の bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。
