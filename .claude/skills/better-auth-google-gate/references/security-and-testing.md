# セキュリティ不変条件と受入テスト

## 不変条件

1. `BETTER_AUTH_SECRET`は32文字以上の高エントロピー値にする。本番値はWrangler Secretへ置く。
2. `GOOGLE_CLIENT_SECRET`を`wrangler.jsonc`、ソース、`NEXT_PUBLIC_*`、ログへ置かない。
3. `.dev.vars`と`.env`を併用しない。選んだ一方をGit対象外にする。
4. `baseURL`を本番originへ固定し、`trustedOrigins`にワイルドカードを使わない。
5. callback URLをユーザー入力から組み立てない。ログイン後URLは同一originの既知パスだけにする。
6. Workspace限定は`socialProviders.google.hd`で強制する。メール末尾比較だけにしない。
7. Googleの`email_verified`がfalseならユーザー作成を拒否する。
8. 既存ユーザーの停止状態をsession作成前またはデータアクセス直前で検証する。
9. 認証route以外の保護API、Server Action、データアクセスで有効sessionを検証する。
10. Cookie存在チェックはUX上の早期redirect専用。認可判定に使わない。
11. Better Auth標準のstate、PKCE、CSRF、Cookie設定を無効化しない。
12. ログインだけなら`openid email profile`以外のGoogle scopeを追加しない。
13. Cloudflareでは`cf-connecting-ip`をrate limitのIP sourceに使い、serverlessでmemory rate limitへ依存しない。
14. Drizzle/D1ではBetter Auth CLIでschemaを生成し、D1 migrationを本番起動前に適用する。
15. 本番起動時の自動migrationを行わない。
16. auth instanceまたはDB clientをプロセス全体で危険に共有せず、Cloudflare/OpenNextのリクエスト境界へ合わせる。
17. 拒否画面には許可ドメイン一覧、内部判定、token、stack traceを出さない。
18. Secretを含む可能性がある`.dev.vars`全文、request header全文、Set-Cookie全文を出力しない。
19. 静的SPAアセットを`not_found_handling: "single-page-application"`で配る構成では、`assets.run_worker_first`で`/api/*`をWorker先行にする。これが無いとOAuthコールバック（ブラウザのトップレベル遷移=`Accept: text/html`）がSPAフォールバックに横取りされ、Better Authが実行されずセッションが張れない。`fetch`は届くので気づけない。Hono／素のWorker + 別ビルドSPAで必須。

## 自動テスト

- typecheck、unit test、production build。
- `check-auth-readiness.mjs`のローカル検査。
- Cloudflareログイン済みなら`check-auth-readiness.mjs --remote`。
- D1 migration listで未適用がないこと。
- `/sign-in`が200。
- 未認証で保護APIが401、保護ページがサインインへ遷移。
- 適当なCookie値を与えても保護APIが通らない。
- `/api/auth/callback/google`をstateなしで直接呼んでもsessionを発行しない。
- OAuth開始時のcallbackが登録済みURIと完全一致。
- error queryを表示しても内部理由を開示しない。
- **（SPA配信時）ブラウザのトップレベル遷移が`/api/*`でWorkerに届く**。`curl -H "Accept: text/html" -H "Sec-Fetch-Mode: navigate" "$ORIGIN/api/me"`が`index.html`（`<title>`/`<!doctype>`）ではなくWorkerのJSON/リダイレクトを返すこと。届かないとOAuthコールバックが完了せず、ログイン画面に戻り続ける。

## 実アカウント受入テスト

| ケース | 期待結果 |
|---|---|
| 対象Workspaceの管理対象ユーザー | 成功し、callbackURLへ遷移 |
| 同じユーザーの2回目ログイン | 成功し、userを重複作成しない |
| 個人Gmail | 拒否、sessionなし |
| 別Workspace | 拒否、sessionなし |
| 同一ドメイン風の個人Googleアカウント | `hd`なしで拒否 |
| Google Group／エイリアス | 独立アカウントとしてログイン不可 |
| 停止済み既存ユーザー | 新規sessionなし |
| サインアウト後の保護API | 401 |

## 完了判定

自動テストと対象構成の受入テスト結果を分けて報告する。実アカウント試験が残っている場合は「コード実装完了、実アカウント認証は未確認」と明示し、完全完了と呼ばない。
