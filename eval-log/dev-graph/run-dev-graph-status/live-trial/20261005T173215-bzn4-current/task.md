# タスク: dev-graph:run-dev-graph-status の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-status`
は素の git repo であり dev-graph 未初期化です。まず正規経路で初期化してください。

Skill({skill: "dev-graph:run-dev-graph-init", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-status --hook-source plugin"})

その後、以下を行ってください。

status 対象の graph を **手作業ではなく skill の正規経路で** 用意してください。
C02 単一 writer (`dev-graph:run-dev-graph-node`) 経由で、slug `lt-task-001` の task
(writer が割り当てる id は `task-lt-task-001`) を含む task を複数登録し、
`task-lt-task-001` が depends_on を持ち、closed_at が意味を持つ状態にしてください。
id は writer が slug から割り当てるもので、呼出側から任意の id は指定できません。

準備で起動する init / node も「skill を正規経路で動かす」対象です。準備だからといって
責務 prompt の読込みを省略しないでください (下の経路制約はこの 2 skill にもかかります)。

### 本題

Skill({skill: "dev-graph:run-dev-graph-status", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-status --id task-lt-task-001"})

status skill が作る report の本文 (少なくとも対象 node の status / closed_at / depends_on を含むもの) を、
要約せずにそのまま応答として出力してください。「report を作った」と述べるだけでは出力したことになりません。

### 検証

- 出力した report の status / closed_at / depends_on が graph の実値と一致すること
- C11 (`validate-graph-schema.py`) が exit 0 であること
- 被験 skill 実行の前後で graph digest が不変であること (read-only)
- GitHub / Beads への write が 0 件であること


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. Bash で `/Users/dm/miniconda3/bin/python3 /tmp/bzn4-status-helper.py 6 PASS`（失敗なら FAIL、実行障害なら ERROR）を実行し、固定先の完了マーカーを create-only で出す。パスを手で組み立てない。
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
  これは被験 skill だけでなく、準備で起動する init / node にも適用する。
- SKILL.md が独立 auditor / verifier subagent の起動を要求している場合は
  Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記のいずれかが「実行できない」と判断した場合は、代替実装で回避せず、
  status.json に `FAIL` を書き、何がどう実行不能だったかを報告すること。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

機械隔離契約: Write/Edit/Artifact/ArtifactComments は CLI で禁止。全子プロセスも macOS sandbox により本 fixture と本 run dir 以外の file write を拒否する。run内 session-state/session-tmp は native CLI の認証・履歴・scratchpad・Agentの実行補助として許可するが、skillの成果物は fixture 内に作る。グローバルconfig/plugin/settingsを変更しない。必要なJSON入力も canonical手順からBashでfixture内へ出す。独立Agentにも同じ境界・prompt先読みを伝える。
必須順序: 起動した各SkillのSKILL.mdと、その出力に先行するprompts/R*.mdを実際にReadしてから writer を実行する。必須Agentを起動する。内部validatorが実行済みならその実結果も記録し、未実施checkをPASSにしない。
