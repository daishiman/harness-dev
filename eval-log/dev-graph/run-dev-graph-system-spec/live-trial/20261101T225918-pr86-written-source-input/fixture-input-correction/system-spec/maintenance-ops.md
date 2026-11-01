---
status: confirmed
category: maintenance-ops
aggregate: 確定
spec_cells: [maintenance-ops.web, maintenance-ops.mobile, maintenance-ops.tablet, maintenance-ops.desktop-windows, maintenance-ops.desktop-linux, maintenance-ops.desktop-macos]
serves_goals: [G1]
---

# 保守運用管理 (maintenance-ops)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-008。裏付け質疑 (`qa_refs`): `qa-036`, `qa-o1-fixture-v3`, `qa-job-choice-fixture-v3` — 本章の「確定内容 (質疑録)」へ接地根拠として併記。資するゴール: G1 |
| モバイル (mobile) | 対象外 | 理由: 承認: appr-001 |
| タブレット (tablet) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (Windows) (desktop-windows) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (Linux) (desktop-linux) | 対象外 | 理由: 承認: appr-001 |
| デスクトップ (macOS) (desktop-macos) | 対象外 | 理由: 承認: appr-001 |

## 対象外の承認範囲

> 本章の対象外セルが引用している承認の実体。状態表の「承認: <id>」だけでは、その承認が何をどこまで認めたものかを章から辿れない。

### 承認: `appr-001`

ユーザー一括承認: 非 Web プラットフォームは全カテゴリで対象外

## 上流指針 (doctrine anchors)

> 本章の設計判断が従う上流の正本 (1 concern 1 authority)。具体技術ではなく上流工程を導く規範であり、下位の技術選定は本節と矛盾してはならない。正本: `ref-system-design-knowledge/references/doctrine-anchor-registry.json`

| 設計 concern | 上流の正本 (authority) | 導く範囲 | 出典 | 最終確認 | 本章の確定セルへの反映 |
|---|---|---|---|---|---|
| operations | Google SRE | 運用手順・障害対応・トイル削減・ポストモーテムの上流指針 | https://sre.google/workbook/ | 2026-07-12 | オンコール輪番と障害 runbook (qa-008) を、月末 3 営業日の遅延通知 (qa-029) の受け手として結ぶ。週次のリストア訓練 (qa-008) は、日次バックアップ (qa-001) が戻せたかを記録に残す。  qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: Google SREの観測可能性/トイル削減/復旧を、1秒claim・15分走査の稼働、lease/fencing状態、リトライ上限/失敗状態、30分超未処理の運用画面表示、worker停止後の永続outboxからの再開へ対応させる。請求漏れの検知/解消履歴と締め直後未解消件数をO1の月次0件/3か月連続0件へ追跡し、手動無視で解消しない。Clean Codeに従いrunbookの検知/切分け/再開を意図の分かる単位へ分ける。SRE名の引用だけで信頼性を保証せず、未回答の新しい回数/閾値/運用権限を確定しない。 concern=operationsの章固有適用として記録する。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1

#### 主たる接地根拠: `qa-008`

**問**

保守運用管理（maintenance-ops）× Web の要件は?

**答**

オンコール輪番・障害 runbook・週次リストア訓練。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 原本 (orig-spec-state.json、ファイル更新 2026-10-05) に当初から記録されていたシナリオ上の利用者回答。対話の逐語ログと回答時刻は残っていない。問は開いた問 (選択肢なし) で、代替案を提示した記録は無い (basis の user-decision は原本の値で、writer は記録済みの basis を上書きできない))

#### 裏付け質疑: `qa-036`

**問**

当番への通知を、どこからどのような手段で届けたいかを教えてください。

**答**

情報システム部の社内監視基盤のアラートから、オンコール輪番 (qa-008) のその週の担当者へ、社内チャットの当番チャンネルとメールの両方で送る。通知には、該当する runbook の手順へのリンクを付ける。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12, sysspec5): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。sysspec4 の評価で、infrastructure 章の応答時間の目安と通知の送り方に利用者の決定が無いことが指摘されたため、team-lead の指示 (2026-10-12) で足した。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T07:39:16Z)

