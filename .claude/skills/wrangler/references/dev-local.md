# ローカル開発とテスト

## 開発サーバーの起動

```bash
# ローカルモード (デフォルト) — ローカルストレージシミュレーションを使う
pnpm wrangler dev

# 環境を指定
pnpm wrangler dev --env staging

# ローカル専用を強制 (リモートバインディングを無効化)
pnpm wrangler dev --local

# リモートモード — Cloudflare エッジ上で実行 (レガシー)
pnpm wrangler dev --remote

# ポートを指定
pnpm wrangler dev --port 8787

# HTML 変更のライブリロード
pnpm wrangler dev --live-reload

# scheduled/cron ハンドラのテスト
pnpm wrangler dev --test-scheduled
# その後 http://localhost:8787/__scheduled にアクセス
```

**ローカル開発はデフォルトでローカルストレージを使う**: バインディングは `remote: true` を指定しない限りローカルシミュレーションになる。

## ローカル開発でのリモートバインディング

バインディング設定に `remote: true` を指定すると、ローカル実行のまま実リソースへ接続できる。

```jsonc
{
  "r2_buckets": [
    { "binding": "BUCKET", "bucket_name": "my-bucket", "remote": true }
  ],
  "ai": { "binding": "AI", "remote": true },
  "vectorize": [
    { "binding": "INDEX", "index_name": "my-index", "remote": true }
  ]
}
```

**リモートバインディングを推奨するサービス**: AI (必須)、Vectorize、Browser Rendering、mTLS、Images。

## ローカルシークレット

ローカル開発用のシークレットは `.dev.vars` に置く (設定ファイルにシークレットをコミットしない)。

```
API_KEY=local-dev-key
DATABASE_URL=postgres://localhost:5432/dev
```

## Vitest によるローカルテスト

```bash
pnpm add -D @cloudflare/vitest-pool-workers vitest
```

`vitest.config.ts`:

```typescript
import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: {
        wrangler: { configPath: "./wrangler.jsonc" },
      },
    },
  },
});
```

## scheduled イベントのテスト

```bash
# dev で有効化
pnpm wrangler dev --test-scheduled

# HTTP でトリガー
curl http://localhost:8787/__scheduled
```

## 原則

- **ローカルで先にテストする**: デプロイ前に `pnpm wrangler dev` でローカルバインディングを使って確認する。
- **ローカル状態の保存先**: `.wrangler/state` ディレクトリ。永続化されない場合はここを確認する。
