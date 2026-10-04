# シークレット管理

> **セキュリティ**: シークレットの値をコマンド引数として渡したり、`echo` でパイプしたりしてはいけない。
> 対話プロンプト (推奨)、ファイルからのパイプ、または `secret bulk` を使う。
> シークレットの値を出力・ログ出力・コマンドへのハードコードのいずれもしてはいけない。

## Worker シークレット

```bash
# 先に名前を確認。同名があれば次のputは「更新」になる
pnpm wrangler secret list

# シークレットを設定 — 対話プロンプト (推奨。wrangler が安全に値を尋ねる)
pnpm wrangler secret put API_KEY

# ファイルから設定 (PEM 鍵や CI 環境で有用)
pnpm wrangler secret put PRIVATE_KEY < path/to/private-key.pem

# シークレット一覧
pnpm wrangler secret list

# シークレットを削除
pnpm wrangler secret delete API_KEY

# JSON ファイルから一括設定 (このファイルはバージョン管理にコミットしない)
pnpm wrangler secret bulk secrets.json
```

## ローカル開発用シークレット

ローカル開発では `.dev.vars` を使う。詳細は [dev-local.md](dev-local.md) を参照。

## Secrets Store

### ストアの管理

```bash
# ストアを作成
pnpm wrangler secrets-store store create my-store

# ストア一覧
pnpm wrangler secrets-store store list

# ストアを削除
pnpm wrangler secrets-store store delete <STORE_ID>
```

### ストア内シークレットの管理

```bash
# ストアにシークレットを追加
pnpm wrangler secrets-store secret put <STORE_ID> my-secret

# ストア内のシークレット一覧
pnpm wrangler secrets-store secret list <STORE_ID>

# シークレットを取得
pnpm wrangler secrets-store secret get <STORE_ID> my-secret

# ストアからシークレットを削除
pnpm wrangler secrets-store secret delete <STORE_ID> my-secret
```

### 設定バインディング

```jsonc
{
  "secrets_store_secrets": [
    {
      "binding": "MY_SECRET",
      "store_id": "<STORE_ID>",
      "secret_name": "my-secret"
    }
  ]
}
```

## 原則

- **コマンドにシークレットを埋め込まない**: 対話プロンプト (`pnpm wrangler secret put`)、ファイル入力 (`pnpm wrangler secret bulk`)、または CI の安全な環境変数を使う。シークレットの値を echo・ログ出力・CLI 引数として渡してはいけない。
- **ローカルシークレットは `.dev.vars`**: 設定ファイルにシークレットをコミットしない。
- **既存値を通常セットアップで上書きしない**: `secret list`に同名があればローテーション。認証パスワードなら旧パスワードが使えなくなり、署名secretなら既存セッションが無効になる。影響を説明し、所有者が明示した場合だけ更新する。
- **コードrollbackではsecretは戻らない**: 戻す必要がある値はパスワードマネージャー等の承認済み保管先から再登録する。値をGitや運用ログへ残さない。
