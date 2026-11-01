---
status: confirmed
category: backend
aggregate: 確定
spec_cells: [backend.web, backend.mobile, backend.tablet, backend.desktop-windows, backend.desktop-linux, backend.desktop-macos]
serves_goals: [G1, G2]
---

# バックエンド (backend)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-006。裏付け質疑 (`qa_refs`): `qa-018`, `qa-024`, `qa-025` — 本章の「確定内容 (質疑録)」へ接地根拠として併記。資するゴール: G1, G2 |
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
| application-architecture | Robert C. Martin — Clean Architecture | レイヤ境界・依存方向 (内向き)・ユースケース中心設計 | Clean Architecture (2017), the Dependency Rule | 2026-07-12 | 請求書・突合・確定承認のユースケースを FastAPI のルーティングから分け、内側のエンティティ (取引先・契約・請求書・明細・入金・突合結果・監査ログ, qa-024) は FastAPI と PostgreSQL に依存しない。非同期の突合ジョブ (qa-006, qa-025) も同じユースケースを呼ぶ。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |
| data-access | Robert C. Martin — Clean Architecture | 永続化を境界の外側へ追い出し interface adapter で隔離する | Clean Architecture — gateways/repositories boundary | 2026-07-12 | 同時編集で後勝ちの上書きを起こさない (qa-025) ため、請求書の更新は版番号を条件にした更新にし、版が合わなければ保存を止める。重い突合は冪等キー付きのジョブにして二重に走らせない (qa-025)。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1, G2

#### 主たる接地根拠: `qa-006`

**問**

バックエンド（backend）× Web の要件は?

**答**

Python/FastAPI。REST + 非同期ジョブ(キュー)。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 原本 (orig-spec-state.json、ファイル更新 2026-10-05) に当初から記録されていたシナリオ上の利用者回答。対話の逐語ログと回答時刻は残っていない。問は開いた問 (選択肢なし) で、代替案を提示した記録は無い (basis の user-decision は原本の値で、writer は記録済みの basis を上書きできない))

#### 裏付け質疑: `qa-018`

**問**

あらかじめ決まっている制約があれば教えてください。

**答**

社内規程で、社内 k8s で動かし、ログインは社内 IdP の OIDC を使うことになっている。バックエンドは保守体制に合わせて Python/FastAPI にする。CI/CD は会社で契約している GitHub Actions を使う。データベースは情報システム部が提供する PostgreSQL を使う。提供されている版は 15 と 16 の 2 つ。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R0-foundation の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:45Z)

#### 裏付け質疑: `qa-024`

**問**

このシステムで扱う主なデータを、互いのつながりがわかるように教えてください。

**答**

取引先ごとに契約があり、契約から毎月の請求書を作る。請求書は複数の請求明細を持つ。入金は請求書に消し込む。突合は月ごとに行い、食い違いを記録する。確定した請求書は書き換えず、直すときは取り消しの請求書と新しい請求書を発行する (赤黒訂正)。すべての操作は監査ログに残し、監査ログは追記だけで、消したり書き換えたりしない。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:45Z)

#### 裏付け質疑: `qa-025`

**問**

画面とサーバのあいだでやり取りする主な操作を教えてください。

**答**

請求書の一覧と登録・更新、突合の実行と結果の取得、確定の承認、監査ログの検索。一覧は件数が多いのでページに分けて取得する。2 人が同じ請求書を同時に直したときは、後から保存した方を上書きせずに止めてほしい。突合のような重い処理は裏で動かし、同じ処理が二重に走らないようにしたい。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:52Z)

## To-Be / Delta

> 本章の**規範**。上位概念 (要件定義書 U3 ゴール / U4 目標 / U9 具体的やりたいこと) を本章の serves_goals で絞り込んだ射影であり、設計知識 card (非規範の参考資料) とは役割が異なる。As-Is (現行実装の姿) は spec-state.json の管轄外のため本節では断定せず、到達点と、その到達を判定する観測点だけを規範として置く。

### 到達すべき状態 (To-Be)

- **G1**: 請求・監査データを単一の信頼できる情報源へ統合する
- **G2**: 主要業務動線を Web だけで完結できるようにする

### 受入条件 (Delta の判定点)

| 目標 | 到達点 | 達成の観測点 (measure) |
|---|---|---|
| O1 | 請求漏れをシステムが自動で検知する | 締め後に残る請求漏れ 月次 0 件 (稼働後最初の月次締めから計測) |
| O2 | 月末の突合を表計算に書き出さずに終える | 月末 3 営業日の表計算への書き出し 0 回 (稼働後最初の月次締めから計測) |

### 本章がかなえる具体的やりたいこと (U9)

