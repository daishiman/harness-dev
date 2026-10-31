---
status: confirmed
category: auth
aggregate: 確定
spec_cells: [auth.web, auth.mobile, auth.tablet, auth.desktop-windows, auth.desktop-linux, auth.desktop-macos]
serves_goals: [G1]
---

# 認証(ログイン) (auth)

- カテゴリ集約状態: **確定**
- 章確定マーカー: `status: confirmed`

## カテゴリ別収集状態

| プラットフォーム | 状態 | 根拠 |
|---|---|---|
| Web (web) | 確定 | 確定質疑: qa-002。裏付け質疑 (`qa_refs`): `qa-018`, `qa-026`, `qa-034`, `qa-037`, `qa-038` — 本章の「確定内容 (質疑録)」へ接地根拠として併記。資するゴール: G1 |
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
| authentication | OWASP ASVS + Secrets Management Cheat Sheet | 認証方式・セッション・資格情報/シークレット/API キーの取扱いの上流指針 | https://owasp.org/www-project-application-security-verification-standard/ | 2026-07-12 | 認証は社内 IdP の OIDC に委ね (qa-002, qa-018)、本システムはパスワードを持たない。OIDC のトークンはバックエンドが持ち、ブラウザには cookie のセッションだけを渡す (D3, qa-034)。セッションは Pod のメモリに置かず、D1 の PostgreSQL 16 の表に保存して、Pod の再起動や複数の replica の間でもログインが切れないようにする。有効期限は 8 時間で (qa-002)、期限切れは使えなくして定期的に消し、ログアウトではすぐに無効にする (qa-038)。IdP でアカウントが無効になれば入れなくなる (qa-026)。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |
| security | OWASP ASVS + Secrets Management Cheat Sheet | 脅威モデル・入力検証・暗号化・監査ログの上流指針 | https://owasp.org/www-project-application-security-verification-standard/ | 2026-07-12 | 認可は既定で拒否し、ロールごとに許す操作だけを列挙する (qa-026)。セッションの cookie には HttpOnly・Secure・SameSite=Lax を付け、状態を変える要求 (POST・PUT・PATCH・DELETE) にはサーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にして、無いか合わない要求は拒否する (qa-037)。OIDC のクライアントシークレットはリポジトリに置かず、k8s の Secret で渡す (シークレット管理)。 (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない)) |

## 確定内容 (質疑録)

> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の逐語である。ここに現れない主張は本章の確定内容ではない。

### Web (web)

- 資するゴール: G1

#### 主たる接地根拠: `qa-002`

**問**

認証(ログイン)（auth）× Web の要件は?

**答**

OIDC(社内 IdP)+ ロールベース認可。セッションは 8h。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 原本 (orig-spec-state.json、ファイル更新 2026-10-05) に当初から記録されていたシナリオ上の利用者回答。対話の逐語ログと回答時刻は残っていない。問は開いた問 (選択肢なし) で、代替案を提示した記録は無い (basis の user-decision は原本の値で、writer は記録済みの basis を上書きできない))

#### 裏付け質疑: `qa-018`

**問**

あらかじめ決まっている制約があれば教えてください。

**答**

社内規程で、社内 k8s で動かし、ログインは社内 IdP の OIDC を使うことになっている。バックエンドは保守体制に合わせて Python/FastAPI にする。CI/CD は会社で契約している GitHub Actions を使う。データベースは情報システム部が提供する PostgreSQL を使う。提供されている版は 15 と 16 の 2 つ。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R0-foundation の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:45Z)

#### 裏付け質疑: `qa-026`

**問**

誰がどの操作をできるようにするかを教えてください。

**答**

請求担当は自分の担当取引先の入力と突合ができる。確定の承認は経理チームのリーダーだけができる。内部監査室はすべてを閲覧できるが、変更はできない。情報システム部は運用だけを行い、請求データは見られない。退職や異動で社内 IdP のアカウントが無効になったら、このシステムにも入れなくなるようにする。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R2 のセル補充の開いた問 (選択肢なし、代替案の提示なし)。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T00:16:52Z)

#### 裏付け質疑: `qa-034`

**問**

社内 IdP の OIDC で得たトークンを、どこで持ち、API へどう送るかを選んでください。(1) バックエンド (FastAPI) がトークンを持ち、ブラウザには cookie のセッションだけを渡す方式 (2) SPA が PKCE 付きの認可コードフローでトークンを取り、ブラウザのメモリだけに置いて Authorization: Bearer で API へ送る方式。どちらも採らない、別の方式と比べる、決めずに保留する、も選べます。

**答**

(1) バックエンドがトークンを持つ方式にする。8 時間のセッション (qa-002) と、IdP でアカウントが無効になったときの締め出し (qa-026) をサーバ側の一か所で扱いたいし、トークンをブラウザに置きたくない。CSRF 対策とセッションの保存先は、この方式の前提として設計に入れてほしい。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-12, sysspec5): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。R5: 問の外で比較表 (decisions D3 の options bff-session / spa-pkce-memory を同じ比較軸で並べたもの) と AI の推奨 (参考: bff-session。理由・注意点・信頼度・確認日時つき) を示した後、推奨の印を付けない問で選択を依頼した、というシナリオ。sysspec4 の評価で、D2 が auth 章へ送った OIDC のトークンの扱いに利用者の決定が無いことが指摘されたため、team-lead の指示 (2026-10-12) で足した。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T07:38:46Z)

#### 裏付け質疑: `qa-037`

