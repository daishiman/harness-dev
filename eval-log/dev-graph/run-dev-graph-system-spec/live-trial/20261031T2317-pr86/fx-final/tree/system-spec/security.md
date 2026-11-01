---
status: confirmed
category: security
aggregate: 確定
spec_cells: [security.web, security.mobile, security.tablet, security.desktop-windows, security.desktop-linux, security.desktop-macos]
serves_goals: [G1]
---

# セキュリティ (security)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-004。裏付け質疑 (`qa_refs`): `qa-030`, `qa-037` — 本章の「確定内容 (質疑録)」へ接地根拠として併記。資するゴール: G1 |
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
| security | OWASP ASVS + Secrets Management Cheat Sheet | 脅威モデル・入力検証・暗号化・監査ログの上流指針 | https://owasp.org/www-project-application-security-verification-standard/ | 2026-07-12 | qa-030 の脅威ごとに対策を対応づける: 確定金額の書換えには確定後の更新を禁じ赤黒訂正だけを許す (qa-024)、残ったアカウントには IdP 連携での無効化 (qa-026)、権限の設定ミスには担当取引先による行単位の制限とロール割当ての監査ログ記録、監査ログの改ざんには追記のみの保存と削除権限を誰にも与えないこと。通信は TLS 1.3、入力は検証する (qa-004)。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1

#### 主たる接地根拠: `qa-004`

**問**

セキュリティ（security）× Web の要件は?

**答**

TLS1.3・入力検証・監査ログ・OWASP Top10 受動対策。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 原本 (orig-spec-state.json、ファイル更新 2026-10-05) に当初から記録されていたシナリオ上の利用者回答。対話の逐語ログと回答時刻は残っていない。問は開いた問 (選択肢なし) で、代替案を提示した記録は無い (basis の user-decision は原本の値で、writer は記録済みの basis を上書きできない))

#### 裏付け質疑: `qa-030`

**問**

このシステムで、起きると困る不正や事故を教えてください。

**答**

確定した請求金額が書き換えられること。退職者や異動者のアカウントが残って使われること。権限の設定ミスで、担当外の取引先の請求を見たり直したりできてしまうこと。監査ログが消されたり改ざんされたりすること。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:53Z)

#### 裏付け質疑: `qa-037`

**問**

D3 で決めた cookie のセッションについて、状態を変える要求を利用者になりすまして送られること (CSRF) をどう防ぐかを選んでください。(1) cookie に SameSite=Lax・HttpOnly・Secure を付け、SameSite の属性だけで防ぐ (2) (1) の属性に加えて、状態を変える要求 (POST・PUT・PATCH・DELETE) には、サーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にする (3) (1) の属性に加えて、double-submit cookie (cookie と要求のヘッダに同じ乱数を入れて突き合わせる) を使う。どれも採らない、別の方式と比べる、決めずに保留する、も選べます。

**答**

(2) にする。cookie には HttpOnly・Secure・SameSite=Lax を付ける。状態を変える要求 (POST・PUT・PATCH・DELETE) には、サーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にし、無いか合わない要求は拒否する。SameSite の属性だけに頼らず、セッションをサーバ側に持つ (D3) ので、トークンもサーバ側で突き合わせたい。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-13, sysspec7): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。orchestrator がシナリオ上の利用者の発言として書いた既定値で、実利用者との対話ではない。R2 のセル補充で、問の中に代替案を推奨の印を付けずに並べ、利用者が選んだ、というシナリオ (decisions には足していない)。sysspec5 の評価で、D3 の前提の CSRF 対策とセッションの保存先に利用者の決定が無いことが指摘された。sysspec6 ではこれを orchestrator の既定値 (basis は agent-inference) として足し、その評価で matrix_coverage が FAIL になったため、team-lead の指示 (2026-10-13) で、qa-034〜036 と同じく利用者の発言の turn (basis は user-decision) に変えた。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T17:34:57Z)

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

## 適用された設計知識

> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。

### 本章での適用

secure-by-design の脅威モデリングに従い、守る対象 (確定金額と監査ログ) と起きると困る事象 (qa-030 の 4 つ) を先に並べてから対策を選んだ。多層防御として、認証 (社内 IdP の OIDC)・認可 (ロールと担当取引先)・記録 (追記のみの監査ログ) の 3 層のどれか 1 つが破れても、確定金額を黙って書き換えられないようにする。データのライフサイクルでは、確定した請求書と監査ログを消さないことを前提にする (qa-024)。

- (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない) / 記録時刻: 2026-10-12T00:17:23Z)

### Secure by Design — deep knowledge card

- 出典カード: `ref-system-design-knowledge/references/secure-by-design.md`

#### 目的

利用者の注意や運用後のpatchへ安全性を押し付けず、systemのdefault、architecture、development lifecycleに安全な結果を組み込み、被害可能性と復旧費を下げる。

#### 解決する問題

- 認証・認可・data protectionが後付けで、business flowと矛盾する。
- defaultが過大権限/公開状態で、利用者の完全な設定に安全性が依存する。
- 単一防御の突破で全面侵害になり、検知・封じ込め・復旧の証拠が無い。
- dependency、secret、build、releaseの供給chain riskが製品境界外として放置される。

#### 適用条件

- identity、個人/機密data、金銭、外部入力、admin操作、multi-tenant boundaryを扱う全system。
- compromise時の影響がgoal、法規、信頼、運用継続を損なう。
- vendor/serviceを使う場合も、共有責任とfailure/exit planを明示できる。

#### 非適用条件

- security自体が不要なsystemは原則ない。asset/threatが極小ならcontrolを軽量化できるが、根拠付きrisk acceptanceが必要。
- controlがthreatを減らさず、accessibility/availability/safetyを重大に損なう場合はそのcontrolを採用しない。代替・補償統制を設計する。
- checklist準拠だけでproject固有のtrust boundaryとabuse caseを置き換えない。

#### トレードオフ・失敗モード

- friction、latency、delivery費、運用負荷が増えるため、risk reductionと明示的に釣り合わせる。
- security theaterとしてcontrol数だけ増やし、owner、evidence、responseを持たない。
- fail closedを無差別適用してavailability/safety incidentを起こす。degraded modeとbreak-glass監査が必要。
- secretを隠しても過大権限や長期credentialを残す、暗号化してもkey lifecycleを設計しない等の局所最適。
- free tier製品を価格だけで選び、audit、export、retention、MFA、incident support不足を見落とす。

#### goalへの寄与

- stakeholderの安全・信頼・継続性をsuccess criteriaへ変換し、threat/control/evidenceをgoalへトレースする。
- security controlは「導入済み」ではなく、阻止/検知/復旧時間、権限範囲、data exposureで効果を測る。
- 予算0制約でも、secure default、最小data、短命credential、標準機能、open-source検査を優先し、残余riskを隠さない。

---

### 確定判断ごとの原則採否

- 確定内容 `qa-004` (対応セル: web)
  - 確定要件: 「TLS1.3・入力検証・監査ログ・OWASP Top10 受動対策。」 (正本: 本章「確定内容 (質疑録)」の `qa-004`)
  - 設計解釈の記録経路: `unrecorded`
  - 設計原則の採否根拠: (未記録 — qa_log[].design_applications を writer 経由で補完すること)
- 資するゴール: G1

## 最新ドキュメント出典

- (このカテゴリに割り当てた取得済みドキュメントなし。全体出典は index.md 参照)