- **I1**: 請求・監査データを日次でバックアップする
- **I2**: 突合画面は未突合件数と食い違いのある取引先を先頭に出し、食い違いを金額の大きい順に並べ、一致済みの明細は畳む
- **I3**: 確定した請求書は書き換えず赤黒訂正で直し、監査ログは追記のみとする

### 本章に効く確定意思決定

- **D1**: データベースに使う PostgreSQL の版をどれにするか (情報システム部の提供版は 15 と 16, qa-018)
  - 採択: PostgreSQL 16 (情報システム部が提供する版) (`pg16`)
  - 目的適合: G1 (単一の信頼できる情報源) に要るトランザクション・制約・バックアップの機能を満たす
  - 採択の接地根拠: `qa-031`
- **D2**: 画面の作り方をどの方式にするか
  - 採択: React + TypeScript の SPA (`react-spa`)
  - 目的適合: G2 を満たす。突合の画面で頁を読み直さずに並べ替えと行の修正ができる
  - 採択の接地根拠: `qa-032`
- **D3**: 社内 IdP の OIDC で得たトークンを、どこで持ち、API へどう送るか
  - 採択: バックエンド (FastAPI) がトークンを持ち、ブラウザには cookie のセッションだけを渡す方式 (`bff-session`)
  - 目的適合: G1 (請求・監査データの単一の情報源) の信頼を、トークンをブラウザに出さないことで支える。8 時間のセッション (qa-002) と、IdP でのアカウントの無効化 (qa-026) をサーバ側で扱える
  - 採択の接地根拠: `qa-034`

## 適用された設計知識

> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。

### 本章での適用

clean-architecture の依存の規則に従い、ユースケース (請求書の登録・更新、突合の実行、確定の承認、監査ログの検索, qa-025) を FastAPI と PostgreSQL から切り離す。api-design-patterns に従い、一覧は不透明なカーソルでページに分け、請求書の更新は ETag と If-Match で版を照合して後勝ちの上書きを止め、突合ジョブの起動には冪等キーを付けて二重実行を防ぐ (いずれも qa-025)。ddd に従い、境界づけられたコンテキストを請求と監査の 2 つに分け、監査は請求のドメインイベント (登録・更新・確定・赤黒訂正) を受けて追記する (qa-024)。

- (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない) / 記録時刻: 2026-10-12T00:17:23Z)

### Domain-Driven Design — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/ddd.md`

#### 目的

businessの重要なruleと用語をmodel/code/会話で一致させ、複雑性を適切な境界へ閉じ込め、継続的な学習をsoftwareへ反映する。

#### 解決する問題

- 仕様語、画面語、DB列、code名がずれ、変更時に意味を再解釈する。
- 異なる業務文脈の同名概念を一modelへ押し込み、巨大で矛盾したmodelになる。
- invariantとtransaction ownerが不明で、どこからでもdataを変更できる。
- legacy codeのtechnical構造がbusiness capabilityを隠し、改善順を決められない。

#### 適用条件

- rule、例外、用語、状態遷移が多く、domain expertとの継続的なmodel学習が価値を持つ。
- team/部門ごとに言葉やownershipが異なり、integrationで翻訳が必要。
- core domainの差別化がsystemの本質的目的に直結する。

#### 非適用条件

- 単純CRUD、汎用supporting機能、既製serviceで十分なgeneric subdomain。
- domain expertへアクセスできず、用語とruleを検証するfeedback loopを作れない段階。
- bounded contextをservice数へ機械変換する目的。monolith内moduleでも境界は成立する。

#### トレードオフ・失敗モード

- workshop、model、mapping、専門語彙の維持に継続的な時間が必要。
- aggregateを大きくしすぎてlock/latencyを増やす、細かくしすぎてinvariantをeventual consistencyへ漏らす。
- 「Repository/Entity」等のpattern名だけ採用したanemic modelになり、business ruleがserviceへ散る。
- bounded contextを組織図やDB tableから決め、実際の言語・capability境界を検証しない。
- eventを事実でなくcommandとして命名し、ordering/idempotency/failure recoveryを設計しない。

#### goalへの寄与

- U1-U9の語彙をmodelへ接続し、goalがどのcontext/capability/invariantで実現されるかを示す。
- core domainへ設計投資を集中し、generic領域は無料/低コストserviceや標準実装も比較対象にできる。
- refactoringは一括rewriteでなく、重要なbusiness rule周辺からstrangler/bubble context等で境界を育てる。

---

### Clean Architecture — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/clean-architecture.md`

#### 目的

変化しやすいUI、DB、framework、外部サービスから、長く保持したい業務ルールとuse caseを隔離し、技術交換やテストを目的達成の阻害要因にしない。

