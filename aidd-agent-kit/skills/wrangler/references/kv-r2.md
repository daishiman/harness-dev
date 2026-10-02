# KV (Key-Value ストア) と R2 (オブジェクトストレージ)

## KV — Namespace の管理

```bash
# Namespace を作成
pnpm wrangler kv namespace create MY_KV

# 一覧
pnpm wrangler kv namespace list

# 削除
pnpm wrangler kv namespace delete --namespace-id <ID>
```

## KV — キーの管理

```bash
# 値を書き込む
pnpm wrangler kv key put --namespace-id <ID> "key" "value"

# 有効期限付きで書き込む (秒)
pnpm wrangler kv key put --namespace-id <ID> "key" "value" --expiration-ttl 3600

# 値を取得
pnpm wrangler kv key get --namespace-id <ID> "key"

# キー一覧
pnpm wrangler kv key list --namespace-id <ID>

# キーを削除
pnpm wrangler kv key delete --namespace-id <ID> "key"

# JSON から一括書き込み
pnpm wrangler kv bulk put --namespace-id <ID> data.json
```

## KV — 設定バインディング

```jsonc
{
  "kv_namespaces": [
    { "binding": "CACHE", "id": "<NAMESPACE_ID>" }
  ]
}
```

---

## R2 — バケットの管理

```bash
# バケットを作成
pnpm wrangler r2 bucket create my-bucket

# ロケーションヒント付きで作成
pnpm wrangler r2 bucket create my-bucket --location wnam

# 一覧
pnpm wrangler r2 bucket list

# バケット情報を取得
pnpm wrangler r2 bucket info my-bucket

# Worker経由で使う非公開バケットの公開状態を確認
pnpm wrangler r2 bucket dev-url get my-bucket
pnpm wrangler r2 bucket domain list my-bucket

# 削除
pnpm wrangler r2 bucket delete my-bucket
```

## R2 — オブジェクトの管理

```bash
# アップロード
pnpm wrangler r2 object put my-bucket/path/file.txt --file ./local-file.txt

# ダウンロード
pnpm wrangler r2 object get my-bucket/path/file.txt

# 削除
pnpm wrangler r2 object delete my-bucket/path/file.txt
```

## R2 — 設定バインディング

```jsonc
{
  "r2_buckets": [
    { "binding": "ASSETS", "bucket_name": "my-bucket" }
  ]
}
```

Worker binding経由で認可して配信するバケットは、`r2.dev`とCustom Domainを有効にしない。`dev-url get`が`Public access ... is disabled`、`domain list`が空であることを確認する。存在確認のために実データや検証用オブジェクトをアップロードしない。

複数Cloudflare Accountがある場合は`pnpm wrangler whoami`を先に実行する。新規の自社アプリはチーム用共有Accountを既定にし、個人Accountへ同名バケットを作らない。既存バケットが別Accountにある場合は移行判断で停止する。
