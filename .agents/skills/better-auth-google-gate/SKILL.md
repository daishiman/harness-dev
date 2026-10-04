---
name: better-auth-google-gate
description: Webアプリのアクセス制御・認証・認可の実装はすべてこのスキルを使う。遮断だけならCloudflare Access、アプリ内identity・role・session・WebSocket等が必要ならBetter Authとする単一決定表の正本。「認証を付けて」「ログイン機能」「Googleでログインできるように」「社員だけに限定」「特定企業だけに公開」「許可リスト/招待制」「メール+パスワード認証」「セッション管理」「ロール・権限管理」「OAuth設定」「redirect_uri_mismatchを直す」「認証のセキュリティレビュー」などの文脈で、ユーザーが「認証」と明示しなくてもログイン要件が含まれるなら必ず読む。特にNext.js App Router＋OpenNext＋D1、Hono、素のWorkersでのBetter Auth＋Google OAuth導入を自動化し、Google Cloud Consoleで人間にしかできない操作は日本語のクリック手順と直リンクへ切り分ける。
---

# Better Auth Google Gate

Cloudflare上のアプリへGoogle認証を導入する。既定はGoogle Workspaceの単一組織限定とし、個人Gmail・別Workspace・グループアドレス・メールエイリアスをログイン主体として扱わない。

## 実行原則

- コード、依存関係、D1、migration、Wrangler、テスト、デプロイは可能な限り自動実行する。
- Google Cloud ConsoleのOAuthアプリ作成、Audience選択、Client ID/Secret取得だけをユーザー作業として切り出す。
- Secret値をチャット、コマンド引数、Git、ログ、`wrangler.jsonc`、`NEXT_PUBLIC_*`へ出さない。
- 既存コードと設定を先に調査し、既存認証やユーザー変更を上書きしない。
- Google Workspace制限にはメール末尾比較でなく、Google署名済みIDトークンの`hd` claimをBetter Authの`socialProviders.google.hd`で検証する。
- ルート保護はCookieの存在だけで完了させず、保護ページ、Server Action、API、データアクセス直前で`auth.api.getSession`を検証する。
- Better Authの認証テーブルを記憶で手書きしない。CLIで現在の導入バージョンに対応したスキーマを生成する。
- ユーザーが「実装して」と依頼した場合、検証済みの安全な次工程が残る限り、案内だけで止まらず実行する。
- 通常は事前質問ゼロで、既存コードと設定から認証モデルを再構成し、secretを必要としない実装・テスト・設定ガイドを先に完成させる。複数方式を並べず、証拠に合う安全な構成を1つ選ぶ。

## 0. アクセス制御の単一決定表（正本、INV-4）

v0/v1 の呼び方で分岐させず、**アプリが利用者のidentityを必要とするか**で決める。

| 要件 | 採用方式 | v1 での扱い |
|---|---|---|
| 社内利用者以外をエッジで遮断するだけ。全員が同じデータを使い、アプリ内のidentity・role・session・ユーザー単位データが不要で、WebSocketも使わない | **Cloudflare Access** | そのまま継続可。Better Auth への移行を残課題にしない |
| アプリ内のidentity、role/認可、session、ユーザー単位データのいずれかが必要、または WebSocket を使う | **Better Auth** | v0 から必須。Access だけを一時利用して後送りにしない |

Access で利用者を識別してアプリの所有者・権限に使う折衷案は採用しない。`Cf-Access-Jwt-Assertion` の識別実装が必要となった時点で Better Auth の行を選ぶ。Access の遮断範囲・バージョン別プレビューURL・許可/拒否の実機検証は `cloudflare-secure-deploy` に従う。Access の行を選んだら本Skillの Better Auth 実装手順はここで終了する。

Better Auth の行を選んだ場合は、以降の手順を実行する。

- Auth.js（旧NextAuth）は2025年9月にBetter Authチームへ移管されメンテナンスモードのため、新規では選ばない。
- Google以外のプロバイダー（メール+パスワード、GitHub、Microsoft等）が要件でも、Better Authのプロバイダー追加で同じ骨格のまま対応する。セキュリティ不変条件は共通で適用する。
- 無料枠が最重要要件なら、実装前に`references/free-tier-guardrails.md`と`references/known-pitfalls.md`のD1セッションコストを確認する。

## 1. プロジェクトを判定する

最初に次を実行する。

```bash
node <skill-dir>/scripts/inspect-project.mjs --project <project-root>
```

結果から経路を選ぶ。

| 検出結果 | 読むファイル |
|---|---|
| Next.js + OpenNext + D1 | `references/nextjs-opennext-d1.md`（既定） |
| Honoまたは素のWorker + D1 | `references/hono-workers-d1.md` |
| 既存Better Authあり | 上記該当リファレンス＋`references/security-and-testing.md`で差分監査 |
| Cloudflareでない／DBがD1でない | 勝手に移行せず、現在の構成と変更範囲を説明して確認する |

