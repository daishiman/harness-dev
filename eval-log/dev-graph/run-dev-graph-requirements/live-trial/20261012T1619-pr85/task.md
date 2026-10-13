# タスク: dev-graph:run-dev-graph-requirements の実走

### 準備

fixture `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx`
は、前回 run (20261004T1020-f11) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の状態 (追跡ファイル・`.dev-graph/`・content) を、この run のためにその場で git init した新しい repo へ写したものです。写した config と receipt の repository_id は新しい repo から導出した値へ置き換えてあり、C24 を通ります (前回の handoff 出力 `.dev-graph/handoff` は除いてあります)。
そのうえで、この session の開始前に、system-dev-planner の promote 経路 (`promote-system-plan.py`) で exact-13 package を publish し、dev-graph C02 の `register-package.py register` で P01..P13 の 13 member を graph に登録してあります。
初期化済みで、`LT-FEATURE-001` と、その配下の登録済みの P01..P13 exact-13 task package
`/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx/.dev-graph/plans/feature-package-LT-FEATURE-001/package.json`
(published package dir `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx/.dev-graph/plans/feature-package-LT-FEATURE-001`、C02 の登録 receipt `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx/.dev-graph/state/registration-receipts/feature-package-LT-FEATURE-001.json`)
を持っています。

前回の状態を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は新規 node を常に
`confirmation_status=draft` / `evaluation_status=pending` で書き、confirmed / pass へ遷移させる経路を持ちません。
confirmed / pass の exact-13 package は system-dev-planner の promote 経路でしか作れないため、今の正規経路だけでは handoff の入力を用意できません。
この trial では feature と package を作り直さず、この fixture をそのまま handoff の入力にしてください。

### 本題

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "handoff --repo-root /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx --feature-id LT-FEATURE-001 --package /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/fx/.dev-graph/plans/feature-package-LT-FEATURE-001/package.json"})

### 検証

- handoff が実在し、capability-build / task-graph 向けの要件・13 task・lineage / digest を持つこと
- 本 skill が実装 code を 1 件も生成していないこと
- system plan validator と C11 がともに exit 0 であること (どちらかが非 0 なら PASS にしない)


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4/workdir/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C04-OUT1-positive-ready-handoff-fixture-standard-v2"}`
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。** 自分で書いた実装で
  成果を作れば、検証されるのは skill ではなくあなたのコードになる。
- graph / content への書込みが必要になった場合は必ず C02 単一 writer
  (`Skill({skill: "dev-graph:run-dev-graph-node", ...})`) を通すこと。
  直接の file write や手書き JSON の graph 組み立てで代替しないこと。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 auditor / verifier subagent の起動を要求している場合は
  Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

隔離環境の注記: この session は sandbox 内で動いています。書込みは `/private/tmp/claude-501/-Users-dm-dev-dev------harness/077ff83f-2a4a-43b3-ac23-5a506e015759/scratchpad/wttrial/runs/requirements4` の内側だけが許可され、外部ネットワークは遮断、gh/bd は stub です。遮断や拒否に当たっても回避 (sandbox の解除・別経路) はせず、そのまま結果として扱ってください。