#### 裏付け質疑: `qa-o1-fixture-v3`

**問**

O1の請求漏れをどう定義し、いつ検知し、誰へ示し、どのデータで月次成果を計測しますか。

**答**

O1 のテスト用要件を次で確定する。対象は qa-024 の有効契約から当月に発生する請求予定とその契約明細。請求予定ごとに契約ID・対象年月・予定請求期限・期待明細を保持する。予定請求期限を過ぎても有効な請求書がない、または請求書に必要な契約明細が欠ける場合を請求漏れとする。金額の食い違いは既存の突合機能へ分け、請求漏れの定義と混同しない。
15分ごとに自動走査し、期限超過から30分以内に担当者のWeb画面の「請求漏れ」一覧へ出す。契約担当の経理担当者と経理リーダーが閲覧し、件数・取引先・対象月・期限・不足明細・金額を表示して金額順に並べる。外部メールやSlackは追加しない。請求書を正しく発行すると次の走査で解消し、単なる手動の無視では解消扱いにしない。検知と解消を既存の追記専用監査ログへ残す。
請求予定は有効契約の期間と月次条件から漏れなく作り、取消済み・対象期間外の契約を除く。締め処理は全有効契約と請求予定・有効請求書を同じ整合した業務スナップショットで再照合し、漏れが残れば確定を拒否して一覧へ返す。結果は対象件数と未解消件数を保持する。締め完了直後の未解消件数をO1の月次計測値とし、元の「月次0件」と「3か月連続0件」を維持する。締め後の変更は元どおり赤黒訂正で、検知履歴・締め検査結果・監査ログを物理削除しない。
新しい表は billing_expectations、missing_billing_cases、billing_closing_checks、job_outbox とし、既存PostgreSQL 16内に置く。請求予定/検知ケースは契約ID・対象年月・種別の一意キーで重複反映を防ぐ。GET /billing-missing は一覧取得、POST /billing-missing/checks は再検査jobを202で受付け、GET /jobs/{id} で状態を返す。認可と更新競合は既存の担当者/リーダー権限と楽観ロックの規則を使う。業務ルールはAPIとworkerで共通に呼ぶユースケースへ置き、FastAPIやDB rowの型を業務中核へ持ち込まない。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: CI live-trial の正の合成入力 v3 を orchestrator が作成。111でO1実現要件が欠けていたことをC05と独立評価が検出したため補完する。以下の問答・承認はシナリオ上の利用者の既定発言であり、実利用者との対話・本番の承認ではない。対象agentが問答やPASSを自作したものでもない。 v5は独立した新しい正の合成fixture。v4を実行中に更新したものではない。質問/回答/承認/選択は保持し、作者agentの設計解釈だけを新fixtureの回答記録時に正規writerへ渡す。 / 回答時刻: 2026-11-01T08:35:54.756712Z)

#### 裏付け質疑: `qa-job-choice-fixture-v3`

**問**

非同期実行の構成として、(1) PostgreSQL outboxと独立worker/CronJob、(2) PostgreSQL outboxとAPI BackgroundTasks/内部HTTP起動を比較しました。どちらを採用しますか。別案・保留も選べます。理由と運用条件を教えてください。

**答**

