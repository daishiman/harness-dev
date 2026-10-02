---
name: wrangler
description: Cloudflare Workers CLIでWorkers、KV、R2、D1、Vectorize、Hyperdrive、Workers AI、Containers、Queues、Workflows、Pipelines、Secrets Storeを開発・デプロイ・管理する。Wranglerコマンドを実行する前に使用し、最新の公式ドキュメントに基づく構文と安全規則を確認する。
---

# Wrangler CLI

> 本ファイルは cloudflare/skills（Apache-2.0）を基に改変しています。詳細は リポジトリルートの ATTRIBUTION.md を参照。
>
> **原則: 仕様の確認と調査は MCP、deploy / secret put / d1 migrations apply は監査性・可逆性・秘密保護のため wrangler CLI を既定にする**(MCP に能力が無いからではない)。操作別の既定表と MCP 不通時の復旧は `references/mcp-vs-cli-routing.md` が唯一の正本。

Wrangler の CLI フラグ・設定フィールド・サブコマンドに関する知識は古くなっている可能性がある。**事前学習した知識より取得 (retrieval) を優先すること。**

## 最初に: package managerとWranglerを確認する

既存projectではlockfileを正本にし、package managerを勝手に移行しない。

| 検出したlockfile | Wrangler command |
|---|---|
| `pnpm-lock.yaml` / `pnpm-workspace.yaml` | `pnpm exec wrangler` |
| `package-lock.json` / `npm-shrinkwrap.json` | `npx --no-install wrangler` |
| `yarn.lock` | `yarn exec wrangler` |

新規AIDD projectでlockfileがまだない場合だけpnpmを既定にする。以下の例は、このrepositoryの既定である`pnpm exec wrangler`で表記する。npm/yarn projectでは上表のprefixへ置き換え、subcommandとflagsは同じに保つ。

```bash
pnpm exec wrangler --version   # v4.x 以上が必要
```

未インストールなら:

```bash
pnpm add -D wrangler@latest
```

既存lockfileがない新規AIDD projectはpnpmへ統一する。既存npm/yarn projectへpnpm lockfileを追加しない。可能な限りAPI requestを手で組み立てず、project-localなWranglerを使う。

`You installed workerd on another platform`、`workerd-darwin-64`、`workerd-darwin-arm64`が出た場合、別PCの`node_modules`やlockfile削除で回避しない。`pnpm-workspace.yaml`の`supportedArchitectures`を確認してから次を実行する。

```bash
pnpm install --force --frozen-lockfile
pnpm exec wrangler --version
```

## 複数Accountの安全規則

Cloudflareへ変更を加えるコマンドの前に、選択したpackage managerの`wrangler whoami`で対象Accountを確認する。このrepositoryでは`pnpm exec wrangler whoami`を使う。チーム用共有Accountと個人Accountの両方があり、新しく自社アプリを作る場合は**チーム用Accountを既定選択**する。個人Accountは利用者の明示指定時だけ。

既存`wrangler.jsonc`やWorker/D1/R2が特定Accountにある場合は、その所有先を優先して照合する。チームへ移したい場合も別Accountへ同名リソースを勝手に作らず、移行タスクとして止める。Account不一致時はcreate / secret put / migrations apply / deployを実行しない。

## 最新情報の取得先

コマンドや設定を書く・レビューする前に**最新**の情報を取得する。CLI フラグ、設定フィールド、バインディング形状を記憶に頼って書かない。

| ソース | 取得方法 | 用途 |
|--------|----------|------|
| Wrangler docs | `https://developers.cloudflare.com/workers/wrangler/` | CLI コマンド、フラグ、設定リファレンス |
| Wrangler 設定スキーマ | `node_modules/wrangler/config-schema.json` | 設定フィールド、バインディング形状、許可値 |
| Cloudflare docs | 検索ツール または `https://developers.cloudflare.com/workers/` | API リファレンス、compatibility date/flag |

## 主要原則

