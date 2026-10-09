# `registry-ledger-schema` — `youtube-registry.json` のスキーマと初期化手順

`knowledge/youtube-registry.json` の正本スキーマ。ソース登録簿 (`priority`/`status`/チャンネルの識別情報) + 正となる動画一覧のスナップショット + 照合台帳を1ファイルに束ねる。**実ファイルは本ビルドでは作成せず、運用時に1回きりの実行が自動初期化するか、本手順で手作りする** (実データ投入は運用時)。

## 置き場

`plugins/ubm-goal-setting/knowledge/youtube-registry.json` (プラグインのルートの `knowledge/` 直下・既存 `registry.json`/`router.json`/`schema.json` と同層の共有データ)。

## 同時起動の排他

実書き込みでは、解決済み登録簿の隣に `<registryのファイル名>.lock` を作り、登録簿の読み込み前から最終保存までOSロックを保持する。原子的に置換する登録簿とは別のinodeを使う。ロックファイルは次回も同じinodeを使うため削除しない。dry-runではロックファイルを含め書き込みを行わない。スキルの正式実行では、このファイルの作成と保持も中央guardのpreviewの保存範囲・副作用説明に含める。

## スキーマ

```json
{
  "schema_version": "1.0.0",
  "sources": [
    {"priority": "required-primary", "handle": "@北原孝彦のコンサルティング", "channel_id": null, "status": "active"},
    {"priority": "secondary", "handle": null, "channel_id": null, "status": "pending-identification"}
  ],
  "cursor": {"<handle>": {"last_run_at": 0, "last_run_id": "run-N"}},
  "lease": {"holder": "run-N | null", "expires_at": 0},
  "videos": {
    "<video_id>": {
      "source": "<channel_id|handle>",
      "state": "ingested | temporary_failure | terminal_unavailable | waived",
      "idempotency_key": "<video_id>",
      "attempts": 1,
      "title": "...",
      "published_at": "2026-07-01",
      "first_seen_at": 0,
      "ingested_at": 0,
      "normalized_source": "YouTube/2026-07-01 - 題名.md",
      "origin": "caption | asr",
      "provenance_gaps": [],
      "waiver_ref": "<user 承認参照。state=waived 時 必須>"
    }
  },
  "ledger": {"runs": [{"run_id": "run-N", "at": 0, "mode": "sync", "discovered": 0, "ingested": 0, "temporary_failure": 0, "terminal_unavailable": 0, "waived": 0, "stopped_reason": null}]}
}
```

## フィールド規約

- **`sources`**: 先頭が `required-primary` (提示済み『北原孝彦のコンサルティング』・全量必須)。第2アカウントは URL/handle/channel_id 未提示のため `status=pending-identification` で保持し、その未同定を `required-primary` 停止の理由にしない。**`pending-identification` の仮置きは未同定のチャンネルが残るときだけ置く** (`--channel` を 2 つ以上明示して全ソース確定済みなら幽霊の仮置きを作らない)。
- **`cursor`**: チャンネルごとの**最終実行の記録** (`last_run_at`/`last_run_id` の目印)。**増分の洗い出しのための続きの位置ではない** — 洗い出しは毎回ページ送りを完走し、差分性 (二回目 0 件) は `videos[vid].state==ingested` の `already_ingested` による読み飛ばしが担保する。`cursor` は出所情報/監査用の最終実行のメタ情報に徹する。
- **`lease`**: `holder` が起動ごとに一意なトークン (`run-N:<hex>`)、`expires_at` がエポック時刻。**取得直後にディスクへ永続化**し、稼働中の実行権の占有を別の実行が読めるようにする。期限切れでない占有を別の実行が持つ間は何もしない (スケジューラの二重発火による多重処理の防止)。実行の終了時に `{holder: null, expires_at: 0}` へ解放。異常終了で解放されなかった占有は有効期限の失効後に次の実行が奪取して回復する。
- **`videos`**: `idempotency_key=video_id`。状態は下記4値。分母 (`discovered_total`) は正となるスナップショットの全 ID で、取得不能を除外して縮めない。`provenance_gaps` は必須の出所情報 (video_id/source_url/published_at) の欠落時の列挙で、非空の間は `ingested` にせず `temporary_failure` で保留する (正規化ソースのフロントマターは `references/normalized-source-schema.md` が正本)。
- **`normalized_source`**: 新規保存は normalized-source-schema.md「保存パスと動画の識別」の動画ID hex付き相対パス。既存ingestedの旧パスは有効な台帳として保持し、改名・再取得で自動移行しない。保存予定先がforeign video_idなら上書きせずtemporary_failureに保留する。
- **`state` の遷移**:
  - `ingested`: 正規化ソースを永続化済み。二度目は飛ばす (冪等)。
  - `temporary_failure`: 一時失敗。次の実行で再試行、成功で `ingested` へ。`attempts` を加算し `--max-retries` 超過で警告 (状態は保持)。
  - `terminal_unavailable`: 恒久的な取得不能。再試行しない。
  - `waived`: ユーザー承認で全量対象から除外。**`waiver_ref` (承認参照) 必須**。無承認の握り潰しは禁止。

## 初期化手順

1. **1回きりの実行による自動初期化 (推奨)**: `run-youtube-sync-oneshot.py` は `--registry` が未存在なら `required-primary` (`--channel` 先頭) + `pending-identification` の第2ソースで空の登録簿を初期化して書き込む。`--dry-run` 時は初期化も書込まない。
2. **手作り**: 上記スキーマの空形 (`videos={}`, `ledger.runs=[]`, `lease` 解放, `sources` に `required-primary` + `pending-identification`) を配置する。`schema_version="1.0.0"`。
3. 登録簿はプラグイン同梱の `knowledge/` 配下ゆえ `ubm-write-path-guard` の対象外 (vault 外)。

## 完全性ゲート (C03) との接点

`check-youtube-backfill-completeness.py` (経路 C03 が実装) は本登録簿の `videos` を分母、正となる動画一覧をスナップショットとして突合し、`FULL_BACKFILL_PASS = ingested==discovered_total かつ temporary_failure==0 かつ unapproved_unavailable==0` を二値判定する。`waived` は `waiver_ref` 付きに限り分母から控除できる。除外による分母縮小は終了コード 1。
