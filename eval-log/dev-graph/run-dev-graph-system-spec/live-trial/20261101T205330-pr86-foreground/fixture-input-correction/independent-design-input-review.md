# 正の合成入力 v5 の独立レビュー

**PASS（入力定義の確認のみ）**。blockerはありません。これは次trialの受入PASS、C05完成度評価、C19 OUT1またはC02取込成功の判定ではありません。

評価者: `/root/review_sysspec115`。対象は `positive-input-v5` の現物・producer・正規writer/compiler source。旧input reviewの結論は読まず、転用していません。

## 再現と保持

別scratchで元48QA stateから、canonical `chunk` → `set-decision` → `set-targets` → canonical references assembler → 章単位18op → canonical compile → coverage/citation/design-knowledge-ref validatorsを実行しました。26 CLIはすべてexit0。stateと全 `system-spec/` はv5とbyte完全一致しました。private/publicは全file同一で、producerの/tmp原本とD copyも同一です。

元48QAは全field不変。v4の50QAと比較して、全question/answer/basis/source/answered_at・全承認・foundation・D1-D4・targets・matrixは不変です。相違は追加2QAの `design_applications`／`provenance` と、章単位のdesign/doctrine記録だけでした。各章の旧適用文はprefixとして保持されています。

v4の保護済みQA metadataを上書きするopは実行していません。新しいfixtureの初回chunkへ設計解釈を渡しており、実利用者の新しい承認やlegacy_backfillを偽称していません。source・v4・v5・publicのレビュー前後hashも一致しました。

## 意味上の適合と描画

追加2QAは、それぞれO1の業務／表示／測定と、D4の実行境界／復旧／最小権限を別の具体的な理由・trade-offとして記録しています。設計解釈は作者agentの推定であることを明記し、元の利用者回答と混ぜていません。

| 章 | 現物から確認した具体適用 |
|---|---|
| database | billing_expectations/missing_billing_cases/billing_closing_checks/job_outbox、同一PG transaction、claim/lease/fencing、一意キー、締め時の整合snapshotを既回答へ結ぶ。Blob offloading/複数資産補償を追加しない。 |
| backend | 既回答のAPI3操作・202・job状態とAPI/worker共通ユースケースを依存境界に結び、業務更新とoutboxを同一transactionへ置く。棄却済みBackgroundTasks案を復活させない。 |
| ui-ux | 既回答の担当者/リーダー・Web一覧・金額順・期限/不足明細・正しい請求書発行による解消を具体的な状態表示へ結ぶ。色だけに依存しない既存WCAG方針を継承し、外部メール/Slackを追加しない。 |
| security | D4既存security_fit/comparison_basisにあるPG最小権限と既存認可/追記監査をworker/CronJobへ当てる。DB role名・秘密配布方式・追加閲覧権は新規利用者決定にしない。 |
| infrastructure | 既存k8s/PG・Python worker Deployment・同じimageのCronJob・1秒claim/15分走査を観測/復旧へ接続。Cron重複抑制をexactly-onceとせず、未回答の資源上限/SLO/リトライ回数を追加確定しない。 |
| frontend | 既存画面/API取得層の境界を請求漏れ一覧/jobs状態へ適用し、受付と最終結果を区別する。クライアントが独自の業務解消判断を行わず、新しいグローバル状態管理基盤や外部通知を足さない。 |
| maintenance-ops | SRE観測/トイル削減/復旧と既存runbookを、失敗job・30分超未処理・永続outbox再開・検知解消/締め検査履歴へ具体的に接続。月次0件/3か月連続0件を保持し、新規の回数/閾値/運用権限を創作しない。 |

７章の `set-design-application` は本文へ逐語描画され、11件の `set-doctrine-application` もcanonical compilerが行う表セルの改行／pipe処理後に全件描画されています。元文をprefix保持し、根拠の性質は全追加記録で `agent-inference` です。auth章と要件定義章は追加対象外で、元bytesを保持しています。

単一PGであることはBlob offloading／外部資産補償を先行導入しない理由になります。一方、workerの再実行・claim/lease/fencing・冪等な業務反映を不要とはしていません。この境界はC04 cardの非適用条件と既回答に整合します。新broker/Redis/外部Blob、外部メール/Slack、具体DB role名、新SLO／retry数値を新しい利用者決定として追加していません。

## seedと適用範囲

canonical `system-spec/` にC05評価report・resume receipt・監査台帳はありません。graph／取込receiptもseedしていません。candidate-importは確認／評価status・confirmation evidence・imported_atを持たない草案です。compiled章は新しい評価済み成果ではなくgivenであり、次runで正規compile・独立監査／評価・C02登録を実証する必要があります。

D全体には旧 `independent-target-input-review.json`／`.md` が準備資料として継承されています。この２ファイルの中身は読んでいません。そのため「Dには一切reviewファイルが無い」とは主張せず、canonicalの評価seed無しと区別します。次trialの期待判定や受入証拠に旧reviewの結論を使わないでください。

refs／公式取得証跡はv4とbyte不変です。本レビューは現実世界の最新版を再取得・保証したものではなく、次trialのC08鮮度監査を免除しません。

## 証跡

- 独立replay詳細: `/tmp/pr86-positive-input-v5-replay.json`
- scratch: `/var/folders/35/t3gvbkdd2w55yk8csmzskzrw0000gn/T/pr86-v5-independent-wvjedsae`
- v5 state SHA-256: `f6b2fed7d76b05bd609fcba75b44f936e7dd1f8998f05f47043d72fa4a05d4aa`
- producer SHA-256: `bf6d0780ae93aace21a4429462091d6f7fe9ffa02d84ac8dc7051de3c431c21e`

source/state/publicは編集せず、検証書込は独立scratchと/tmpに限定しました。
