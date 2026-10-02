# Workers AI・Vectorize・Hyperdrive

## Workers AI

```bash
# 利用可能なモデル一覧
pnpm wrangler ai models

# ファインチューン一覧
pnpm wrangler ai finetune list
```

### 設定バインディング

```jsonc
{
  "ai": { "binding": "AI" }
}
```

**注意**: Workers AI は常にリモートで実行され、ローカル開発中でも利用料金が発生する。

---

## Vectorize (ベクトルデータベース)

### インデックスの管理

```bash
# 次元数を指定してインデックスを作成
pnpm wrangler vectorize create my-index --dimensions 768 --metric cosine

# プリセットで作成 (次元数/メトリックを自動設定)
pnpm wrangler vectorize create my-index --preset @cf/baai/bge-base-en-v1.5

# 一覧
pnpm wrangler vectorize list

# インデックス情報を取得
pnpm wrangler vectorize get my-index

# 削除
pnpm wrangler vectorize delete my-index
```

### ベクトルの管理

```bash
# NDJSON ファイルからベクトルを挿入
pnpm wrangler vectorize insert my-index --file vectors.ndjson

# クエリ
pnpm wrangler vectorize query my-index --vector "[0.1, 0.2, ...]" --top-k 10
```

### 設定バインディング

```jsonc
{
  "vectorize": [
    { "binding": "SEARCH_INDEX", "index_name": "my-index" }
  ]
}
```

---

## Hyperdrive (データベースアクセラレーター)

### 設定の管理

```bash
# 設定を作成
pnpm wrangler hyperdrive create my-hyperdrive \
  --origin-host db.example.com \
  --origin-port 5432 \
  --database my-database \
  --origin-user db-user \
  --origin-password "$DB_PASSWORD"

# 環境変数の接続文字列から作成
pnpm wrangler hyperdrive create my-hyperdrive \
  --connection-string "$HYPERDRIVE_CONNECTION_STRING"

# 一覧
pnpm wrangler hyperdrive list

# 詳細を取得
pnpm wrangler hyperdrive get <HYPERDRIVE_ID>

# 更新
pnpm wrangler hyperdrive update <HYPERDRIVE_ID> \
  --origin-password "$DB_PASSWORD"

# 削除
pnpm wrangler hyperdrive delete <HYPERDRIVE_ID>
```

パスワードや接続文字列は必ず環境変数経由で渡す。平文でコマンドに書かない。

### 設定バインディング

```jsonc
{
  "compatibility_flags": ["nodejs_compat"],
  "hyperdrive": [
    { "binding": "HYPERDRIVE", "id": "<HYPERDRIVE_ID>" }
  ]
}
```
