# Codex native実走の契約

利用者がCodexを選んだときだけ使う。Claudeの証拠や起動失敗をCodexのPASSへ置き換えない。

## 起動と隔離

- `plan-live-trials.py --runtime codex`で対象・再利用・予算を決める。既定の新規2件・同時2件、明示承認後のexhaustiveという境界は共通。
- `manage-codex-live-trial.py --config <absolute-json-path> run`は、絶対pathで検証したCodex CLIの新規`exec`を起動する。継続は得られた同一sessionだけの`exec resume`。
- source provider、private control/raw、公開workdirはactorのworkspace外に置く。actorが書けるのは新fixtureと完了マーカー用の`workdir/out`だけ。HOME・CODEX_HOME・auth・ユーザー設定を別用途に使わず、sandboxを無効化しない。
- projectの`.agents/skills`から選択した実体を参照する。global/systemのskillカタログは残る場合があるため、「カタログが指定providerだけ」と主張しない。実際に適用・読込したskillは許可集合とsource bytesへ照合する。

## 本物の適用・呼出し

最初のuser入力にはnativeカタログの実登録名と業務argsを置く。plugin skillは`$<plugin>:<skill-name>`を使い、namespaceを省略しない。単独skillは実登録名が非修飾である場合だけ`$<skill-name>`を使う。原rolloutの自動`<skill>`注入・source対応表・成功した全文Readを、指定されたSKILL.mdのbytesへ束縛する。単なる名前・pathの言及、script直実行、架空のClaude `Skill`イベントは適用証拠ではない。

Codexで`Agent`相当の責務を実施するときは、元の責務promptを読んでnative subagentへ渡す。実spawn/waitと子の原ログを採取し、親sessionへの関係と終了を確認する。提供されない`close_agent`等を必須操作として捏造しない。

同じskillの複数operationや別skillへの正規handoffには、configの順序付き`native_operations`を使える。actorが指定されたcheckpointを出し、controllerが次の名前・args・sourceと完全一致する場合だけ、実user turnでnative適用を行う。これは明示的な複数入力の試行であり、救済nudgeや単一入力の自走と区別して記録する。未宣言の操作・順序逆転・Readだけを別のnative呼出しと数えることは拒否する。

成功した更新の後に期待される拒否を試すscenarioでは、各invocationのgoal-seek実体を編集せずbytes一致で保存できる。`goal_seek_eval_root_relative`で成功側を選ぶ場合、そのpathを起動前に固定し、最後の拒否側のblocked記録も保持する。fresh evaluatorは、保存元の実invocationと最終graphの一致・拒否前後のwrite 0・全観測を確認する。最後のblockedをPASSへ書き戻したり、過去やworkspace外のPASSを選んだりしない。

## 成果物提示と選択

1. main contextだけで最小の実成果物と最低限のguardを作る。
2. assistant本文に実path・bytes SHA-256・開き方・深度の四択を提示する。tool出力や自己申告receiptだけでは提示にならない。
3. fixtureの`artifact-choice-request.json`を待機状態で書き、turnを終える。outにはまだ書かない。
4. controllerが本文・現物bytes・許可source・未応答ID・Agent未起動を確認し、本物のuser turnで`standard`を返す。
5. actorは実返答の後にcanonical選択記録を保存し、後続の評価・Agentへ進む。

controllerは選択receipt・署名・承認イベントを自作しない。外部変更の確認はこの深度選択とは別契約である。実native hookや正規guard consumerが未到達なら保留し、generic resumeを契約上の承認へ読み替えない。

外部確認を検証するfixtureだけは、起動前に確認対象のsource・実cwd・許可argv・局所adapterとhook定義を固定する。利用者が正規`/hooks`で信頼した定義を照合し、Codex用の`hook-confirm --runtime codex`と`pretool --runtime codex`を実イベントで動かす。controllerが送れるのは、実assistantが提示した署名済みpreviewに一致する確認行だけである。原hook入力・出力と正本が発行した確認receiptを事後照合し、救済の`continue`と区別して回数を記録する。fixtureのadapterや実行対象のbytesが変わった場合は不合格とし、未観測のhookや未取得の利用者許可を補完しない。

外部確認の信頼照合には、標準のTOML readerを使えるPython 3.11以上が必要。`--ignore-user-config`を保ったまま、利用者が保存した当該fixtureのproject trustと2hookのnative hashだけを明示継承する。定義・native `hooks/list`の値・実際の保存値の不一致では起動せず、一般的なhook trust bypassは使わない。

## 証跡と終了

native JSONLをClaude形式へ変換しない。モデルはturn_context、CLI版とidentityはsession_meta、usageは原累積値から読み、同一threadの累積値を重ねて足さない。親子関係が証明できる子だけを合算し、不明・欠落・未完は合格にしない。

`collect`で原本をprivateへ固定してから公開copyを作り、除外・変換・SHAを保存する。fixture-finalとfreezeを取得後、別contextのfresh evaluatorへ渡す。作者・runnerはgoalのPASSを作らない。

`finalize --goal-evaluation <path>`は共通verdictの`--runtime codex`へ接続する。scenario全観測・goal-seek実体・予算・原SHA・閉包・独立goalをすべて維持する。未実行/停止は`--blocked`で記録し、PASSへ変えない。自ら起動したprocess groupだけを終了し、他sessionへ操作しない。

environmentにはruntime、native形式、Codex CLI版を明示する。Claudeの版やtmuxの存在をCodexの証明として使わない。旧Claudeのschema・digest・受入規則を維持する。