比較した2案のうち pg-worker-cron を選ぶ。既存PostgreSQL 16のjob_outboxへ業務更新と同じtransactionで投入し、社内k8s上のPython worker Deploymentが1秒間隔でclaimする。重い突合と手動の再検査を処理し、15分ごとの請求漏れ走査は同じworker imageのCronJobで起動する。CronJobの重複起動抑制に加え、DB claimの排他・lease/fencing token・業務の一意キーと冪等性を使う。再試行で同じjobが実行され得ることは認め、業務効果の二重反映を禁止する。リトライ上限と失敗状態を保存し、30分を超えた未処理と失敗jobを運用画面へ出す。Worker停止時は永続outboxから再開する。監査ログは元の追記専用規則を保ち、業務/検知結果と整合するtransaction境界で残す。
API BackgroundTasksへ処理を寄せ、CronJobから内部HTTPを叩く案はAPI再起動・replica数・再試行・内部認証の運用が結び付くので採らない。外部broker/Redis/新しい保存基盤は足さない。両案のOSSライセンス追加費を0円とする比較はこの合成fixture内の前提であり、実サービスの総費用0や実相場を主張しない。workerのCPU/DB負荷と実装・監視の工数は残る。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: CI live-trial の正の合成入力 v3 を orchestrator が作成。111でO1実現要件が欠けていたことをC05と独立評価が検出したため補完する。以下の問答・承認はシナリオ上の利用者の既定発言であり、実利用者との対話・本番の承認ではない。対象agentが問答やPASSを自作したものでもない。 v6は同じ回答/採択/業務要件を持つ新givenで、decision-comparison-presentation.mdにid昇順の案別比較、問の外の参考推奨、中立な問、提供済み合成回答を分けて定義する。実利用者の新しい回答/承認ではない。 v5は独立した新しい正の合成fixture。v4を実行中に更新したものではない。質問/回答/承認/選択は保持し、作者agentの設計解釈だけを新fixtureの回答記録時に正規writerへ渡す。 / 回答時刻: 2026-11-01T08:35:54.756712Z)

## To-Be / Delta

> 本章の**規範**。上位概念 (要件定義書 U3 ゴール / U4 目標 / U9 具体的やりたいこと) を本章の serves_goals で絞り込んだ射影であり、設計知識 card (非規範の参考資料) とは役割が異なる。As-Is (現行実装の姿) は spec-state.json の管轄外のため本節では断定せず、到達点と、その到達を判定する観測点だけを規範として置く。

### 到達すべき状態 (To-Be)

- **G1**: 請求・監査データを単一の信頼できる情報源へ統合する

### 受入条件 (Delta の判定点)

| 目標 | 到達点 | 達成の観測点 (measure) |
|---|---|---|
| O1 | 請求漏れをシステムが自動で検知する | 締め後に残る請求漏れ 月次 0 件 (稼働後最初の月次締めから計測) |

### 本章がかなえる具体的やりたいこと (U9)

- **I1**: 請求・監査データを日次でバックアップする
- **I3**: 確定した請求書は書き換えず赤黒訂正で直し、監査ログは追記のみとする

### 本章に効く確定意思決定

- **D1**: データベースに使う PostgreSQL の版をどれにするか (情報システム部の提供版は 15 と 16, qa-018)
  - 採択: PostgreSQL 16 (情報システム部が提供する版) (`pg16`)
  - 目的適合: G1 (単一の信頼できる情報源) に要るトランザクション・制約・バックアップの機能を満たす
  - 採択の接地根拠: `qa-031`
- **D3**: 社内 IdP の OIDC で得たトークンを、どこで持ち、API へどう送るか
  - 採択: バックエンド (FastAPI) がトークンを持ち、ブラウザには cookie のセッションだけを渡す方式 (`bff-session`)
  - 目的適合: G1 (請求・監査データの単一の情報源) の信頼を、トークンをブラウザに出さないことで支える。8 時間のセッション (qa-002) と、IdP でのアカウントの無効化 (qa-026) をサーバ側で扱える
  - 採択の接地根拠: `qa-034`
- **D4**: 非同期突合とO1自動検知のジョブ実行構成
  - 採択: 既存PG outbox＋独立Python worker＋k8s CronJob (`pg-worker-cron`)
  - 目的適合: 独立workerがAPIの再起動/重いHTTP負荷から分離して永続outboxを継続処理し、G1/O1の15分走査・30分以内表示とG2の重い突合を担う。1秒claim/15分CronJobは合成givenの構成値で、処理時間や達成率の実測保証ではない。
  - 採択の接地根拠: `qa-job-choice-fixture-v3`

## 適用された設計知識

> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。

### 本章での適用

clean-code の『意図の分かる名前』と『効果とエラーを明示する』を runbook (qa-008) に当てた。障害手順は『何が起きたら・誰が・何をするか』が名前で分かる単位に分ける。週次のリストア訓練 (qa-008) は、実行できる手順そのものを runbook に置き、日次バックアップ (qa-001) が戻せることを毎週確かめる (実行できる例)。