既存アプリの構成を変更しない。**Next.js + OpenNext + D1 と判定した場合は、APIをNext.js Route Handlerで実装し、Honoを追加しない。** Honoのリファレンスは、Honoまたは素のWorker構成として判定されたプロジェクトだけで使用する。

依存バージョンやCLI構文は変わり得る。実装前に`references/official-sources.md`を読み、公式ドキュメントを再確認する。

## 2. 発見できない値を仮説で補い、成果物を先に作る

コードやWrangler設定から取得できない値は、既存のサービス名、git remote、公開設定、メールドメインから可逆な仮説を置く。仮説値を明記したsecret-freeの実装、テスト、設定ガイドを先に生成し、Google Cloudの本人操作や組織ドメインなど本人しか確定できない境界だけを最後に1回で確認する。

```text
APP_NAME=Google同意画面とサインイン画面に出す名称
PRODUCTION_ORIGIN=https://app.example.com（パス・末尾スラッシュなし）
WORKSPACE_DOMAIN=example.co.jp
LOCAL_ORIGIN=http://localhost:3000（通常は既定値）
```

Client ID、Client Secret、BETTER_AUTH_SECRETの値をチャットで尋ねない。Workspace限定でない要件でも、既定は閉じた構成のままローカル成果物を作り、許可主体とリスクを具体化してから`hd`を外す一点だけを確認する。

## 3. 自動実装する

該当リファレンスに従い、次を実施する。

1. `better-auth`、D1/ORMアダプター、Wrangler/OpenNext依存を既存package managerで導入する。
2. Cloudflare bindingをリクエスト単位で取得し、Better Authインスタンスも同一リクエスト内で共有する。
3. `baseURL`、固定`trustedOrigins`、Google providerの`hd`、`emailVerified`、DB-backed rate limit、`cf-connecting-ip`を設定する。
4. `/api/auth/[...all]`、auth client、サインインUI、サインアウト、保護ページ/APIのサーバー側検証を配線する。
5. 静的SPAアセットを`not_found_handling: "single-page-application"`で配る構成（Hono／素のWorker + 別ビルドSPA）なら、`assets.run_worker_first`に`/api/*`を入れる。入れないとOAuthコールバック（ブラウザのトップレベル遷移=`Accept: text/html`）がSPAフォールバックに横取りされ、Better Authが実行されずログインが完了しない。`fetch`は届くので気づけない。
6. Better Auth CLI用の副作用のない設定を用意し、スキーマを生成する。
7. D1がなければWranglerで作成し、bindingを設定する。migrationをローカル、本番の順で適用する(作成・migration・secret・デプロイの手順と停止条件は`cloudflare-secure-deploy` §2・§10が正本。本Skillでは再定義しない)。
8. `.dev.vars`または`.env`の一方だけを使い、`.gitignore`へ含める。ローカル値はユーザーがエディタへ直接入れるか、安全な対話入力を使う。

`.gitignore`へ`.dev.vars`を追加後、ローカル設定がなければ次で安全に初期化する。

```bash
node <skill-dir>/scripts/setup-local-vars.mjs --project <project-root>
```

このスクリプトはローカル`BETTER_AUTH_SECRET`を自動生成して値を表示しない。既存`.dev.vars`や`.env`があれば変更せず停止する。

資材をコピーする場合は`assets/nextjs-opennext-d1/`を出発点にする。`__APP_NAME__`、`__WORKSPACE_DOMAIN__`、`__LOCAL_ORIGIN__`、`__PRODUCTION_ORIGIN__`を置換し、プロジェクトの既存パス、DB schema、UIへ適合させる。既存ファイルを無確認で上書きしない。

新規Next.js/OpenNextアプリで対象ファイルがまだ存在しない場合は、安全な雛形をCLI生成できる。

```bash
node <skill-dir>/scripts/render-nextjs-templates.mjs \
  --output <project-root> \
  --app-name "<APP_NAME>" \
  --workspace-domain "<WORKSPACE_DOMAIN>" \
  --production-origin "<PRODUCTION_ORIGIN>" \
  --d1-name "<D1_DATABASE_NAME>" \
  --d1-id "<D1_DATABASE_ID>"
```

1つでも同名ファイルがあれば、スクリプトは何も上書きせず停止する。既存アプリはagentが差分を読んで`apply_patch`する。

## 4. ユーザー用Google設定リンクを発行する

実装直後に次を実行し、プロジェクト直下へ案内書を生成する。

```bash
node <skill-dir>/scripts/generate-user-guide.mjs \
  --app-name "<APP_NAME>" \
  --production-origin "<PRODUCTION_ORIGIN>" \
  --workspace-domain "<WORKSPACE_DOMAIN>" \
  --output auth-google-setup.md
```

Pagesの場合は`--cloudflare-target pages --cloudflare-project-name <name>`を追加する。複数Workerや環境指定が必要な場合だけ`--worker-name`または`--cloudflare-env`を追加する。生成先には案内書と`.better-auth-google/setup-secrets.mjs`が作られる。

