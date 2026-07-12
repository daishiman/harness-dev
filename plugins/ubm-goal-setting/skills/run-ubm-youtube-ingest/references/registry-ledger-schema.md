# registry-ledger-schema — youtube-registry.json の schema と初期化手順

`knowledge/youtube-registry.json` の正本スキーマ。source registry (priority/status/channel identity) + authoritative video snapshot + reconciliation ledger を1ファイルに束ねる。**実ファイルは本 build では作成せず、運用時に one-shot が自動初期化するか、本手順で手作りする** (実データ投入は運用時)。

## 置き場

`plugins/ubm-goal-setting/knowledge/youtube-registry.json` (plugin-root `knowledge/` 直下・既存 `registry.json`/`router.json`/`schema.json` と同層の共有データ)。

## schema

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

- **sources**: 先頭が `required-primary` (提示済み『北原孝彦のコンサルティング』・全量必須)。第2アカウントは URL/handle/channel_id 未提示のため `status=pending-identification` で保持し、その未同定を required-primary 停止の理由にしない。**pending placeholder は未同定 channel が残るときだけ置く** (`--channel` を 2 つ以上明示して全 source 確定済みなら幽霊 pending を作らない)。
- **cursor**: channel ごとの**最終 run 記録** (`last_run_at`/`last_run_id` の watermark)。**増分 discovery cursor ではない** — discovery は毎回 pagination 完走し、差分性 (二回目 0 件) は `videos[vid].state==ingested` の `already_ingested` skip が担保する。cursor は provenance/監査用の last-run メタに徹する。
- **lease**: `holder` が invocation ごとに一意な token (`run-N:<hex>`)、`expires_at` が epoch。**取得直後に disk へ永続化**し、稼働中 lease を別 run が読めるようにする。未失効 lease を別 run が持つ間は no-op (scheduler 二重発火の多重処理防止)。run 終了時に `{holder: null, expires_at: 0}` へ解放。異常終了で解放されなかった lease は TTL 失効後に次 run が奪取して回復する。
- **videos**: `idempotency_key=video_id`。状態は下記4値。分母 (discovered_total) は authoritative snapshot 全 ID で、取得不能を除外して縮めない。`provenance_gaps` は必須 provenance (video_id/source_url/published_at) 欠落時の列挙で、非空の間は `ingested` にせず `temporary_failure` で保留する (正規化ソース frontmatter は `references/normalized-source-schema.md` が正本)。
- **state 遷移**:
  - `ingested`: 正規化ソースを persist 済み。二度目は skip (冪等)。
  - `temporary_failure`: 一時失敗。次 run で retry、成功で `ingested` へ。`attempts` を加算し `--max-retries` 超過で alert (状態は保持)。
  - `terminal_unavailable`: 恒久取得不能。retry しない。
  - `waived`: ユーザー承認で全量対象から除外。**`waiver_ref` (承認参照) 必須**。無承認の握り潰しは禁止。

## 初期化手順

1. **one-shot 自動初期化 (推奨)**: `run-youtube-sync-oneshot.py` は `--registry` が未存在なら required-primary (`--channel` 先頭) + pending 第2source で空 registry を初期化して書き込む。`--dry-run` 時は初期化も書込まない。
2. **手作り**: 上記 schema の空形 (`videos={}`, `ledger.runs=[]`, `lease` 解放, `sources` に required-primary + pending) を配置する。`schema_version="1.0.0"`。
3. registry は plugin 同梱 `knowledge/` 配下ゆえ `ubm-write-path-guard` 対象外 (vault 外)。

## 完全性ゲート (C03) との接点

`check-youtube-backfill-completeness.py` (route C03 が実装) は本 registry の `videos` を分母、authoritative video-list を snapshot として突合し、`FULL_BACKFILL_PASS = ingested==discovered_total かつ temporary_failure==0 かつ unapproved_unavailable==0` を二値判定する。`waived` は `waiver_ref` 付きに限り分母から控除できる。除外による分母縮小は exit1。