**問**

D3 で決めた cookie のセッションについて、状態を変える要求を利用者になりすまして送られること (CSRF) をどう防ぐかを選んでください。(1) cookie に SameSite=Lax・HttpOnly・Secure を付け、SameSite の属性だけで防ぐ (2) (1) の属性に加えて、状態を変える要求 (POST・PUT・PATCH・DELETE) には、サーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にする (3) (1) の属性に加えて、double-submit cookie (cookie と要求のヘッダに同じ乱数を入れて突き合わせる) を使う。どれも採らない、別の方式と比べる、決めずに保留する、も選べます。

**答**

(2) にする。cookie には HttpOnly・Secure・SameSite=Lax を付ける。状態を変える要求 (POST・PUT・PATCH・DELETE) には、サーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にし、無いか合わない要求は拒否する。SameSite の属性だけに頼らず、セッションをサーバ側に持つ (D3) ので、トークンもサーバ側で突き合わせたい。

- (根拠の性質: 利用者が代替案を見たうえで明示選択した決定 / 出所: live-trial fixture 再構築 (orchestrator 補助, 2026-10-13, sysspec7): シナリオ上の利用者発言として記録した。実利用者との対話ログではない。orchestrator がシナリオ上の利用者の発言として書いた既定値で、実利用者との対話ではない。R2 のセル補充で、問の中に代替案を推奨の印を付けずに並べ、利用者が選んだ、というシナリオ (decisions には足していない)。sysspec5 の評価で、D3 の前提の CSRF 対策とセッションの保存先に利用者の決定が無いことが指摘された。sysspec6 ではこれを orchestrator の既定値 (basis は agent-inference) として足し、その評価で matrix_coverage が FAIL になったため、team-lead の指示 (2026-10-13) で、qa-034〜036 と同じく利用者の発言の turn (basis は user-decision) に変えた。answered_at は本記録の作成時刻 / 回答時刻: 2026-10-12T17:34:57Z)

#### 裏付け質疑: `qa-038`

**問**

D3 の方式でサーバ側に持つセッションを、どこに保存するかを選んでください。(1) 各 Pod のメモリに置く (2) 情報システム部が提供している PostgreSQL 16 (D1) の表に置く (3) Redis などのセッション用の新しい保存基盤を足して置く。あわせて、セッションをどれだけの期間で無効にするか (有効期限と、ログアウトのときの扱い) を教えてください。どれも採らない、別の方式と比べる、決めずに保留する、も選べます。

**答**

(2) PostgreSQL 16 (D1) の表に保存する。Pod のメモリには置かず、Pod の再起動や複数の replica でもログインが切れないようにする。Redis などの新しい保存基盤は足さない。有効期限は qa-002 のとおり 8 時間で、期限切れは使えなくして定期的に消す。ログアウトではすぐに無効にする。

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

secure-by-design の最小権限と既定拒否を qa-026 のロールへ当てた。ロールごとに許す操作を列挙し、列挙に無い操作は拒否する: 請求担当は担当取引先の入力と突合、リーダーは確定の承認、内部監査室は閲覧のみ、情報システム部は請求データに触れない。アカウントの寿命は社内 IdP に従わせ、退職・異動で無効になったアカウントは本システムでも使えない (qa-026。qa-030 の『残ったアカウント』への対策)。D3 (qa-034) でバックエンドがトークンを持ち、ブラウザには cookie のセッションだけを渡す方式に決まったので、既定で安全 (secure defaults) と多層防御をブラウザとの境界にも当てる: セッションの cookie には HttpOnly・Secure・SameSite=Lax を付け、状態を変える要求 (POST・PUT・PATCH・DELETE) にはサーバがセッションごとに発行する CSRF トークン (synchronizer token) を必須にして、無いか合わない要求は拒否する (qa-037)。データのライフサイクルとして、セッションは Pod のメモリに置かず、D1 の PostgreSQL 16 の表に保存して、Pod の再起動や複数の replica の間でもログインが切れないようにする。有効期限は 8 時間で (qa-002)、期限切れは使えなくして定期的に消し、ログアウトではすぐに無効にする (qa-038)。

- (根拠の性質: アシスタントの推定 (利用者確認も検証可能な出典も経ていない) / 記録時刻: 2026-10-12T17:34:58Z)

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

- 確定内容 `qa-002` (対応セル: web)
  - 確定要件: 「OIDC(社内 IdP)+ ロールベース認可。セッションは 8h。」 (正本: 本章「確定内容 (質疑録)」の `qa-002`)
  - 設計解釈の記録経路: `legacy_backfill` (`set-qa-design-applications`)
  - 原則 (`plugins/system-spec-harness/skills/ref-system-design-knowledge/references/secure-by-design.md#中核概念`): 最小権限と既定拒否
    - 採否: `applied`
    - 章固有の根拠: qa-002の社内IdPのOIDCとロール認可・8時間セッションを前提に、qa-026の請求担当・リーダー・内部監査・情報システム部の操作権限を許可表へ分ける。列挙されない操作は拒否し、画面表示だけでなくAPI側でも担当取引先の範囲を判定する設計解釈とする。
    - トレードオフ:
      - IdP停止の影響を受けるため、障害時の扱いと監査が必要。
      - 細粒度の認可は権限表と境界テストの保守負担を伴う。
- 資するゴール: G1

## 最新ドキュメント出典

- (このカテゴリに割り当てた取得済みドキュメントなし。全体出典は index.md 参照)
