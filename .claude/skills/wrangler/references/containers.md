# Containers

## イメージのビルドとプッシュ

```bash
# コンテナイメージをビルド
pnpm wrangler containers build -t my-app:latest .

# ビルドとプッシュを一度に実行
pnpm wrangler containers build -t my-app:latest . --push

# 既存イメージを Cloudflare レジストリへプッシュ
pnpm wrangler containers push my-app:latest
```

## コンテナの管理

```bash
# 一覧
pnpm wrangler containers list

# 情報を取得
pnpm wrangler containers info <CONTAINER_ID>

# 削除
pnpm wrangler containers delete <CONTAINER_ID>
```

## イメージの管理

```bash
# レジストリ内のイメージ一覧
pnpm wrangler containers images list

# イメージを削除
pnpm wrangler containers images delete my-app:latest
```

## 外部レジストリの管理

> **セキュリティ**: レジストリの認証情報をコマンドにハードコードしてはいけない。環境変数を使う。

```bash
# 設定済みレジストリの一覧
pnpm wrangler containers registries list

# 外部レジストリを設定 (例: ECR)
pnpm wrangler containers registries configure <DOMAIN> \
  --aws-access-key-id "$AWS_ACCESS_KEY_ID"

# DockerHub を設定
pnpm wrangler containers registries configure <DOMAIN> \
  --dockerhub-username "$DOCKERHUB_USERNAME"

# レジストリ設定を削除
pnpm wrangler containers registries delete <DOMAIN>
```
