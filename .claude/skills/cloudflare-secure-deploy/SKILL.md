---
name: cloudflare-secure-deploy
description: >
  Cloudflare Workers + D1/R2/KV/Durable Objects でデータベースとサーバーを安全・高速・高品質に接続し、
  絶対に間違えずにデプロイするためのスキル。「デプロイして」「公開して」「本番反映」「Cloudflareに載せて」
  「Workersで作って」「D1とつなぐ」「wrangler」「マイグレーション適用」「プレビューURL」などの文脈で必ず使用する。
  Cloudflare上のアプリを新規作成・機能追加・デプロイ・レビューする場合、ユーザーが「Cloudflare」と明示しなくても
  デプロイ先がWorkersなら必ずこのスキルを読むこと。D1スキーマ設計・パフォーマンス改善・セキュリティ強化・
  wrangler設定の相談でもトリガーする。認証実装の詳細は Skill better-auth-google-gate、
  LLM API組み込みは Skill llm-api-integration を併用。
---

# Cloudflare セキュア・デプロイ スキル

Workers + D1 を中心に、**①正しいスタック選定 ②本番品質の wrangler 設定 ③D1の鉄則 ④セキュリティ不変条件 ⑤パフォーマンス最適化 ⑥失敗しないデプロイ手順** を定める。
実プロジェクト13本(不動産マッチング/恵友系/ポータル系/Quiz Bingo等)の実戦知見 + 2026-07時点の公式ドキュメント検証済み。

> **原則: 仕様の確認と調査は MCP、deploy / secret put / d1 migrations apply は監査性・可逆性・秘密保護のため wrangler CLI を既定にする**(MCP に能力が無いからではない)。操作別の既定表と MCP 不通時の復旧は `skills/wrangler/references/mcp-vs-cli-routing.md` が唯一の正本。本スキル固有の制約は §10 の停止条件だけである。

- 具体的な設定スニペット集: `references/recipes.md`(レシピ別の完全な wrangler.jsonc / スクリプト)
- 実戦で踏んだ落とし穴集: `references/gotchas.md`(**デプロイ前に必ず一読**)
- 非エンジニア向けAccount/API Token/GitHub/Worker secret設定は Skill `ci-cd-pipeline` の生成ガイドを正本にする

## 0. Cloudflare Accountを先に固定する(INV-10)

リソース作成・secret設定・deployより前に対象Accountを固定する。1人が複数Accountへ所属しており、チーム用共有Accountと個人Accountの両方がある場合の既定は**チーム用Account**。個人Accountは利用者が明示指定した場合だけ使う。

優先順は「既存`wrangler.jsonc`と既存リソースの所有Account → 新規ならチーム用Account → 明示指定時だけ個人Account」。既存リソースが個人側にあるとき、チーム側へ同名リソースを作らない。チーム移行はD1/R2データ・Worker URL・secret・GitHub Environmentを含む別タスクとして承認を取る。

Cloudflare公式では共有環境も個人環境もAccountであり、特定の有料「Team plan」と同義ではない。料金プランの変更・購入は別の承認境界。

最低確認:

```bash
pnpm wrangler whoami
```

Worker/D1/R2を使う場合は一覧と`wrangler.jsonc`のID/名前を照合する。Account不一致のまま作成・secret更新・deployへ進まない。Account IDの完全値をチャットや最終報告へ載せない。

---

## 1. スタック選定(最初に決める)

| 要件 | レシピ | キー技術 |
|---|---|---|
| SSR/RSC が必要な Web アプリ | **A: Next.js + OpenNext** | `@opennextjs/cloudflare` |
| SPA + API(業務ツールの大半はこれ) | **B: Vite SPA + Worker API** | `@cloudflare/vite-plugin` + Hono |
| APIのみ / 軽量 | **C: Hono 単体 Worker** | `hono` |
| リアルタイム(WebSocket/対戦/共同編集) | **D: Durable Objects** | WebSocket Hibernation, `new_sqlite_classes` |
| 静的サイトのみ | **E: Workers Assets のみ**(`main` なし) | — |

