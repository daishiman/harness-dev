# タスク: dev-graph:run-dev-graph-sync の実走 (gate 応答あり)

### 入力 (準備済み)

fixture repo-root (以下 `<FX>`) は
`/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-sync`
です。同期前の seed を commit した fixture repo の worktree で、次をすでに持っています。

- `.dev-graph/config.json` (execution_tracker.mode=github、github.enabled=true、issue_repository=local-fixture/r5-sync)
- tracker_binding=github の confirmed/pass/readiness-complete task 2 件 (`tasks/T-SYNC-001.md`、`tasks/T-SYNC-002.md`) と `.dev-graph/state/graph.json`
- 3-way base の `.dev-graph/state/github-sync-snapshot.json`
- remote authority の代わりになる決定論 adapter `<FX>/github-adapter.json` と、それを読む `<FX>/tools/fake-gh.py`

fixture の使い方は `<FX>/README.md` を読んで確かめること。
**この入力を準備のために書き換えないこと** (init や seed node の追加は不要)。
fixture へ書いてよいのは、被験 skill 自身が正規経路で行う同期の結果だけです。

### 本題

Skill({skill: "dev-graph:run-dev-graph-sync", args: "sync --repo-root /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-sync --binding github --adapter-fixture /Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-sync/github-adapter.json --repeat 2"})

**実在の GitHub へは絶対に接続しないこと。** remote は必ず adapter fixture (`github-adapter.json` と `tools/fake-gh.py`) だけを使うこと。

### external mutation guard の隔離fixture回答契約 (v2)
このtrialではcanonical preview→UserPromptSubmit hook→authorize→executeを実際に通す。事前に指定するfixture回答は、fixtureだけを対象にしたpreviewのchallengeへ `CONFIRM EXTERNAL MUTATION <challenge>` と返信すること。この返信はorchestratorが本Claude UIへ送る自動fixture入力であり、実在人間の新規判断や本repo/実GitHubの承認を証明するものではない。confirmation receiptを自作したりhook-confirm stdinを偽造してはならない。
まずBash cwdをfixture `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-sync` に移して、すべてのguard呼出しは --project-root `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/20261005T171515-bzn4-sync` に固定する。scopeはfixtureのlocal fake-ghだけ。実在GitHubへ接続せず、現実のaccountを操作しない。
preview後はchallenge, preview_receipt_id, project_rootを `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261005T173215-bzn4-current/gate-request.json` へWriteし、`GATE-CHALLENGE: <challenge>`を報告する。orchestratorのcanonical send-lineによる上記予め決めたreplyを待つ。この実UserPromptSubmit hookが発行したreceiptだけを利用する。新replyのhook出力または `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/run-dev-graph-sync/live-trial/20261005T173215-bzn4-current/gate-response.json` に返されたcanonical confirmation_receipt_pathをReadしてauthorize/executeに進む。Read待機中にBash pollingやpreview cancelを行わない。scope不一致やreceipt不成立は迂回せずFAIL。

### 検証

- 1 回目が期待どおりの import / export を適用すること (**export が実際に apply されるまで到達すること**)
- 2 回目の imports / exports の changes がともに 0 件であること (冪等)
- stable ID と snapshot が不変であること
- 3-way の base が保持されていること

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. Bash で `/Users/dm/miniconda3/bin/python3 /tmp/bzn4-status-helper.py 7 PASS`（失敗なら FAIL、実行障害なら ERROR）を実行し、固定先の完了マーカーを create-only で出す。パスを手で組み立てない。
2. `DONE: <status>` と1行だけ報告する。

**status 判定の規則 (厳守):**
- 1 回目の export が実際に apply され、かつ 2 回目が changes 0 件だったときだけ `PASS`。
- gate 未成立で 1 回目が未適用のまま終わった場合は `FAIL`。
  「前提が成立しないので 2 回目を省略した」は PASS の根拠にならない。

制約:
- gate 待機以外では人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと。

経路に関する絶対制約 (違反した時点でこの trial は無効):
- **被験 skill の責務を代行する自作スクリプトを書かないこと。**
- graph / content への書込みは、被験 skill の正規経路 (skill が定める script と C02 単一 writer) だけで行うこと。
  入力の graph.json・task・snapshot・config を手で書き換えて状態を作ってはならない。
- 責務 prompt (`prompts/R*.md`) は、その責務の出力を作る前に必ず読むこと。
- SKILL.md が独立 verifier subagent の起動を要求している場合は Agent tool で実際に起動すること。
- 上記が実行不能と判断した場合は、代替実装で回避せず status.json に `FAIL` を書くこと。

追加の試行境界: 書込先は上記の隔離fixtureと本runの証跡dirのみ。作業repoのsource/settings/plugin/install/release/Git/Beadsを変更しない。実在GitHub/Beads/外部サービスへの接続・mutationは禁止。現在repo下にpinされたplugin以外を代用しない。

隔離fixtureの事前回答契約: artifact_deliveryの選択はstandard。fixture内成果物を提示してから、この予め指定済みのstandardを記録して正規の後続検証へ進める。これは本repoや外部アカウントの承認ではない。Skill toolがUnknown skillになった場合、直ちにstatus.jsonをFAILで終了し、Readで真似る/直接scriptへ代替しない。

実行の意味: Skill toolは手順を現在contextへロードする。ロード成功だけでwriterが実行済みになったとは扱わず、ロードされたSKILLと各責務promptに従ってcanonical writer/validator/必須Agentを実行し、実成果を作って検証する。これはSkillが未登録の場合の代替ではない。

現行OUT1の追加観測: 2回目はIssue plannerとProjects plannerの両方でconverged=true、unresolved_count=0を実reportで確認する。changes=0のみではPASSとせず、missing/conflicts/held/skippedが残る場合はnextに従い未解決としてFAILにする。

外部公開は禁止: Artifact tool/Claude.ai publish/外部artifact作成は使わない。実成果物はfixture内ローカルfileのみ。ブラウザ検証が必要なら既存localPlaywright/Chromiumをisolatedprofileで使い、package/browserのinstallはしない。

機械隔離契約: Write/Edit/Artifact/ArtifactComments は CLI で禁止。全子プロセスも macOS sandbox により本 fixture と本 run dir 以外の file write を拒否する。run内 session-state/session-tmp は native CLI の認証・履歴・scratchpad・Agentの実行補助として許可するが、skillの成果物は fixture 内に作る。グローバルconfig/plugin/settingsを変更しない。必要なJSON入力も canonical手順からBashでfixture内へ出す。独立Agentにも同じ境界・prompt先読みを伝える。
必須順序: 起動した各SkillのSKILL.mdと、その出力に先行するprompts/R*.mdを実際にReadしてから writer を実行する。必須Agentを起動する。内部validatorが実行済みならその実結果も記録し、未実施checkをPASSにしない。
