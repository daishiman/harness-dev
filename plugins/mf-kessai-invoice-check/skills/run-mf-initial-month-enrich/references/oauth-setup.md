# MFクラウド請求書 API v3 — OAuth2 アクセストークン取得手順（取得担当向け・正本）

> **位置づけ**: これは任意スキル `run-mf-initial-month-enrich`（`初回契約月` の一括エンリッチ・
> 取得担当 1 名のみ）で使う OAuth トークン取得手順の**正本**です。コードはプラグインに同梱・配布
> されますが、**実行には本書で取得する OAuth トークンが必須**で、それを持つ取得担当だけが実行します
> (一般メンバーは不要)。スキルの使い方は親ディレクトリの `SKILL.md` を参照してください。
>
> 「初回契約月」の真値(2026-04 より前を含む最古発行月)を取得するために、別製品
> **MFクラウド請求書 (MoneyForward Cloud Invoice)** の API を使う。MF掛け払い (Kessai) とは
> 別プロダクト・別認証で、**APIキー方式は無く OAuth2 のみ**。本書はそのトークン取得の正本手順。

## 0. 用語と全体像

| 項目 | MF掛け払い (既存) | MFクラウド請求書 (本書) |
|---|---|---|
| 製品 | 与信・保証 (Kessai) | 請求書の発行 (Invoice) |
| API ベースURL | `https://api.mfkessai.co.jp/v2` | `https://invoice.moneyforward.com/api/v3` |
| 認証 | APIキー (`apikey:` ヘッダ・静的) | **OAuth2** (`Authorization: Bearer`・動的) |
| 認可サーバ | — | `https://api.biz.moneyforward.com` |
| Keychain | `mfkessai-api-key.<keychain-prefix>` | `mf-invoice-oauth.<keychain-prefix>` (token一式をJSONで保存) |

OAuth2 は **初回1回だけ**ブラウザ同意が必要。以後は `refresh_token` で access_token を自動更新でき、
無人運用 (cron / 集中取得) が成立する。**取得担当 (runner) 1か所**で取得し、チームメンバーは
認証情報を持たず Notion を見るだけ (= 集中取得型)。

### 環境変数 (スクリプト経路で export する 4 つ・正本)

`mf_invoice_oauth.py` はこの 4 つを env から読む (STEP1 で取得した値を入れる)。値の意味はここを正本とする:

| 環境変数 | 意味 |
|---|---|
| `MF_INVOICE_CLIENT_ID` | アプリ登録で得た Client ID |
| `MF_INVOICE_CLIENT_SECRET` | アプリ登録で得た Client Secret (秘密。Git/ログに残さない) |
| `MF_INVOICE_REDIRECT_URI` | アプリ登録時の Callback URI と完全一致させる値 |
| `MF_INVOICE_SCOPE` | 要求 scope (参照のみは `mfc/invoice/data.read`・空白区切り) |

## 1. STEP 1 — アプリ登録 (Client ID / Client Secret の取得)

1. MFクラウドにログイン → 右上メニュー等から **「アプリポータル」** を開く
   (または各プロダクトの「API連携(開発者向け)」→「**APIの利用を開始する**」ボタンでアプリポータルへ遷移)
2. 新規アプリケーションを作成し、以下4点を設定/取得する:
   - **Client ID** … 取得して控える
   - **Client Secret** … 取得して控える (秘密。Git/フロントに置かない)
   - **Scopes** … `mfc/invoice/data.read` を選択 (**参照のみで十分**。発行漏れチェックは読み取り専用)
   - **Callback URI (= redirect_uri)** … 例 `http://localhost:12345/callback` を登録
     (ローカルに受け側サーバが無くても、ブラウザのアドレスバーから `?code=` を手で拾えるので可)

> Scope の意味: `mfc/invoice/data.read` = 参照のみ (GET) / `mfc/invoice/data.write` = 参照+更新
> (GET/POST/PUT/DELETE)。本用途は **read のみ** (最小権限)。

## 2. STEP 2 — 認可エンドポイントで「認可コード」を取得 (ブラウザ・初回のみ)

以下URLをブラウザで開く (`${ClientID}` / `${RedirectURI}` を STEP1 の値へ置換):

```
https://api.biz.moneyforward.com/authorize?response_type=code&client_id=${ClientID}&scope=mfc/invoice/data.read&redirect_uri=${RedirectURI}
```

1. マネーフォワード ID でログイン
2. 連携先の事業者・アプリ・要求権限が表示される → 内容を確認し **「許可」**
3. STEP1 で登録した redirect_uri に転送され、URL に `?code=XXXXXXXX` が付く
   → この **code を控える** (ページがエラー表示でもアドレスバーの `code=` をコピーすればよい)

> ⚠️ **認可コードの有効期限は 10 分**。取得したら速やかに STEP3 を実行する。

## 3. STEP 3 — 認可コードをアクセストークンに交換

**第一推奨はスクリプト経路** `mf_invoice_oauth.py --exchange`。取得した token は Keychain へ
**stdin 経由で保存**するため、refresh_token / client_secret がシェル履歴に残らない (下記 STEP4 の
ヘルパー参照)。env を export 済みなら 1 コマンドで交換+保存まで完了する:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py" --exchange '<AuthCode>'
```

<details><summary>手動 curl で叩く場合 (通常は上のスクリプト経路を使う)</summary>

トークンエンドポイントは **HTTP Basic 認証** (`-u ClientID:ClientSecret`) を使う:

```bash
curl --request POST "https://api.biz.moneyforward.com/token" \
  -u "${ClientID}:${ClientSecret}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=${AuthCode}" \
  -d "redirect_uri=${RedirectURI}"
