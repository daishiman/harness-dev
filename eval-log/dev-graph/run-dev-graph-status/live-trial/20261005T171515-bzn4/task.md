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

1. /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-status/live-trial/20261005T171515-bzn4/out/status.json に完了マーカーを1ファイルだけ Write する。内容: `{"status":"PASS|FAIL|ERROR","scenario":"C18-OUT1-positive-read-only-status"}`
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
