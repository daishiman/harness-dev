# Wrangler 設定 (wrangler.jsonc)

## 最小構成

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2026-01-01"
}
```

## バインディングを含むフル構成

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2026-01-01",
  "compatibility_flags": ["nodejs_compat"],

  // 環境変数
  "vars": {
    "ENVIRONMENT": "production"
  },

  // KV Namespace
  "kv_namespaces": [
    { "binding": "KV", "id": "<KV_NAMESPACE_ID>" }
  ],

  // R2 Bucket
  "r2_buckets": [
    { "binding": "BUCKET", "bucket_name": "my-bucket" }
  ],

  // D1 Database
  "d1_databases": [
    { "binding": "DB", "database_name": "my-db", "database_id": "<DB_ID>" }
  ],

  // Workers AI (常にリモート実行)
  "ai": { "binding": "AI" },

  // Vectorize
  "vectorize": [
    { "binding": "VECTOR_INDEX", "index_name": "my-index" }
  ],

  // Hyperdrive
  "hyperdrive": [
    { "binding": "HYPERDRIVE", "id": "<HYPERDRIVE_ID>" }
  ],

  // Durable Objects
  "durable_objects": {
    "bindings": [
      { "name": "COUNTER", "class_name": "Counter" }
    ]
  },

  // Cron トリガー
  "triggers": {
    "crons": ["0 * * * *"]
  },

  // 環境
  "env": {
    "staging": {
      "name": "my-worker-staging",
      "vars": { "ENVIRONMENT": "staging" }
    }
  }
}
```

## 設定から型を生成する

```bash
# worker-configuration.d.ts を生成
pnpm wrangler types

# 出力先を指定
pnpm wrangler types ./src/env.d.ts

# 型が最新かチェック (CI 向け)
pnpm wrangler types --check
```

## 新規 Worker の作成

```bash
# 新規プロジェクトを初期化
pnpm wrangler init my-worker

# フレームワーク付きで作成
pnpm create cloudflare@latest my-app
```

## 設定に関する原則

- **`wrangler.jsonc` を使う**: TOML より JSON を優先する。新しい機能は JSON 専用のものがある。
- **`compatibility_date` を設定する**: 直近 30 日以内の日付を使う。https://developers.cloudflare.com/workers/configuration/compatibility-dates/ を確認。四半期ごとに更新して新しいランタイム機能を取り込む。
- **設定変更後は型を再生成する**: `pnpm wrangler types` で TypeScript バインディングを更新。
- **staging/production は環境で分ける**: 設定に `env.staging` と `env.production` を定義する。
- **`wrangler.jsonc` をバージョン管理する**: Worker 設定の唯一の情報源として扱う。
- **自動プロビジョニングを使う**: リソース ID を省略するとデプロイ時に自動作成される。
- **CI で `pnpm wrangler types` を実行する**: ビルドステップに追加してバインディングの不一致を検出する。

## 設定フィールドの参照先

| ソース | 取得方法 | 用途 |
|--------|----------|------|
| Wrangler docs | `https://developers.cloudflare.com/workers/wrangler/` | CLI コマンド、フラグ、設定リファレンス |
| Wrangler 設定スキーマ | `node_modules/wrangler/config-schema.json` | 設定フィールド、バインディング形状、許可値 |
| Cloudflare docs | 検索ツール または `https://developers.cloudflare.com/workers/` | API リファレンス、compatibility date/flag |

```bash
# 設定スキーマのドキュメントを開く
pnpm wrangler docs configuration
```
