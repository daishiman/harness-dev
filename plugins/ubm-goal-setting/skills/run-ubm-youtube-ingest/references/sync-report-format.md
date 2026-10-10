# `sync-report-format` — 1回きりの実行が出す同期の報告の正本形式

`run-youtube-sync-oneshot.py` が標準出力へ出す JSON。スケジューラ / R4 / 受入テストが消費する照合の結果台帳。**書込 (登録簿/`source-out`) と分離**され、`--dry-run` でも報告は出る (件数は「反映予定」を示すが永続化しない)。

## スキーマ

```json
{
  "schema_version": "1.0.0",
  "run_id": "run-N",
  "mode": "sync | backfill | url",
  "dry_run": false,
  "channels": ["<handle>", "..."],
  "discovered_total": 0,
  "ingested": 0,
  "already_ingested": 0,
  "temporary_failure": 0,
  "terminal_unavailable": 0,
  "waived": 0,
  "alerts": ["[temporary_failure] <video_id> (attempt N): ...", "..."],
  "ingested_video_ids": ["v1"],
  "stopped_reason": null
}
```

## フィールド規約

- **`run_id`**: `run-<len(ledger.runs)+1>`。登録簿の状態から決定論で導出 (タイムスタンプを焼き込まない)。
- **`discovered_total`**: 正となるスナップショットのユニークな `video_id` の数 (= 全量性の分母)。
- **`ingested`**: 本実行で新規に永続化した件数。**冪等性の核**: 同一入力の二回目は `ingested=0`、`already_ingested` が増える。
- **`already_ingested`**: 既に `ingested` 済みで飛ばした件数 (冪等キー=`video_id`)。
- **`temporary_failure` / `terminal_unavailable` / `waived`**: 各状態に写像された件数。取得不能を `ingested` に混ぜない。
- **`alerts`**: 監視向けの行。`[temporary_failure]` / `[terminal_unavailable]` / `[quota]` / `[auth]` / `[retry_exhausted]` / `[lease]` を接頭辞にする。
- **`stopped_reason`**: `null` | `quota` | `auth` | `lease_held`。穏当な停止の理由。停止でも終了コード 0 (スケジューラが次の周期で再開)。`lease_held` は稼働中の実行権の占有（lease）を別の実行が保持している間の、何もしない終了 (二重起動の排他)。(`aborted_after_lease` は `YT_ONESHOT_ABORT_AFTER_LEASE` を立てたときのみ現れるテスト専用のフォールト注入値で、通常運用では出ない。)

## 受入テストが照合する不変則 (OUT1)

1回きりの実行の責務は正規化ソース(.md)+登録簿(台帳) までの決定論での確定で、ナレッジ/グラフへの反映は
スキルのセッションが `ingested>0` のとき R3 相当を再実行して担う (スケジューラによる直接起動は次回のスキル実行へ持ち越し)。
`tests/test_youtube_sync_oneshot.py` が `fixture` の取得元で1回きりの実行の単体について以下を確認する:

1. 新着1件 → 1回目 `ingested==1`・正規化ソース(.md) が一度だけ書かれ `registry.videos[vid].state==ingested`。
2. 二回目 → `ingested==0`・`already_ingested==1`・ソース .md は増えない。
3. `TemporaryFailure` → `ingested==0`・`temporary_failure==1`・`state==temporary_failure`。検証用の入力データの復旧後の再試行の実行で `ingested==1`・`attempts==2`・`state==ingested`。
4. `--dry-run` → 登録簿は未生成・`source-out` へ .md 書込0・実行権の占有は不変 (報告の件数は反映予定として表示)。
5. 複数ページ → ページ送りの完走で `discovered_total` が全 ID。
6. `QuotaExceeded` → `stopped_reason==quota`・`ingested==0`・警告に `quota`。
7. 実行権の占有 → 稼働中の占有をディスクへ永続化し二回目の実行が `stopped_reason==lease_held` で何もせず、有効期限の失効後は奪取して `ingested==1`。
8. 必須の出所情報の欠落 (video_id/source_url/published_at) → `ingested==0`・`temporary_failure==1`・登録簿に `provenance_gaps` を記録・.md 書込0。
9. フロントマター → `references/normalized-source-schema.md` の方言 (`source_type`/引用符付きの区間/`coverage` の列挙値/`provenance_gaps`/`untrusted_data_notice`) に準拠。

## 終了コード

- `0`: 完了 (`quota`/`auth`/`lease` による穏当な停止を含む)。
- `1`: 入力/登録簿の破損。壊れた登録簿を上書きしない。
- `2`: 使い方のエラー (引数不足等)。
