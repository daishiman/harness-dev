# D4 合成givenの案別比較

この文書はCI用の新しい合成入力定義であり、実利用者への提案/新承認ではない。料金の0円は追加OSSライセンス部分だけのgivenで、実価格/総TCOの見積りではない。

## api-background-http

- goal_fit: "PG outboxと再走査/claimを正しく実装すればG1/O1/G2を満たす構成は可能。ただし実行をAPIプロセスとHTTP起動に置くため、APIのrollout/停止/混雑がジョブ開始/進捗と結合する。BackgroundTasksそのものを永続queueや定期schedulerと扱わず、outboxによる再開処理を別に要する。"

- cost_model: {"category": "free", "amount": 0, "currency": "JPY", "billing_period": "month", "tco": "amount=0 JPY/月はこのfixtureが仮定する追加OSSライセンス部分だけ。構築費はPG outbox/再開/冪等性に内部HTTP認証/起動連携を加え、運用費はAPIのCPU/容量/監視にjob再送/復旧と秘密更新を加える。専用worker Deploymentは減るが実装/運用総費の大小は未実測。移行/撤退時はBackgroundTasks/HTTP起動と再開経路を独立worker等へ置換する費用がある。総TCO0を意味しない。"}

- free_tier_limits: "FastAPI/PGの追加ライセンスを無償と置く合成前提で、実行資源無償や商用API枠を意味しない。API replicaのCPU/メモリ/同時実行とDB接続枠をオンライン要求と共有し、重い突合で干渉しない容量検証が必要。"

- security_fit: "API側のDB接続/認可を再利用する一方、CronJobから内部HTTPを起動する認証・認可と呼出し主体/秘密の管理、不要な外部公開を防ぐ境界を増やす。HTTP再送にも業務一意キー/claim排他を適用する必要がある。"

- pros: ["worker専用imageを減らせる"]

- cons: ["APIの再起動と負荷へ結合", "内部HTTP認証と再開処理が増える"]

- risks: ["API停止時に処理が遅れる", "複数replica/再試行時に排他が必要"]

- lock_in: "PG outbox/claimに加えてFastAPI BackgroundTasksのプロセス実行と内部HTTP起動API、CronJobの呼出し設定へ依存する。別backend/独立workerへ移す際は起動/再開/認証の接続部を変更する。業務データや純Pythonユースケースは共通化できる。"

- ops_burden: "中〜高。専用worker Deploymentは減らせるが、API rollout/replica/負荷制御とjob再開、内部HTTPの認証/再送/失敗切分けを同じ運用で扱う。PG outboxがあるためAPI再起動で必ずjobが消失するとは主張しない。"

- evidence_refs: ["https://fastapi.tiangolo.com/tutorial/background-tasks/", "https://www.postgresql.org/docs/16/sql-select.html", "https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/"]

## pg-worker-cron

- goal_fit: "独立workerがAPIの再起動/重いHTTP負荷から分離して永続outboxを継続処理し、G1/O1の15分走査・30分以内表示とG2の重い突合を担う。1秒claim/15分CronJobは合成givenの構成値で、処理時間や達成率の実測保証ではない。"

- cost_model: {"category": "free", "amount": 0, "currency": "JPY", "billing_period": "month", "tco": "amount=0 JPY/月はこのfixtureが仮定する追加OSSライセンス部分だけ。構築費はoutbox/claim/lease/fencing/冪等性とworker/CronJobの実装・テスト、運用費は既存PG/クラスタのCPU/容量/監視と復旧工数、移行/撤退費はclaim adapter・scheduler/manifestと手順の置換。資源/工数の金額は未見積りで、総TCOが0との主張ではない。"}

- free_tier_limits: "PG/Python/Kubernetesのソフトウェア追加ライセンスを無償と置く合成前提であり、商用free-tierの容量保証ではない。workerとCronJob用の既存クラスタCPU/メモリ、DB接続/容量と負荷の余力を別途計測する必要がある。"

- security_fit: "worker/CronJobのDB接続をAPIと別の実行主体として最小権限化でき、追加のHTTP起動入口を設けない。DB権限・秘密配布・lease/fencing/追記監査の実装検証は必要であり、具体roleや新しい業務閲覧権を承認済みと追加しない。"

- pros: ["APIライフサイクルと分離", "永続queueと同じ業務規則を再利用"]

- cons: ["workerのdeploy/監視が増える"]

- risks: ["lease/fencingと冪等実装が必要", "Cronの重複抑制だけではexactly-onceを保証しない"]

- lock_in: "PGのclaim SQL/lease表とKubernetes Deployment/CronJob設定へ依存する。業務ユースケースは純Pythonで共有し、別の実行基盤へ移す際はscheduler/DB claim adapterと運用手順を置換する。APIフレームワークのBackgroundTasksには依存しない。"

- ops_burden: "中。workerとCronJobのdeploy/停止/再開、pending齢・lease切れ・失敗件数、DB負荷を観測する対象が増える。HTTP/APIのrolloutから処理系を分離でき、復旧は永続outboxのclaim再開で行う。"

- evidence_refs: ["https://www.postgresql.org/docs/16/sql-select.html", "https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/"]

## 参考：推奨（問の外）
G1/O1の定期自動検知とG2の重い突合を、オンラインAPIの停止/rollout/負荷から分離できる点でpg-worker-cronを推奨する。追加のworker/CronJob運用が必要という不利を認め、既存PG/k8sを使い新brokerを増やさないというgivenの制約と整合させる。推奨それ自体は利用者の採否ではない。

## 中立な問
非同期実行の構成として、(1) PostgreSQL outboxと独立worker/CronJob、(2) PostgreSQL outboxとAPI BackgroundTasks/内部HTTP起動を比較しました。どちらを採用しますか。別案・保留も選べます。理由と運用条件を教えてください。

## 合成利用者の既定回答
比較した2案のうち pg-worker-cron を選ぶ。既存PostgreSQL 16のjob_outboxへ業務更新と同じtransactionで投入し、社内k8s上のPython worker Deploymentが1秒間隔でclaimする。重い突合と手動の再検査を処理し、15分ごとの請求漏れ走査は同じworker imageのCronJobで起動する。CronJobの重複起動抑制に加え、DB claimの排他・lease/fencing token・業務の一意キーと冪等性を使う。再試行で同じjobが実行され得ることは認め、業務効果の二重反映を禁止する。リトライ上限と失敗状態を保存し、30分を超えた未処理と失敗jobを運用画面へ出す。Worker停止時は永続outboxから再開する。監査ログは元の追記専用規則を保ち、業務/検知結果と整合するtransaction境界で残す。
API BackgroundTasksへ処理を寄せ、CronJobから内部HTTPを叩く案はAPI再起動・replica数・再試行・内部認証の運用が結び付くので採らない。外部broker/Redis/新しい保存基盤は足さない。両案のOSSライセンス追加費を0円とする比較はこの合成fixture内の前提であり、実サービスの総費用0や実相場を主張しない。workerのCPU/DB負荷と実装・監視の工数は残る。