qa-o1-fixture-v3/qa-job-choice-fixture-v3/D4への追加解釈: Google SREの観測可能性/トイル削減/復旧を、1秒claim・15分走査の稼働、lease/fencing状態、リトライ上限/失敗状態、30分超未処理の運用画面表示、worker停止後の永続outboxからの再開へ対応させる。請求漏れの検知/解消履歴と締め直後未解消件数をO1の月次0件/3か月連続0件へ追跡し、手動無視で解消しない。Clean Codeに従いrunbookの検知/切分け/再開を意図の分かる単位へ分ける。SRE名の引用だけで信頼性を保証せず、未回答の新しい回数/閾値/運用権限を確定しない。
これは既存回答に対するfixture作者agentの設計解釈であり、新規の利用者承認ではない。

- (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない) / 記録時刻: 2026-11-01T13:09:33.335262Z)

### Clean Code — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/clean-code.md`

#### 目的

codeを、次の変更者が意図・制約・failureを短時間で理解し、安全に変更・検証できる作業媒体にする。

#### 解決する問題

- 名前と抽象度が意図を表さず、readerが実装詳細からbusiness ruleを逆算する。
- 一つの変更理由が複数moduleへ散り、副作用とerror pathを予測できない。
- 重複したruleが別々に更新され、仕様のSSOTが崩れる。
- testがimplementation detailへ結合し、refactoringを妨げる。

#### 適用条件

- 複数人・長期保守・高変更頻度・重要ruleがあり、理解と変更の費用が支配的。
- test/lint/review/observabilityで改善効果をfeedbackできる。
- domain languageとcoding conventionをteamで合意・更新できる。

#### 非適用条件

- throwaway explorationでは全規則を先行適用せず、学習後に残すcodeだけを整理する。
- generated/vendor codeへ手動styleを強制しない。generation inputとboundaryを管理する。
- 短い関数、class化、DRY等を絶対値として扱い、局所的な明瞭さを悪化させる場合は適用しない。

#### トレードオフ・失敗モード

- naming/refactoring/testへ時間を使うため、寿命とriskが低いcodeでは投資超過になり得る。
- micro-function化でcontrol flowが多数fileへ散り、かえって読みにくくなる。
- DRYを急ぎ、異なるdomain conceptを一つの抽象へ結合して変更を難しくする。
- commentを全否定して、理由、trade-off、外部制約、security decisionまで消す。
- coverageやlint scoreを目的化し、重要behaviorの未検証を隠す。

#### goalへの寄与

- goalに関わるbusiness ruleを名前とtestで明示し、仕様→code→evidenceのtraceを短くする。
- maintenance objectiveには変更lead time、review指摘、escaped defect、rollback率などのoutcomeを使う。
- 無料toolの導入自体を成功とせず、teamが継続運用でき、重要riskを減らすかで判断する。

---

### 確定判断ごとの原則採否

- 確定内容 `qa-008` (対応セル: web)
  - 確定要件: 「オンコール輪番・障害 runbook・週次リストア訓練。」 (正本: 本章「確定内容 (質疑録)」の `qa-008`)
  - 設計解釈の記録経路: `legacy_backfill` (`set-qa-design-applications`)
  - 原則 (`plugins/system-spec-harness/skills/ref-system-design-knowledge/references/clean-code.md#中核概念`): 意図と効果・失敗を明示し、実行例で手順を検証する
    - 採否: `applied`
    - 章固有の根拠: qa-008のオンコール輪番・障害runbook・週次リストア訓練を、誰が何を実行し何を確認すれば回復したと言えるかが読み取れる単位で記録する。
    - トレードオフ:
      - 手順と実際の運用がずれないよう、訓練後の更新作業が必要。
      - 自動化は目的ではなく、障害時にも効果と失敗が追えることを優先する。
- 資するゴール: G1

## 最新ドキュメント出典

| 対象 | バージョン | 公式発行元 | 出典URL | 取得 | 最新確認 |
|---|---|---|---|---|---|
| kubernetes | 2026-05-13T21:32:47+01:00 | The Kubernetes Authors (kubernetes.io) | https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/ | 2026-11-01T09:14:52.437427Z | 2026-11-01T09:14:52.437427Z |