原則:
- **既存のNext.js + OpenNextアプリにはHonoを追加しない**。APIはNext.js Route Handlerを使い、レシピB/CはVite SPAまたはHono Workerとして新規に構成する場合だけ選ぶ。
- **新規プロジェクトは Pages ではなく Workers(static assets)を使う**。機能開発は Workers 側に集中している(公式移行ガイドあり)
- DB は既定で **D1**。ただし「10GB超 / 本物のトランザクション / Postgres機能」が要るなら Hyperdrive + Postgres に切り替える(D1に Hyperdrive は不要)
- **OpenNext と Durable Objects は同居させない**。DO が要る場合はリアルタイム専用 Worker を分離する(2 Worker 構成)
- 迷ったらレシピB。dev体験・デプロイ速度・無料枠適合のバランスが最良

---

## 2. 新規デプロイの標準手順(この順番を崩さない)

```bash
# 1. プロジェクト作成(スキャフォールドを使う。手組みしない)
pnpm create cloudflare@latest -- <app-name> --framework=next   # レシピA
pnpm create cloudflare@latest -- <app-name> --framework=react  # レシピB

# 2. リソースをプロビジョニング(IDを控えて wrangler.jsonc に記入)
pnpm wrangler d1 create <app-name>-db
pnpm wrangler r2 bucket create <app-name>-docs    # 必要な場合
# ※ Bindings MCP 認証済みなら MCP(d1_database_create 等)でも可。未認証なら CLI のまま進め、認証は促さない
#   (既定表: skills/wrangler/references/mcp-vs-cli-routing.md)

# 3. wrangler.jsonc をベースライン(§3)に整える。compatibility_date は今日の日付

# 4. D1 マイグレーション(必ず migrations 方式。単発 schema.sql 直実行は避ける)
pnpm wrangler d1 migrations create <db-name> init
# → SQL記述(テーブル + インデックス + CHECK制約。§4)
pnpm wrangler d1 migrations apply <db-name> --local    # ローカルで検証
pnpm wrangler d1 migrations apply <db-name> --remote   # ★コードのデプロイより先に適用

# 5. シークレット設定(vars に秘密を書かない。§5)
#    先にsecret list。既存secretは通常セットアップで上書きしない
pnpm wrangler secret list
pnpm wrangler secret put SESSION_SECRET
# ローカルは .dev.vars(.gitignore 必須)

# 6. 型生成 + ローカル検証(workerd 上で確認してからデプロイ)
pnpm wrangler types
pnpm run build && pnpm run preview   # OpenNextは opennextjs-cloudflare preview

# 7. デプロイ前検証(mvp-first §5 の前段。どちらも失敗ならデプロイしない)
pnpm exec wrangler deploy --dry-run   # 設定・binding・バンドルの検証。実デプロイなし
pnpm audit --prod                     # 高危険度の依存脆弱性を確認(HIGH 以上は残課題へ記録か解消)

# 8. デプロイ
pnpm run deploy
# 9. デプロイ後検証(§8): 本番URLを実際に叩く・wrangler tail・Access確認
```

**順序の鉄則**: マイグレーション適用(--remote)→ コードデプロイ。逆にすると新スキーマ前提のコードが旧DBに当たって全面エラーになる。カラム削除を伴う場合は「新コードデプロイ→旧カラム参照が消えたことを確認→削除マイグレーション」の2段階(expand → contract)。

---

