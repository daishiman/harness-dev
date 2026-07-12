# Database スクリプトテンプレート指示

> **読み込み条件**: type === "database" の場合
> **対応ランタイム**: Node.js, Python

---

## 目的

データベース操作（SQL実行、マイグレーション等）を行うスクリプトを生成する。

---

## AIへの実装指示

### 必須機能

1. **接続管理**
   - 接続文字列からの接続
   - 接続プール管理
   - 安全な接続終了

2. **クエリ実行**
   - SELECT/INSERT/UPDATE/DELETE
   - パラメータバインディング（SQLインジェクション防止）
   - トランザクション管理

3. **結果処理**
   - 結果セットの取得
   - 影響行数の取得
   - エラー処理

### 対応データベース

| DB | Node.js | Python |
|----|---------|--------|
| PostgreSQL | pg | psycopg2, asyncpg |
| MySQL | mysql2 | mysql-connector-python |
| SQLite | better-sqlite3 | sqlite3 |

### 環境変数

- `{{DATABASE_URL}}`: 接続文字列
- `{{DB_HOST}}`, `{{DB_PORT}}`, `{{DB_USER}}`, `{{DB_PASSWORD}}`, `{{DB_NAME}}`: 個別指定

### 引数仕様

| 引数 | 必須 | 説明 |
|------|------|------|
| --query | △ | 実行するSQL |
| --file | △ | SQLファイルパス |
| --output | × | 結果出力先 |
| --format | × | 出力形式（json, csv, table） |

---

## 品質基準

- [ ] SQLインジェクション対策（パラメータバインディング必須）
- [ ] 接続エラーの適切な処理
- [ ] 長時間クエリのタイムアウト
- [ ] センシティブデータのログマスク
- [ ] 接続の確実なクローズ
