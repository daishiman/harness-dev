# Observability とトラブルシューティング

## ログのストリーミング (tail)

```bash
# ライブログをストリーム
pnpm wrangler tail

# 特定の Worker を tail
pnpm wrangler tail my-worker

# ステータスでフィルタ
pnpm wrangler tail --status error

# 検索語でフィルタ
pnpm wrangler tail --search "error"

# JSON 出力
pnpm wrangler tail --format json
```

## ロギングの設定

```jsonc
{
  "observability": {
    "enabled": true,
    "head_sampling_rate": 1
  }
}
```

## よくある問題

| 問題 | 解決方法 |
|------|----------|
| `command not found: wrangler` | インストールする: `pnpm add -D wrangler@latest` |
| 認証エラー | `pnpm wrangler login` を実行 |
| 起動時間の上限超過 | `pnpm wrangler check startup` で起動をプロファイルし CPU プロファイルを生成する |
| 設定変更後の型エラー | `pnpm wrangler types` を実行 |
| ローカルストレージが永続化されない | `.wrangler/state` ディレクトリを確認 |
| Worker でバインディングが undefined | バインディング名が設定と完全一致しているか確認 |

## デバッグコマンド

```bash
# 認証状態の確認
pnpm wrangler whoami

# Worker の起動時間をプロファイル
pnpm wrangler check startup

# 設定スキーマのドキュメントを開く
pnpm wrangler docs configuration

# バージョン確認 (v4.x 以上が必要)
pnpm wrangler --version
```
