# デプロイ・バージョン管理・Pages

## Worker のデプロイ

```bash
# 本番へデプロイ
pnpm wrangler deploy

# 環境を指定してデプロイ
pnpm wrangler deploy --env staging

# ドライラン (デプロイせず検証のみ)
pnpm wrangler deploy --dry-run

# ダッシュボードで設定した変数を保持する
pnpm wrangler deploy --keep-vars

# コードを minify する
pnpm wrangler deploy --minify
```

**大きな変更の前には `--dry-run`** で検証してからデプロイする。

## バージョンとロールバック

```bash
# 直近のバージョン一覧
pnpm wrangler versions list

# 特定バージョンの詳細
pnpm wrangler versions view <VERSION_ID>

# 直前のバージョンへロールバック
pnpm wrangler rollback

# 特定バージョンへロールバック
pnpm wrangler rollback <VERSION_ID>
```

## Worker の削除

```bash
pnpm wrangler delete
```

## 起動時間のプロファイル

```bash
# 起動時間を計測し、起動時間上限を超えるスクリプトを検出する
pnpm wrangler check startup
```

CPU プロファイルが生成されるため、起動時間上限超過エラーの原因特定に使う。

## Pages (フロントエンドのデプロイ)

```bash
# Pages プロジェクトを作成
pnpm wrangler pages project create my-site

# ディレクトリを Pages へデプロイ
pnpm wrangler pages deploy ./dist

# ブランチを指定してデプロイ
pnpm wrangler pages deploy ./dist --branch main

# デプロイ一覧
pnpm wrangler pages deployment list --project-name my-site
```

## 認証

```bash
# 認証状態の確認
pnpm wrangler whoami

# ログイン
pnpm wrangler login
```
