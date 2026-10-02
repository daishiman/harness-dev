# サーバーコスト最適化・パフォーマンス最適化

## 1. コスト原則（Cloudflare無料枠を守る）

数値・詳細ガードレールは `better-auth-google-gate/references/free-tier-guardrails.md` が正。要点:

- Workers Free: 10万リクエスト/日。超過は課金ではなく**エラー**。
- D1 Free: Rows Read 500万/日、Written 10万/日。超過はクエリエラー。
- リセットは00:00 UTC（日本時間 原則9:00）。

### 実装ガードレール

- ポーリング禁止。必要ならロングポーリングやWebSocket（Durable Objects）か、間隔を分単位に。
- クライアントの無限リトライ禁止。指数バックオフ+上限回数。
- 一覧APIは`LIMIT`+ページネーション必須（1ページ最大100件）。`SELECT *`禁止、必要列のみ。
- WHERE/ORDER BY列にインデックス。N+1をJOINまたはバッチで解消。
- ページ閲覧ごとのINSERT、リクエストごとの`last_seen_at`更新、1文字ごとの自動保存を禁止（デバウンス）。
- 画面初期表示のAPI呼び出しは1〜2本にまとめる。同一データの重複取得禁止。
- 静的アセットはWorkerを経由させずAssetsで配信する。

### LLM APIコスト

LLM組込アプリは Skill `llm-api-integration`（設計原則）と Skill `llm-cost-simulator`（試算）を使う。要点: 判別タスクはminiモデルファースト、出力トークン最小化、usage可視化、暴走時のサーキットブレーカー。

## 2. パフォーマンス原則

### バックエンド

- **キャッシュ階層を先に設計する**: 静的アセット（immutable+ハッシュ付きファイル名）→ CDNキャッシュ（Cache-Control）→ アプリ内（KV/メモ化）→ D1。
- 変わらないマスタデータはKVまたはWorkerレスポンスのCache-Controlで配る。D1へ毎回問い合わせない。
- 重い集計はリクエスト時に計算せず、書き込み時に集計テーブルを更新するか、Cron Triggersで事前計算。
- レスポンスはストリーミング可能ならストリームで返す（LLM応答は特に）。

### フロントエンド

- 初期バンドルを小さく: ルート単位のコード分割、重いライブラリの動的import、未使用依存の削除。
- 画像: 適切なサイズ+`loading="lazy"`+モダンフォーマット。ヒーロー画像のみpreload。
- データ取得: 楽観的更新+スケルトンで知覚パフォーマンスを上げる（体感速度の規律は Skill ux-design）。
- Core Web Vitals（LCP/INP/CLS）の実測は Skill `web-perf` で行う。リリース前にLCP 2.5秒以内を確認。

### 計測してから直す

- 推測で最適化しない。`wrangler tail`・D1 Metrics（rows_read/rows_written）・web-perfの実測値で当たりを付けてから修正する。
- 最適化のBefore/Afterを数値で報告する。
