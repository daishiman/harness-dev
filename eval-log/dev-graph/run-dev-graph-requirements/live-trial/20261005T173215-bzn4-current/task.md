# タスク: dev-graph:run-dev-graph-requirements の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-requirements`
は、前回 run (20261004T1020-f11) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の repo から切った git worktree (branch `p83x-requirements`) に、その fixture の未追跡の状態 (`.dev-graph/` と content) を写したものです。同じ repository の worktree なので repository_id は元の fixture と一致し、C24 を通ります (前回の handoff 出力 `.dev-graph/handoff` は除いてあります)。
初期化済みで、`LT-FEATURE-001` と、その配下の P01..P13 exact-13 task package
`/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-requirements/system-plan/LT-FEATURE-001/package.json`
を持っています。

前回の状態を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は新規 node を常に
`confirmation_status=draft` / `evaluation_status=pending` で書き、confirmed / pass へ遷移させる経路を持ちません。
confirmed / pass の exact-13 package は system-dev-planner の promote 経路でしか作れないため、今の正規経路だけでは handoff の入力を用意できません。
この trial では feature と package を作り直さず、この fixture をそのまま handoff の入力にしてください。

### 本題

Skill({skill: "dev-graph:run-dev-graph-requirements", args: "handoff --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-requirements --feature-id LT-FEATURE-001 --package /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-requirements/system-plan/LT-FEATURE-001/package.json"})

### 検証

- handoff が実在し、capability-build / task-graph 向けの要件・13 task・lineage / digest を持つこと
- 本 skill が実装 code を 1 件も生成していないこと
- system plan validator と C11 がともに exit 0 であること (どちらかが非 0 なら PASS にしない)


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-requirements/live-trial/20261005T173215-bzn4-current/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C04-OUT1-positive-ready-handoff-fixture-standard-v2"}`
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