- **`wrangler.jsonc` を使う**: TOML より JSON を優先。新機能は JSON 専用のものがある。バージョン管理し、Worker 設定の唯一の情報源として扱う。
- **`compatibility_date` を設定する**: 直近 30 日以内の日付を使い、四半期ごとに更新する。
- **設定変更後は `pnpm exec wrangler types`**: TypeScript バインディングを再生成する。CI のビルドステップにも入れてバインディング不一致を検出する。
- **ローカル開発はデフォルトでローカルストレージ**: バインディングは `remote: true` を指定しない限りローカルシミュレーション。
- **環境で staging/production を分ける**: `env.staging` / `env.production` を設定に定義する。
- **ローカルで先にテストする**: デプロイ前に `pnpm exec wrangler dev` で確認し、大きな変更前は `pnpm exec wrangler deploy --dry-run` で検証する。
- **自動プロビジョニングを使う**: リソース ID を省略するとデプロイ時に自動作成される。

## 落とし穴 (gotchas)

- **シークレットをコマンドに埋め込まない**: 値を CLI 引数で渡す、`echo` でパイプする、ログ出力する、ハードコードする — いずれも禁止。対話プロンプト (`pnpm exec wrangler secret put`)、ファイル入力 (`< key.pem`、`secret bulk`)、CI の安全な環境変数を使う。ローカル用シークレットは `.dev.vars` に置き、設定ファイルにはコミットしない。
- **secret putの前にsecret list**: 同名があれば新規設定ではなくローテーション。既存ログインの無効化や全セッション失効を説明し、明示承認なしに上書きしない。
- **D1 の `--remote` / `--local` を明示する**: 取り違えると本番データを操作する事故になる。
- **Workers AI は常にリモート実行**: ローカル開発中でも利用料金が発生する。バインディングには `remote: true` が必要。
- **リモート推奨のバインディング**: AI (必須)、Vectorize、Browser Rendering、mTLS、Images。
- **バインディングが `undefined`**: バインディング名が設定と完全一致しているか確認する。
- **起動時間の上限超過**: `pnpm exec wrangler check startup` でプロファイルを取る。
- **レジストリ認証情報をハードコードしない**: 環境変数経由で渡す (Containers)。
- **Hyperdrive のパスワード・接続文字列も環境変数経由**にする。

## 頻出コマンド早見表

| やりたいこと | コマンド |
|--------------|----------|
| ローカル開発サーバー起動 | `pnpm exec wrangler dev` |
| デプロイ | `pnpm exec wrangler deploy` |
| デプロイのドライラン | `pnpm exec wrangler deploy --dry-run` |
| TypeScript 型を生成 | `pnpm exec wrangler types` |
| 起動時間をプロファイル | `pnpm exec wrangler check startup` |
| ライブログを見る | `pnpm exec wrangler tail` |
| 直前バージョンへロールバック | `pnpm exec wrangler rollback` |
| シークレットを設定 | `pnpm exec wrangler secret put API_KEY` |
| D1 マイグレーション適用 (本番) | `pnpm exec wrangler d1 migrations apply my-db --remote` |
| Worker を削除 | `pnpm exec wrangler delete` |
| 認証状態の確認 | `pnpm exec wrangler whoami` |
| 新規プロジェクト作成 | `pnpm exec wrangler init my-worker` / `pnpm create cloudflare@latest my-app` |

## サービス別の頻出コマンド

```bash
# D1
pnpm exec wrangler d1 create my-db
pnpm exec wrangler d1 execute my-db --local  --command "SELECT * FROM users"
pnpm exec wrangler d1 execute my-db --remote --file ./schema.sql
pnpm exec wrangler d1 migrations create my-db create_users_table
pnpm exec wrangler d1 migrations apply my-db --local

# KV
pnpm exec wrangler kv namespace create MY_KV
pnpm exec wrangler kv key put --namespace-id <ID> "key" "value" --expiration-ttl 3600
pnpm exec wrangler kv key get --namespace-id <ID> "key"

# R2
pnpm exec wrangler r2 bucket create my-bucket
pnpm exec wrangler r2 object put my-bucket/path/file.txt --file ./local-file.txt

# シークレット (値は対話プロンプトかファイルで渡す)
pnpm exec wrangler secret put API_KEY
pnpm exec wrangler secret put PRIVATE_KEY < path/to/private-key.pem
pnpm exec wrangler secret list

# ログ
pnpm exec wrangler tail --status error
pnpm exec wrangler tail --search "error" --format json

# 環境を指定した実行/デプロイ
pnpm exec wrangler dev    --env staging
pnpm exec wrangler deploy --env staging

# cron ハンドラのローカルテスト
pnpm exec wrangler dev --test-scheduled   # → http://localhost:8787/__scheduled
```

