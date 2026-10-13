# タスク: dev-graph:run-dev-graph-schedule の実走

### 準備

fixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-schedule`
は、前回 run (20260907T0500-gm4b) が `dev-graph:run-dev-graph-init` と
`dev-graph:run-dev-graph-node` の正規経路で作った fixture の repo から切った git worktree (branch `p83m-schedule`) に、その fixture の未追跡の状態 (`.dev-graph/` と content) を写したものです。同じ repository の worktree なので repository_id は元の fixture と一致し、C24 を通ります。初期化済みで、次が混在する graph を持っています:

- 依存が全て解決済みで ready になるべき task (複数、resource_scope が重なるものと重ならないものの双方)
- 依存が未解決で blocked のままであるべき task
- draft / 未確認 (unconfirmed) / evaluation 非 pass / readiness 非 complete の task

前回の状態を使う理由: 現行の C02 単一 writer (`build-graph-node.py`) は新規 node を常に
`confirmation_status=draft` / `evaluation_status=pending` で書き、通常 task を
confirmed / pass へ遷移させる経路を持たないため、ready な task を今の正規経路では作れません。
この trial では graph / content を作り直さず、この fixture をそのまま schedule の入力にしてください。

### 本題

Skill({skill: "dev-graph:run-dev-graph-schedule", args: "--repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-schedule --max-parallel 4"})

### 検証

- ready-set に全依存済み task だけが入ること
- blocked / draft / unconfirmed / evaluation 非 pass / readiness 非 complete が ready-set に 0 件であること
- batch 内の resource_scope 重複が 0 件であること
- suggested_branch と worktree claim command が一意であること


処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. Bash で `/Users/dm/miniconda3/bin/python3 /tmp/bzn4-status-helper.py 5 PASS`（失敗なら FAIL、実行障害なら ERROR）を実行し、固定先の完了マーカーを create-only で出す。パスを手で組み立てない。
2. `DONE: <status>` と1行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **graph / content を書き換える必要が生じた場合は、必ず `Skill({skill: "dev-graph:run-dev-graph-node", ...})` を
  起動し、その SKILL.md / prompts が定める手順の中で行うこと。** skill を起動せずに
  自分で staging 生成 / lock 取得 / atomic replace / receipt 作成を書くのは経路違反であり、
  この trial を無効にする (skill を「読んで真似る」のではなく「起動して従う」こと)。
- `config.json` / `state/graph.json` / `state/init-receipt.json` を Write tool で直接書き換えないこと。
- SKILL.md が独立 verifier subagent の起動を要求している場合は Agent tool で実際に起動すること。自己判定で代替しないこと。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書き、
  何がどう実行不能だったかを報告すること。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

機械隔離契約: Write/Edit/Artifact/ArtifactComments は CLI で禁止。全子プロセスも macOS sandbox により本 fixture と本 run dir 以外の file write を拒否する。run内 session-state/session-tmp は native CLI の認証・履歴・scratchpad・Agentの実行補助として許可するが、skillの成果物は fixture 内に作る。グローバルconfig/plugin/settingsを変更しない。必要なJSON入力も canonical手順からBashでfixture内へ出す。独立Agentにも同じ境界・prompt先読みを伝える。
必須順序: 起動した各SkillのSKILL.mdと、その出力に先行するprompts/R*.mdを実際にReadしてから writer を実行する。必須Agentを起動する。内部validatorが実行済みならその実結果も記録し、未実施checkをPASSにしない。
