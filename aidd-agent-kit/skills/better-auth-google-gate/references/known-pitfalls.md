# Better Auth × Cloudflare 既知の落とし穴

実装前に、使用するBetter Authバージョンで以下が解消済みかIssueを確認する。

## 1. cookieCache＋secondaryStorage併用時のセッション更新バグ

（better-auth #4203、2026年1月に再オープン）

- 症状：セッションがDB/KV上は有効なのに、cookieCacheの期限（例：5分）で強制ログアウトされる
- 回避：解消が確認できるまで `cookieCache` を無効化し、`storeSessionInDatabase: true`＋`updateAge`で運用（セッション確認ごとにD1読み取り1回のコストを受け入れる）

## 2. リクエストごとにauthインスタンス/Drizzle D1インスタンスを1つだけ生成する

- Worker内で複数インスタンスを作るとローカルSQLiteの書き込みロック競合→ハング→後続503の連鎖が起きる
- middlewareチェーンの先頭で1回生成し、`c.set("auth", auth)`等で下流に共有する

## 3. レート制限のsecondaryStorageにKVを使う場合

- 内部TTLがKVの最小TTL 60秒を下回るエンドポイントがある。KVエラーが出たらレート制限の保存先設定を見直す

## 4. SPAフォールバックによるOAuthコールバック横取り

- 静的SPAアセットを`not_found_handling: "single-page-application"`で配る構成では、`assets.run_worker_first`に`/api/*`を入れる
- 入れないとOAuthコールバック（ブラウザのトップレベル遷移=`Accept: text/html`）がSPAフォールバックに横取りされ、Better Authが実行されずログインが完了しない。`fetch`は届くので気づけない

## 5. redirect_uri_mismatch（最頻出エラー）

次の違いでもエラーになる：`http`/`https`、`www`の有無、大文字小文字、ポート番号、末尾スラッシュ、コールバックパスの欠落。

登録するRedirect URI: `https://<APP_DOMAIN>/api/auth/callback/google`＋`http://localhost:3000/api/auth/callback/google`（basePath変更時は合わせる）

## 6. D1無料枠とDBセッション

- Better AuthはDBセッションが基本。セッション確認ごとにD1 Rows Readを消費する
- 日次アクティブユーザー×平均リクエスト数でRows Read/日を見積もり、D1 Free（5M reads/日）に収まるか設計段階で確認する
- 詳細は `free-tier-guardrails.md`