```

> ⚠️ 手動 curl は `client_secret` がシェル履歴に残るため、通常はスクリプト経路 (`--exchange`) を使う。
</details>

成功レスポンス例:

```json
{
  "access_token": "xxxxxxxx",
  "refresh_token": "yyyyyyyy",
  "scope": "mfc/invoice/data.read",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

- `access_token` … API 呼び出しに使う。**有効期限 1時間 (3600秒)**
- `refresh_token` … access_token の自動更新に使う (長命)

## 4. STEP 4 — Keychain へ保存 (集中取得型・取得担当マシン1か所)

**第一推奨はヘルパー** `mf_invoice_oauth.py`。`--exchange` が token 一式を **stdin 経由で** Keychain へ
書き込むため、refresh_token / client_secret が argv (シェル履歴) に残らない。env (上の正本表) を
export してから STEP2〜4 を一気通貫で実行できる:

```bash
export MF_INVOICE_CLIENT_ID=...  MF_INVOICE_CLIENT_SECRET=...
export MF_INVOICE_REDIRECT_URI='http://localhost:12345/callback'
export MF_INVOICE_SCOPE='mfc/invoice/data.read'
SK="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py"
python3 "$SK" --authorize-url      # 認可URL表示→ブラウザ同意→code取得
python3 "$SK" --exchange '<code>'  # token取得+Keychain保存 (stdin保存=安全)
python3 "$SK" --smoke              # refreshして /partners 疎通確認
```

<details><summary>手動で Keychain へ保存する場合 (通常はヘルパーを使う)</summary>

トークン一式を JSON で Keychain に保存する (本リポジトリの想定サービス名):

```bash
security add-generic-password -U -s mf-invoice-oauth.<keychain-prefix> -a <keychain-prefix> -w \
  '{"client_id":"${ClientID}","client_secret":"${ClientSecret}","refresh_token":"${RefreshToken}","access_token":"${AccessToken}","redirect_uri":"${RedirectURI}"}'
```

> ⚠️ `-w '...'` の引数渡しは秘密がシェル履歴に残るため非推奨。通常はヘルパー (`--exchange`・stdin 保存) を使う。
</details>

## 5. STEP 5 — アクセストークンの自動更新 (refresh)

access_token が切れたら refresh_token で再発行する (こちらも Basic 認証):

```bash
curl --request POST "https://api.biz.moneyforward.com/token" \
  -u "${ClientID}:${ClientSecret}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=${RefreshToken}"
```

> refresh_token がローテーション (毎回新しい値を返す) する実装に備え、レスポンスに
> `refresh_token` が含まれたら**新しい値を保存し直す**。集中取得型 (単一利用) なので
> 同時使用による競合は起きない。
>
> ⚠️ **refresh は 1 経路のみ**。cron と手動を同時に回すと refresh_token ローテーションで
> 片方が失効しうる (一方の更新で他方の保持する refresh_token が無効化される)。

## 6. API 呼び出し例 (取得後)

```bash
curl "https://invoice.moneyforward.com/api/v3/partners?page=1&per_page=1" \
  -H "Authorization: Bearer ${AccessToken}" -H "Accept: application/json"
```

本用途で使うエンドポイント:
- `GET /partners` … 取引先一覧 (顧客名で名寄せ → partner_id)
- `GET /billings?partner_id=...` … 請求書一覧 (最古 `billing_date` = 初回請求月 ≈ 初回契約月の推定初期値)

## 7. 早見表

| 項目 | 値 |
|---|---|
| 認可エンドポイント | `https://api.biz.moneyforward.com/authorize` |
| トークンエンドポイント | `https://api.biz.moneyforward.com/token` (Basic認証 `-u ClientID:ClientSecret`) |
| API ベースURL | `https://invoice.moneyforward.com/api/v3` |
| scope (参照のみ) | `mfc/invoice/data.read` |
| scope (参照+更新) | `mfc/invoice/data.write` |
| response_type | `code` |
| grant_type (初回) | `authorization_code` |
| grant_type (更新) | `refresh_token` |
| 認可コード有効期限 | 10 分 |
| access_token 有効期限 | 1 時間 (3600秒) |
| PKCE | 任意 (CODE_VERIFIER 43〜128文字。実装例により使用) |

## 8. つまずきポイント

- **掛け払いの APIキーは使えない**: MFクラウド請求書は OAuth2 専用。掛け払いの 32文字キーを
  Bearer に載せても `401 token_rejected` になる。
- **scope は read を選ぶ**: write を選ぶと不要な更新権限を持つ (最小権限原則に反する)。
- **redirect_uri は登録値と完全一致**: authorize と token の双方で同じ値を渡す。1文字でも違うと失敗。
- **認可コードは10分で失効**: STEP2 取得後すぐ STEP3 を実行。失効したら STEP2 からやり直し。
- **client_secret は秘密**: Keychain / 環境変数で扱い、Git・ログ・チャットに残さない。

## 出典 (一次情報)

- [マネーフォワード クラウド請求書APIについて (scope定義)](https://biz.moneyforward.com/support/invoice/guide/api-guide/a03.html)
- [クラウド請求書API スタートアップガイド](https://biz.moneyforward.com/support/invoice/guide/api-guide/a04.html)
- [開発者サイト STEP 2. アクセストークンを取得する](https://developers.biz.moneyforward.com/en/docs/tutorials/getting-started-api-call-manually/step-2/)
