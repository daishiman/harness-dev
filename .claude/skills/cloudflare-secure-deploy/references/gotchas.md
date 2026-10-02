# 実戦で踏んだ落とし穴集(デプロイ前に該当項目を確認)

実プロジェクト13本 + 2026-07 公式ドキュメント検証から。番号は重要度順ではない — 該当構成のものを全て確認する。

## ルーティング / アセット配信

1. **静的アセットは Worker より先に返るのがデフォルト**(Pages と逆)。認証チェック・ログ・ヘッダー付与を Worker でやるつもりが、アセットは素通しになる。→ `assets.run_worker_first: true` またはパス配列 `["/api/*"]`
2. **Worker が前段にいると SPA フォールバックが死ぬ**: `not_found_handling: "single-page-application"` は Worker が処理したリクエストには適用されない。未知パスが Hono の `notFound`(JSON 404)に落ちて画面が出ない。→ Worker 側で未知の GET は ASSETS にフォールバックする
3. **`/index.html` を直接 fetch すると 307 リダイレクト**が返り空白ページになる。SPA フォールバックは `new URL("/", request.url)` を叩く
4. **Worker から `*.workers.dev` への fetch は不可**(Cloudflare error 1042)。Worker 同士のサーバーサイド連携・リンクチェック・favicon取得は設計段階から諦め、ブラウザ経由に委譲する
5. 自アプリのエンドポイントを Worker 内から fetch する構成は `compatibility_flags: ["global_fetch_strictly_public"]` を検討(内部ループバックではなく公開経路を強制)

## デプロイ / 設定

6. **vite-plugin 構成の deploy はビルド生成物の config を使う**: `wrangler deploy -c dist/<name>/wrangler.json`。素の `wrangler deploy` はソースの wrangler.jsonc を読んで assets 解決が壊れる。package.json の deploy スクリプトに焼き込むこと
7. **マイグレーションとコードのデプロイ順**: `d1 migrations apply --remote` が先、コードデプロイが後。逆だと新コードが旧スキーマに当たり全 API がエラー
8. **`secrets.required` を書かずに秘密の設定漏れ**: 新環境(staging追加時など)で secret 未設定のままデプロイ → 本番だけ 500。config で宣言すればデプロイ自体が失敗してくれる
9. **Durable Objects は `new_sqlite_classes`**(`new_classes` ではない)。無料プランは SQLite バックエンド必須で、間違えるとデプロイエラー
10. **OpenNext と DO の同居は不可**と考える。リアルタイム要件は別 Worker に分離(2 Worker 構成、フロントへはビルド時にURL注入)
11. ステージングと本番で **database_id を使い回さない**。環境ごとに D1/R2 を作り、`env.staging` / `env.production` で分ける

## セキュリティ

12. **Access を有効化しても Worker 側の JWT 検証を省略しない**。`Cf-Access-Jwt-Assertion` は署名・iss・aud・exp・`type === "app"` まで検証。ヘッダの有無だけ見るのはスプーフィング可能
13. **サービストークンは email が空のまま Access を通過する**。公式サンプルの `payload.email || "authenticated user"` は機械を人間として通す。email/sub 空は拒否
14. **プレビューURLの保護漏れ**: 本番URLに Access を掛けても `<version>-<app>.workers.dev` が野放しになりがち。プレビューにも Access を掛ける
15. **Access は CSRF を防がない**: ログイン済みブラウザはクロスサイトからでも Cookie を送り、Access は有効な JWT を付けて通す。非 GET は Origin 検証を別途行う
16. **Access 設定変数が空なら fail-closed(503)**にする。「未設定なら認証スキップ」のフォールバックは公開事故になる
17. **コード内のデフォルト秘密値が本番に残る**: `SESSION_SECRET || "dev-only-secret-change-me"` のようなフォールバックがそのまま稼働した実例あり。フォールバック禁止・未設定は起動失敗(fail-closed)
18. **`vars` は平文**。wrangler.jsonc にトークンを書いた時点で git 履歴とダッシュボードに露出。秘密は `wrangler secret put` のみ
19. **レート制限のキーに IP を使わない**: オフィス・モバイル網は1つのグローバル IP を共有するため全員巻き添え。ユーザーID・APIキー単位で制限。またこの binding はコロ単位・結果整合の「ベストエフォート」であり課金の門番には使えない

## D1

20. **対話型トランザクションはない**(BEGIN/COMMIT 不可)。複数書き込みの原子性が要る箇所を見つけたら `batch()` に書き直す。「片方だけ書けた」状態は batch で防げる
21. **rows_read 課金**: WHERE 句の列にインデックスがないと、1行返すクエリでも全行スキャン分課金される。`EXPLAIN QUERY PLAN` で `USING INDEX` を確認、インデックス追加後は `PRAGMA optimize`
22. **d1 コマンドには database_name を渡す**(binding 名ではない)
23. クエリ数上限(無料50/リクエスト)があるため、ループ内クエリ(N+1)は無料プランで即死する。JOIN か batch に
24. **Time Travel(7日/30日)はあるが**、`d1 delete` は復元不可。破壊的操作は必ずユーザー確認

## キャッシュ / パフォーマンス

25. **Cache API(`caches.default`)は Access 配下の Worker では使えない**。workers.dev でも挙動が制限される。HTTPキャッシュは Workers Caching(`cache.enabled`)か、KV/モジュールスコープTTLに逃がす
26. **Smart Placement は複数ラウンドトリップがある時だけ効く**。D1 1クエリ/リクエストのアプリに付けても変わらない(害もない)
27. **DO で `ws.accept()` を使うと休止せず課金され続ける**。必ず Hibernation API(`ctx.acceptWebSocket` + クラスハンドラ)。`setTimeout`・outbound WebSocket・alarm は休止を妨げる
28. JWKS 等の外部公開鍵はモジュールスコープで TTL キャッシュ(毎リクエスト fetch しない)。ただしユーザーデータのモジュールスコープ保持は漏洩事故

## フロントエンド / その他

29. **CJK フォントのサブセット化が pdf-lib でグリフ欠けを起こす**。日本語 PDF 生成は TTF を `subset: false` でフル埋め込み
30. `cross-origin-resource-policy: same-origin` を返すサイト(claude.ai 等)の favicon は原理的に表示不可。モノグラムへのフォールバックを用意し、壊れた画像を出さない
31. 新しいメジャーバージョンのフレームワーク(Next 16 等)は訓練データと API が違う。`node_modules/<pkg>/dist/docs/` や公式ドキュメント(MCP `search_cloudflare_documentation`)を**書く前に**読む
32. デプロイ後の動作確認は本番URLへの実 fetch まで。「ビルドが通った=動く」ではない(assets 解決・binding 解決はランタイムでしか分からない)