#### 解決する問題

- 業務ルールがcontroller/ORM/UI lifecycleへ埋まり、単体で検証できない。
- 外部技術変更が内側のuse caseまで波及し、置換費用を予測できない。
- 入出力形式やvendor型が境界を越え、責務と所有者が曖昧になる。

#### 適用条件

- business ruleが外部I/Oより長寿命で、UI/DB/providerの変更可能性がある。
- 複数delivery channelや外部integrationから同じuse caseを再利用する。
- 重要なpolicyを高速・決定論的にテストする価値が、境界導入費を上回る。

#### 非適用条件

- 寿命の短い検証用prototypeで、交換可能性より学習速度が明確に優先される。
- domain ruleがほぼ無い単純変換scriptで、port/adapterが実質的な抽象を生まない。
- 外部製品そのものがsystemの目的で、抽象化すると必要機能が失われる。ただしsecurity/audit boundaryは別途必要。

#### トレードオフ・失敗モード

- 境界、DTO、mapping、dependency injectionの量が増え、小規模systemでは認知負荷が先行する。
- 「4層を作ること」が目的化すると、変化軸のないinterfaceやpass-through use caseが増える。
- domain modelを万能化してdelivery固有の制約を隠すと、現実のlatency/transaction/error semanticsを見失う。
- portを外側が定義したりinner layerがORM型を返したりすると、名前だけcleanな依存逆転になる。

#### goalへの寄与

- `essential_purpose`に直結するpolicyを外部詳細から守り、goal達成ロジックの検証を速くする。
- 制約に「vendor lock-in低減」「複数platform」「高い変更頻度」がある場合、変更範囲と移行riskを局所化する。
- 適用判断は「何層あるか」でなく、守るgoal、予想される変更、boundary testで観測する。

---

### API Design Patterns — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/api-design-patterns.md`

#### 目的

consumerとproviderの独立変更を支える安定した契約を作り、再試行、失敗、並行更新、pagination、evolutionを予測可能にする。

#### 解決する問題

- resource/operationの意味、error、null、time、identifierがendpointごとに揺れる。
- timeout後の再試行で二重処理が起き、clientが成功/失敗を判断できない。
- collection増大や並行更新でoffset paginationと全件responseが破綻する。
- version/evolution方針がなく、provider変更がconsumerを突然壊す。

#### 適用条件

- 複数client/team/organizationが独立releaseで同じservice boundaryを利用する。
- network failureとretryが通常事象で、operation結果の重複や不明状態を制御する必要がある。
- contractの長期互換性とobservabilityが局所的な実装簡潔性より重要。

#### 非適用条件

- 同一process内のprivate callで、network boundaryや独立versioningが存在しない。
- hard real-time stream、双方向session、巨大event flowなど、request/response RESTが問題形状に合わない。
- 単純CRUD表面化がdomain invariantを迂回させる場合。use-case operationまたは別interaction modelを選ぶ。

#### トレードオフ・失敗モード

- version、idempotency ledger、schema governance、compatibility testに運用費がかかる。
- 「名詞URL」だけ守ってtransaction、authorization、error semanticsを設計しない表層RESTになる。
- offset paginationは簡単だが大規模/更新中datasetで遅延・重複・欠落を起こす。
- idempotency keyのscope/TTL/payload bindingが曖昧だと、別requestを誤って同一視する。
- breaking changeを新versionで逃がし続けると、複数version保守とsecurity patch負担が増える。

#### goalへの寄与

- mobile/web/desktop間で一貫したbusiness capabilityを共有し、platform別再実装を減らす。
- reliability goalにはretry-safe operationと明示的error、delivery goalにはcontract testとadditive evolutionを結ぶ。
- 選択はAPI様式の流行でなく、consumer、latency、consistency、offline、security、cost constraintsへの適合で評価する。

---

### 確定判断ごとの原則採否

- 確定内容 `qa-006` (対応セル: web)
  - 確定要件: 「Python/FastAPI。REST + 非同期ジョブ(キュー)。」 (正本: 本章「確定内容 (質疑録)」の `qa-006`)
  - 設計解釈の記録経路: `unrecorded`
  - 設計原則の採否根拠: (未記録 — qa_log[].design_applications を writer 経由で補完すること)
- 資するゴール: G1, G2

## 最新ドキュメント出典

| 対象 | バージョン | 公式発行元 | 出典URL | 取得 | 最新確認 |
|---|---|---|---|---|---|
| fastapi | 0.162.0 | FastAPI (Sebastián Ramírez / tiangolo) (fastapi.tiangolo.com) | https://fastapi.tiangolo.com/release-notes/ | 2026-10-31T14:11:32Z | 2026-10-31T14:11:32Z |
