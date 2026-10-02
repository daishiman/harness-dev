# 無料枠ガードレール（Workers / D1 / Logs）

数値は2026-07時点の公式情報。実装前に公式で最新値を確認する。
- Workers: https://developers.cloudflare.com/workers/platform/limits/ ／ https://developers.cloudflare.com/workers/platform/pricing/
- D1: https://developers.cloudflare.com/d1/platform/limits/ ／ https://developers.cloudflare.com/d1/platform/pricing/

## Workers Free
- **100,000リクエスト/日**。超過するとError 1027（自動課金ではなくエラー）

実装ガードレール：
- 静的ファイルを不要にWorker経由で処理しない
- ポーリング回避、画面ごとのAPI呼び出しをまとめる、同一データの重複取得禁止
- `/api/auth/session`（相当）を短時間に連打しない
- クライアントの無限リトライ禁止。失敗時は指数バックオフ
- Bot対策、開発と本番の負荷分離

## D1 Free

| 項目 | 上限 |
|---|---:|
| Rows read | 5,000,000行/日 |
| Rows written | 100,000行/日 |
| 合計ストレージ | 5GB |
| 1DBの最大サイズ | 500MB |
| DB数 | 10 |
| Point-in-time recovery | 7日 |

- 無料枠は00:00 UTC（日本時間 原則9:00）にリセット
- 超過時は自動課金ではなく**D1クエリがエラー**になる → 認証後のプロフィール取得や一覧APIが落ちる

### 読み取りガードレール（必須）
- WHERE条件列にインデックス／`SELECT *`禁止・必要列のみ／`LIMIT`必須
- 一覧APIはページネーション（1ページ最大100件）／N+1回避
- Better AuthのDBセッションは読み取りコストを設計段階で見積もる（known-pitfalls.md参照）
- 管理画面の全件集計を毎リクエスト実行しない

```sql
-- 悪い例
SELECT * FROM audit_logs;
-- 良い例
SELECT id, action, created_at FROM audit_logs
WHERE organization_id = ?1 AND created_at < ?2
ORDER BY created_at DESC LIMIT 50;
```

### 書き込みガードレール（禁止事項）
- ページ閲覧ごとのアクセス履歴INSERT
- リクエストごとの`last_seen_at`更新
- セッション確認ごとの監査ログ
- 1文字入力ごとの自動保存（数秒デバウンスにする）
- 同一内容の重複更新（更新前に差分確認）
- 不要なトークン保存

推奨：監査ログは重要操作のみ／`last_login_at`はログイン時のみ／期限切れデータの削除方針を持つ

### 使用量確認
Cloudflare Dashboard → Workers & Pages → D1 → 対象DB → Metrics → Row Metrics。
各クエリの`meta.rows_read` / `meta.rows_written`も確認。

## Workers Logs
Freeでも利用可（1日200,000イベント、保持3日）。機密のログ出力禁止ルールは `security-and-testing.md` §6参照。

