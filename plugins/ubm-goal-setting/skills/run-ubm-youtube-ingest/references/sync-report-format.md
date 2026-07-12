# sync-report-format — one-shot sync report の正本形式

`run-youtube-sync-oneshot.py` が stdout へ出す JSON。scheduler / R4 / 受入テストが消費する reconciliation の結果台帳。**書込 (registry/source-out) と分離**され、`--dry-run` でも report は出る (件数は「反映予定」を示すが永続化しない)。

## schema

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

- **run_id**: `run-<len(ledger.runs)+1>`。registry 状態から決定論導出 (timestamp を焼き込まない)。
- **discovered_total**: authoritative snapshot のユニーク video_id 数 (= 全量性の分母)。
- **ingested**: 本 run で新規に persist した件数。**冪等性の核**: 同一入力の二回目は `ingested=0`、`already_ingested` が増える。
- **already_ingested**: 既に `ingested` 済みで skip した件数 (idempotency key=video_id)。
- **temporary_failure / terminal_unavailable / waived**: 各状態に写像された件数。取得不能を ingested に混ぜない。
- **alerts**: 監視向け行。`[temporary_failure]` / `[terminal_unavailable]` / `[quota]` / `[auth]` / `[retry_exhausted]` / `[lease]` を prefix にする。
- **stopped_reason**: `null` | `quota` | `auth` | `lease_held`。graceful stop の理由。stop でも exit0 (scheduler が次 cadence で再開)。`lease_held` は稼働中 lease を別 run が保持している間の no-op (二重起動排他)。(`aborted_after_lease` は `YT_ONESHOT_ABORT_AFTER_LEASE` を立てたときのみ現れる test-only フォールト注入値で、通常運用では出ない。)

## 受入テストが照合する不変則 (OUT1)

one-shot の責務は正規化ソース(.md)+registry(ledger) までの決定論確定で、knowledge/graph 反映は
skill セッションが `ingested>0` のとき R3 相当を再実行して担う (scheduler 直接起動は次回 skill 実行へ持ち越し)。
`tests/test_youtube_sync_oneshot.py` が fixture provider で one-shot 単体の以下を確認する:

1. 新着1件 → 1回目 `ingested==1`・正規化ソース(.md) が一度だけ書かれ registry.videos[vid].state==ingested。
2. 二回目 → `ingested==0`・`already_ingested==1`・ソース .md は増えない。
3. `TemporaryFailure` → `ingested==0`・`temporary_failure==1`・state==temporary_failure。fixture 復旧後の retry run で `ingested==1`・attempts==2・state==ingested。
4. `--dry-run` → registry 未生成・source-out へ .md 書込0・lease 不変 (report の件数は反映予定として表示)。
5. multi-page → pagination 完走で `discovered_total` が全 ID。
6. `QuotaExceeded` → `stopped_reason==quota`・`ingested==0`・alert に quota。
7. lease → 稼働中 lease を disk へ永続化し二回目 run が `stopped_reason==lease_held` で no-op、TTL 失効後は奪取して `ingested==1`。
8. provenance 必須欠落 (video_id/source_url/published_at) → `ingested==0`・`temporary_failure==1`・registry に provenance_gaps 記録・.md 書込0。
9. frontmatter → `references/normalized-source-schema.md` の方言 (source_type/引用符付き span/coverage enum/provenance_gaps/untrusted_data_notice) に準拠。

## exit code

- `0`: 完了 (quota/auth/lease の graceful stop を含む)。
- `1`: 入力/registry 破損。壊れた registry を上書きしない。
- `2`: usage エラー (引数不足等)。
