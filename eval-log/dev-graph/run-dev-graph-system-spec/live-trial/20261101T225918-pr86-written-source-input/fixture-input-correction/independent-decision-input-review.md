# 新規合成入力 v6 の独立レビュー: PASS

このPASSは**入力定義の妥当性と再現性だけ**を対象にする。119のC05監査、C19のgoal達成、live-trialのPASS、実利用者の承認の代用にはしない。

D4は既存PG outbox＋独立worker/CronJobと、API BackgroundTasks＋内部HTTP起動の2案を実質比較している。前者のAPI停止からの独立性と追加運用、後者の専用worker削減と負荷/認証/復旧の結合を示し、goal fit・TCO・security・operations・lock-inの差を辿れる。0 JPY/月は追加OSSライセンス部分の合成givenで、構築・運用・移行・撤退の資源/工数は未見積りと明記している。総TCO0や無料資源保証を主張していない。

公式事実は限定して扱われている。SQLロックとqueue用途の注意は[PostgreSQL SELECT](https://www.postgresql.org/docs/16/sql-select.html)、スケジュールの重複/未実行可能性と冪等性は[Kubernetes CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)、応答後実行と重い計算の留意点は[FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)に接地する。保存HTTP本文3件のdigest/bytesを再計算し、公式URLにも独立アクセスして確認した。1秒claim・15分走査・30分表示、TCO/権限分離/復旧の比較はgivenまたは設計推論と区別され、公式による性能・費用・exactly-once保証へ拡張されていない。

比較提示はid昇順の案別比較、問の外の参考推奨、中立な問、提供済み合成回答を分ける。QAにはpg-worker-cronの明示選択とAPI案の不採用理由があり、その採択回答を改変していない。user_decision.noteはconfirmed_atをgiven記録の上限時刻と説明し、実利用者の新しい選択を観測した時刻と偽称していない。R5が要求しない「全field/全URLは必ず異なる」「TCOは必ず定量見積り」を新設していない。

## 正規CLI再現

独立scratch `/tmp/pr86-positive-input-v6-review-scratch` に旧v4の章/出典と元48QA基礎を複製し、producerの記録どおり正規CLI **25件**を順に再実行した。全件exit 0。state、出典、章10件を含むsystem-specの17ファイルがv6原本とバイト一致した。25 stdoutと空stderrも確認した。追加でdesign knowledge_refの実在gate（17参照）とrequired-infoの接地gateもexit 0。

元48QAは完全一致。v5との比較では全50QAはprovenance追記以外完全一致し、foundation・D1〜D3・matrix・approval_log・targetsも保持される。章単位のdesign/doctrine適用文とbasisは不変で、差は新規定義時のrecorded_atだけである。D4は初回set-decision入力として作られ、既存凍結QAや旧fixtureの内容を通常更新したものではない。評価report・監査台帳・PASSはseedにない。

生の再現ログとファイル別hashは `/tmp/pr86-positive-input-v6-review-replay.json`、構造化判定は `/tmp/pr86-positive-input-v6-review.json` に保存した。

## 確認範囲

blockerはない。依頼文の26CLIという件数と実際の25CLIの差、テンプレートの時刻、補助提示資料だけに全report項目がないことを未宣言のblocking条件へ拡大しない。

C05の全6観点を正式な独立forkで評価する作業は実施していない。次の実走ではcanonical flow、C05の新規判定、C02登録・lineage保持を別途実証する必要がある。本レビューはその成功を予告しない。過去input-reviewの結論や他agentの状態は読まず、旧データは比較の一次資料としてだけ利用した。source/fixture原本は無編集。