## 3. wrangler.jsonc ベースライン(2026-07 検証済み)

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "app-name",
  "main": "./worker/index.ts",
  "compatibility_date": "2026-07-16",              // 新規作成時は必ず「今日」
  "compatibility_flags": ["nodejs_compat"],
  "observability": { "enabled": true, "head_sampling_rate": 1 },  // 高トラフィックなら 0.01–0.1
  "upload_source_maps": true,                       // 本番スタックトレースが読める(GA)
  "assets": {
    "directory": "./dist/client",
    "binding": "ASSETS",
    "not_found_handling": "single-page-application",
    "run_worker_first": ["/api/*"]                  // ★既定はアセット優先。認証/APIはWorker先行を明示
  },
  "d1_databases": [{
    "binding": "DB",
    "database_name": "app-name-db",
    "database_id": "<uuid>",
    "migrations_dir": "migrations"
  }],
  "secrets": { "required": ["SESSION_SECRET"] },    // 未設定ならデプロイが失敗する(事故防止)
  "limits": { "cpu_ms": 10000 },                    // コスト暴走の上限。必要になったら上げる
  "vars": { "APP_ENV": "production" }               // ★varsは平文。秘密は絶対に書かない
}
```

必ず守ること:
- **`run_worker_first`**: Workers はデフォルトで「静的アセットが Worker より先に」返る(Pagesと逆)。認証・ログ・ヘッダー付与を Worker でやるならこの指定が必須。パス配列(`["/api/*"]`)でアセット配信は高速なまま API だけ Worker 先行にするのが最適
- **`secrets.required`**: 必須シークレットを宣言。設定漏れのままデプロイして「本番だけ500」を防ぐ
- **`limits`**: `cpu_ms` / `subrequests` は上げるだけでなく**下げて安全弁**にできる(暴走ループでの課金事故防止)
- **`wrangler types` で Env 型を生成**し手書きしない(公式ベストプラクティス)
- 環境分離は `env.staging` / `env.production` + `wrangler deploy -e <env>`。本番は `workers_dev: false` + カスタムドメインが理想
- ステージング/本番で **D1・R2 は必ず別リソース**にする(同じ database_id の使い回し禁止)

---

## 4. D1 の鉄則

1. **プリペアドステートメント以外禁止**: `env.DB.prepare("... WHERE id = ?").bind(id)`。文字列連結でSQLを組んだら即修正
2. **対話型トランザクションは存在しない**(BEGIN/COMMIT不可)。複数書き込みの原子性は **`env.DB.batch([...])`** で担保 — 1つ失敗で全体ロールバック + ラウンドトリップも1回に集約される
3. **インデックスは課金に直結**: D1 は `rows_read` 課金。フルスキャンは「返した行数」ではなく「読んだ行数」で課金される。WHERE/ORDER BY に使う列には `CREATE INDEX IF NOT EXISTS idx_<table>_<cols>` を最初のマイグレーションから入れる。複合インデックスは左端一致のみ有効
4. インデックス追加・スキーマ変更後は **`PRAGMA optimize`** を実行(クエリプランナ統計の更新)。効いているかは `EXPLAIN QUERY PLAN` で `USING INDEX` を確認
5. **マイグレーションは `wrangler d1 migrations` 一択**(`d1_migrations` テーブルで適用管理される)。`--local` で検証してから `--remote`。コマンドには binding 名でなく **database_name** を渡す
6. スキーマ品質: status 等の列挙は `CHECK` 制約、複合ユニークは `UNIQUE(...)`、`updated_at` はトリガで維持、物理削除より `archived_at`(ソフトデリート)
7. 制限を設計に織り込む: 1リクエストあたりクエリ 50(無料)/1,000(有料)、DB 500MB(無料)/10GB(有料)、bindパラメータ100個/クエリ。N+1 は batch か JOIN で潰す
8. グローバル読み取りが遅い場合: **read replication + Sessions API**(`env.DB.withSession(bookmark)`、bookmark をヘッダで往復)。書き込みは常にプライマリ
9. バックアップ: **Time Travel**(無料7日/有料30日)がある。ただし `d1 delete` や破壊的マイグレーションの免罪符にしない

---

## 5. セキュリティ不変条件(INV-1)

### Secrets
- `vars` は**平文**(config・ダッシュボードで丸見え)。API キー・署名鍵・パスワードは `wrangler secret put` のみ。ローカルは `.dev.vars`(.gitignore)
- **コードにフォールバック秘密値を書かない**(`|| "dev-secret"` 禁止)。未設定なら fail-closed(503)にする。実戦で `'dev-only-secret-change-me'` がそのまま本番に残る事故が起きている
- 複数 Worker で共有する秘密は Secrets Store(`secrets_store_secrets` binding、`await env.X.get()`)も選択肢(open beta)。CI からのデプロイには API トークンに Secrets Store Edit 権限が必要

### アクセス制御(社内・限定公開アプリ)
- **Cloudflare Access で守る + Worker 内で `Cf-Access-Jwt-Assertion` の JWT を必ず署名検証**(ヘッダの存在だけを信じるのはスプーフィング可能)。検証項目: 署名(チーム証明書)・`iss`・`aud`(アプリのAUDタグ)・`exp`・`type === "app"`・email/sub 非空
- **サービストークンは有効な JWT だが email が空** — 公式サンプルの `payload.email || "authenticated user"` は機械を人間として通す穴。email 空は明示的に拒否する
- Access の設定変数(team domain / AUD)が未設定なら**全リクエスト503(fail-closed)**。素通しフォールバック禁止
- **プレビューURL(`<version>-<app>.workers.dev`)にも Access を掛ける**。本番だけ守って横から入られるのが最頻出の穴
- **Access は CSRF を防がない**(誰がを守るが、どこからを守らない)。書き込み系(非GET)は `Origin` ヘッダが自オリジンかを検証して 403

### アプリケーション防御
- レート制限は **`ratelimits` binding**(GA、wrangler >= 4.36):`{ "name": "LIMITER", "namespace_id": "1001", "simple": { "limit": 100, "period": 60 } }`(period は 10 か 60 のみ)。**キーは IP でなくユーザーID** — オフィスは1つのグローバルIPを共有するため IP キーだと全員巻き添えになる
- セキュリティヘッダーは静的アセット向けに `public/_headers`(Workers assets でもネイティブ対応)、API レスポンスには Worker で付与: `X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: strict-origin-when-cross-origin` / CSP(`default-src 'self'; object-src 'none'; frame-ancestors 'none'`ベース)
- Cookie は `HttpOnly; Secure; SameSite=Lax` 以上。トークン生成は Web Crypto(`crypto.getRandomValues`)— `Math.random()` 禁止
- ボディサイズをパース前に検証(`content-length` チェック → 413)。ユーザー由来 URL は `http/https` スキームのみ許可(`javascript:` 対策)
- R2 は**バケット非公開 + Worker 経由配信**(認可ロジックを挟める)を既定に。クライアント直アップロードが必要なときだけ presigned URL(`aws4fetch`、有効期限 3600s 程度)
- モジュールスコープに**リクエスト横断の可変状態を置かない**(isolate 再利用でユーザー間データ漏洩)。JWKS 等のキャッシュは可・ユーザーデータは不可

---

## 6. パフォーマンス最適化

- **バインディングは REST API より速い**: D1/R2/KV へは必ず binding でアクセス(ネットワークホップと認証が消える)
- **Smart Placement**: `"placement": { "mode": "smart" }` — 1リクエストで D1 に複数回クエリするアプリでは Worker が DB の近くで実行され大きく効く。1クエリだけなら効果なし。バックエンド位置が既知なら `placement.region` の明示ヒントも可(2026-01新機能)
- **batch() でラウンドトリップ集約**: 独立した複数クエリも `DB.batch()` でまとめる(N+1 の応急処置にも)
- **キャッシュの選び方(2026年時点)**:
  - HTTPレスポンスのキャッシュ → **Workers Caching**(`"cache": { "enabled": true }`、新機能): Worker の**手前**でヒットするので CPU 課金ゼロ・リクエスト折り畳みあり。新規はこれを優先(公式推奨)。パージは `ctx.cache.purge()`
  - 旧 Cache API(`caches.default`)はコロ単位・複製なし・**Access 配下では使用不可**。workers.dev では挙動が制限されるため頼らない
  - 小さな設定値・JWKS 等 → モジュールスコープ TTL キャッシュ、グローバルに共有したいデータ → KV(結果整合)
- **ストリーミング**: 大きなレスポンスは `TransformStream`/`pipeTo` で流す(128MB メモリ上限対策 + TTFB 改善)
- **Durable Objects は必ず WebSocket Hibernation**: `this.ctx.acceptWebSocket(server)` + クラスメソッド `webSocketMessage/webSocketClose`(`ws.accept()` + addEventListener は課金され続ける)。接続ごとの状態は `serializeAttachment()`。ping/pong は `setWebSocketAutoResponse()`。`setTimeout`/outbound WS/alarm は休止を妨げる。無料プランは `new_sqlite_classes` 必須
- 主要な制限値(2026-07): Worker サイズ gzip 3MB(無料)/10MB(有料)、CPU 10ms(無料)/既定30s・最大5分(有料、`limits.cpu_ms`)、サブリクエスト 50(無料)/**10,000(有料・2026-02に1,000から引き上げ**、`limits.subrequests` で最大1,000万)。静的アセットは配信無料
- フロント側: Vite の `manualChunks` で vendor 分割、画像は R2 + `Cache-Control`

---

## 7. 観測性(デプロイ前に有効化)

- `observability.enabled: true`(Workers Logs GA: 保持7日・無料枠超は約$0.60/M行 → 高トラフィックは `head_sampling_rate: 0.01–0.1`)
- `upload_source_maps: true` でスタックトレースが原コード行に解決される
- 本番デバッグ: `pnpm wrangler tail <name>` (outcome `exceededCpu` 等が見える)
- ビジネスメトリクス(AI利用回数等)は Analytics Engine binding(`writeDataPoint`)。デプロイバージョン別に切りたいときは `version_metadata` binding の id を index に入れる

---

## 8. デプロイ検証と段階的リリース

### 毎回のデプロイ後検証(スキップ禁止)
1. 本番URLを実際に fetch して 200 と主要画面のレンダリングを確認(curl + 主要 API 1本)
2. `wrangler tail` を数十秒眺めて例外ゼロを確認
3. スキーマ変更を伴った場合: 該当機能の読み書きを1往復実行
4. Access 対象アプリ: 未認証アクセスがブロックされること・プレビューURLも守られていることを確認

### リスクの高い変更(スキーマ破壊・認証変更・決済系)
```bash
pnpm wrangler versions upload            # デプロイせずバージョン作成 → プレビューURL発行
# プレビューURLでスモークテスト
pnpm wrangler versions deploy            # 10%/90% 等の段階配信
pnpm wrangler rollback                   # 問題発生時(直近100バージョンまで戻せる)
```

### CI(Workers Builds)
- GitHub 連携時: 本番ブランチ=`wrangler deploy`、非本番ブランチ=自動で `versions upload` → PR にプレビューURLコメント
- ビルド時変数(`NEXT_PUBLIC_*` 等)はランタイム vars と**別枠**の「Build variables and secrets」に設定する

---

## 9. MCP と wrangler の役割分担

操作別の既定経路(D1/R2/KV 作成、docs 検索、deploy、secrets、migration、ログ)は `skills/wrangler/references/mcp-vs-cli-routing.md` の「作業別の既定経路」表に従う。本スキルでは表を複製しない。仕様が不確かなら**推測せず docs MCP を引く**。

## 10. 停止条件(勝手にやらない)(INV-10, INV-13)

- チーム用Accountと個人Accountの判別不能、または`wrangler.jsonc`/既存リソースとログイン先が不一致 → **作成・secret更新・deployを停止**
- 既存Worker secretの更新 → **ローテーション扱い**。ログイン不能・全セッション失効等の影響を示してユーザー確認
- 不足Worker/D1/R2の新規作成 → 対象Account・名前・課金有無を示してユーザー確認
- `wrangler d1 delete` / R2バケット削除 / DROP TABLE を含むマイグレーション → **必ずユーザー確認**(Time Travel があっても)
- 有料機能・課金枠の拡大(limits の大幅引き上げ、有料プラン前提の設定)→ 確認
- カスタムドメインの付け替え・DNS変更 → 確認
- 本番 D1 への手動 UPDATE/DELETE(マイグレーション外)→ 確認 + 実行前に対象行数を SELECT で提示

## 11. 検収チェックリスト

デプロイ完了を宣言する前に:
- [ ] compatibility_date が今日 / nodejs_compat / observability / upload_source_maps 設定済み
- [ ] 対象Accountを固定し、複数候補ならチーム用Accountを既定選択した
- [ ] 既存リソースの所有AccountとWrangler/GitHubのAccount IDが一致する
- [ ] `run_worker_first` の要否を判断した(認証・APIパスは Worker 先行か)
- [ ] D1: migrations 方式・prepare+bind のみ・書き込み原子性は batch・主要クエリにインデックス
- [ ] マイグレーション --remote 適用 → コードデプロイの順を守った
- [ ] 秘密は secret のみ(vars/コードに平文なし)・`secrets.required` 宣言・.dev.vars は .gitignore
- [ ] `secret list`を先に確認し、既存secretを承認なくローテーションしていない
- [ ] 認証: Access なら JWT 署名検証 + fail-closed + プレビューURL保護。書き込みに Origin チェック
- [ ] レート制限(ユーザーIDキー)・セキュリティヘッダー・ボディサイズ上限
- [ ] `limits.cpu_ms` 等のコスト安全弁を設定した
- [ ] preview(workerd 実機)で確認してからデプロイした
- [ ] `wrangler deploy --dry-run` が通った
- [ ] `pnpm audit --prod` を実行し、HIGH 以上は解消するか残課題に記録した
- [ ] デプロイ後: 本番URL実打・tail で例外ゼロ・スキーマ変更機能の1往復確認
- [ ] `references/gotchas.md` の該当項目を確認した