生成物をユーザーへクリック可能なローカルファイルリンクで渡す。会話上では次の3点だけを提示する。

1. [Google Auth Platform - Clients](https://console.cloud.google.com/auth/clients)
2. `node .better-auth-google/setup-secrets.mjs`
3. 本番サインインURL

生成するMarkdownは`references/google-cloud-manual.md`と`assets/google-cloud-beginner-guide.md.template`を使う。案内書へ絶対パスやOS固有操作を入れない。Client ID/Secretは生成されたプロジェクト内スクリプトへ一度だけ非表示入力させ、ローカルとCloudflare本番へ同時登録する。

この段階だけはユーザー操作を待つ。ユーザーにはSecretを貼らせず、Terminalで登録後に「登録した」とだけ返してもらう。

## 5. Secretを登録する

ユーザーがGoogle Clientを発行したら、プロジェクト内Terminalで次を一度だけ実行させる。

```bash
node .better-auth-google/setup-secrets.mjs
```

このスクリプトはOSや個人の絶対パスへ依存しない。Client ID/Secretを一度だけ非表示入力し、`.dev.vars`または既存`.env`とCloudflareへ登録する。`BETTER_AUTH_SECRET`、Git除外、ファイル権限も自動処理する。値入りファイルを生成物、回答、Gitへ含めない。

## 6. 検証してデプロイする

実装後に次を実行する。

```bash
node <skill-dir>/scripts/check-auth-readiness.mjs \
  --project <project-root> \
  --production-origin "<PRODUCTION_ORIGIN>" \
  --workspace-domain "<WORKSPACE_DOMAIN>"
```

その後、プロジェクト固有のtest、typecheck、buildを実行する。Cloudflareログイン済みなら`--remote`でもreadinessを実行し、Secret名とD1 migration状態を読み取り確認する。

デプロイ前に`references/security-and-testing.md`の必須項目を全確認する。デプロイ後は以下を検証する。

- `/sign-in`が200で表示される。
- 未ログインで保護ページ/APIへ入れない。
- OAuth開始レスポンスがGoogleへ遷移し、callback URIが登録値と一致する。
- （SPA配信時）`curl -H "Accept: text/html" -H "Sec-Fetch-Mode: navigate" "$ORIGIN/api/me"`がWorkerの応答を返す（`index.html`が返るならOAuthコールバックが横取りされる）。
- 許可Workspaceユーザーは成功する。
- 個人Gmail、別Workspace、グループアドレス／エイリアスは拒否される。
- 拒否ユーザーのsessionが発行されない。
- Secret、token、Cookie全文がログに出ない。

実アカウントを使うGoogle画面の操作はユーザー本人に依頼するか、明示許可されたブラウザ操作で行う。認証成功を未確認のまま「完了」と報告しない。

## 7. 完了報告の形式

次の順番で簡潔に報告する。

```text
実装済み: 変更した認証機能
自動実行済み: install / schema / migration / secrets / test / build / deploy
あなたの操作: Google Consoleで残っている操作（なければ「なし」）
リンク: 案内書、本番サインイン、Google設定画面
Redirect URI: 開発、本番
検証結果: 許可・拒否・保護API・Secret漏えい
未確認: 実アカウント操作など、残っている事実だけ
```

## リソース

- `references/nextjs-opennext-d1.md`: このチャットで完成した構成を一般化した標準実装
- `references/hono-workers-d1.md`: Hono／素のWorker向け構成
- `references/google-cloud-manual.md`: ユーザー作業の説明規約
- `assets/google-cloud-beginner-guide.md.template`: 非ITメンバー向けの完全なMarkdown手順書
- `assets/setup-secrets.mjs.template`: OS共通・プロジェクトローカルのSecret登録コマンド
- `references/security-and-testing.md`: セキュリティ不変条件と受入テスト
- `references/known-pitfalls.md`: Better Auth×Cloudflareの既知バグ・redirect_uri_mismatch・SPA横取り対策
- `references/free-tier-guardrails.md`: Workers/D1無料枠の数値とクエリ設計ガードレール
- `references/acceptance-and-operations.md`: 受入条件・トラブルシューティング早見表・運用（月次チェック/Secretローテーション/ログ設計）
- `references/official-sources.md`: 現行仕様を確認する一次情報
- `scripts/inspect-project.mjs`: 認証構成の安全な読み取り調査
- `scripts/render-nextjs-templates.mjs`: 新規Next.js/OpenNext向け雛形の非上書き生成
- `scripts/setup-local-vars.mjs`: ローカルSecretと`.dev.vars`の安全な初回作成
- `scripts/setup-google-local-secrets.sh`: Google Client値を非表示入力で`.dev.vars`へ安全に保存
- `scripts/generate-user-guide.mjs`: クリック可能な日本語手順書生成
- `scripts/setup-cloudflare-secrets.sh`: Wrangler Secretの安全な対話登録
- `scripts/check-auth-readiness.mjs`: ローカル／本番readiness検査