## よく使うバインディング設定

```jsonc
{
  "vars": { "ENVIRONMENT": "production" },
  "kv_namespaces": [{ "binding": "KV", "id": "<KV_NAMESPACE_ID>" }],
  "r2_buckets":    [{ "binding": "BUCKET", "bucket_name": "my-bucket" }],
  "d1_databases":  [
    { "binding": "DB", "database_name": "my-db", "database_id": "<DB_ID>",
      "migrations_dir": "./migrations" }
  ],
  "ai": { "binding": "AI" },
  "vectorize":  [{ "binding": "VECTOR_INDEX", "index_name": "my-index" }],
  "hyperdrive": [{ "binding": "HYPERDRIVE", "id": "<HYPERDRIVE_ID>" }],
  "durable_objects": {
    "bindings": [{ "name": "COUNTER", "class_name": "Counter" }]
  },
  "queues": {
    "producers": [{ "binding": "MY_QUEUE", "queue": "my-queue" }],
    "consumers": [{ "queue": "my-queue", "max_batch_size": 10 }]
  },
  "workflows": [
    { "binding": "MY_WORKFLOW", "name": "my-workflow", "class_name": "MyWorkflow" }
  ],
  "triggers": { "crons": ["0 * * * *"] },
  "observability": { "enabled": true, "head_sampling_rate": 1 },
  "env": {
    "staging": { "name": "my-worker-staging", "vars": { "ENVIRONMENT": "staging" } }
  }
}
```

Pipelines / Secrets Store / Containers のバインディング形状は各リファレンスを参照。

## トラブルシュート早見表

| 問題 | 対処 |
|------|------|
| `command not found: wrangler` | `pnpm add -D wrangler@latest` |
| 認証エラー | `pnpm exec wrangler login` |
| `workerd`のplatform/CPU不一致 | `supportedArchitectures`確認後に`pnpm install --force --frozen-lockfile` |
| 複数Accountで対象が不明 | 既存リソース所有先を照合。新規ならチーム用Account、個人は明示指定時だけ |
| 起動時間の上限超過 | `pnpm exec wrangler check startup` でプロファイル |
| 設定変更後の型エラー | `pnpm exec wrangler types` |
| ローカル状態が消える | `.wrangler/state` を確認 |
| バインディングが undefined | 設定のバインディング名と完全一致しているか確認 |

## 詳細リファレンス

必要になったときに該当ファイルを読むこと。

| 状況 | 読むファイル |
|------|--------------|
| `wrangler.jsonc` を書く・バインディングを追加する・型生成をする | `references/config.md` |
| ローカル開発、リモートバインディング、`.dev.vars`、Vitest / scheduled のテスト | `references/dev-local.md` |
| デプロイ、バージョン管理とロールバック、Pages、認証 | `references/deploy.md` |
| Worker シークレット、Secrets Store の操作 | `references/secrets.md` |
| D1 のデータベース作成、SQL 実行、マイグレーション、エクスポート | `references/d1.md` |
| KV Namespace / キー操作、R2 バケット / オブジェクト操作 | `references/kv-r2.md` |
| Workers AI のモデル一覧、Vectorize のインデックス、Hyperdrive の設定 | `references/ai-vectorize-hyperdrive.md` |
| Queues、Workflows とそのインスタンス、Pipelines | `references/queues-workflows-pipelines.md` |
| コンテナイメージのビルド/プッシュ、外部レジストリ設定 | `references/containers.md` |
| ログの tail、observability 設定、エラーの切り分け | `references/observability-troubleshooting.md` |

## 最小構成のスターター

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2026-01-01"
}
```

バインディングを含むフル構成の例は `references/config.md` にある。
