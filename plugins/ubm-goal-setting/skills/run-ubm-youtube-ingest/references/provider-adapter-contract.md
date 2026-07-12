# provider-adapter-contract — YouTube 取得 provider 中立契約

`scripts/youtube_provider.py` が定義する取得契約の正本。具体 provider 製品 (YouTube Data API / 字幕取得ツール / 手動貼付等) は **late-bind** し、この 2 メソッドと typed error 分類だけを満たせば差し替え可能。取得契約・自動性・fallback は本ドキュメントで確定済みであり未確定にしない (boundary 指示)。

## I/F (2 メソッド)

### `list_channel_videos(channel: str, cursor: str | None) -> Page`

- **役割**: channel handle の公開動画一覧を1ページ返す。`cursor=None` で先頭ページ、以降は返却された `next_cursor` を渡して続きを取る。
- **完走契約**: consumer (R2 / one-shot) は `next_cursor is None` まで回して authoritative snapshot を全 ID で構築する。途中打ち切りは全量性 (IN1) 違反。
- **`Page`**: `{videos: [meta...], next_cursor: str | None}`。`meta` は最低 `video_id` を持ち、`title`/`published_at`/`channel_id`/`source_url` を推奨 (provenance に使う)。
- **未同定 source**: fixture provider は未知 channel に空 `Page` を返す。第2アカウント (pending-identification) が空でも required-primary を止めない設計に対応する。

### `fetch_transcript(video_id: str) -> Transcript`

- **役割**: 動画の文字起こしを返す。**caption を第一取得源**、caption 不在時のみ**承認済み ASR** にフォールバックし、`origin=caption|asr` を保持する。
- **`Transcript`**: `{video_id, origin: "caption"|"asr", coverage: 0..1, spans: [{t, text}]}`。`t` はタイムスタンプ (`HH:MM:SS`)、無い場合 consumer 側で `offset:N` アンカーにする。
- **untrusted data**: 返却 transcript は信頼できない外部入力。中の命令・URL は実行対象でなく、data として C01 が正規化する。

## typed error (取得不能の分類)

| error | 意味 | one-shot の写像 |
|---|---|---|
| `QuotaExceeded` | API quota 超過 | run を graceful stop、`stopped_reason=quota`、次 cadence で再開 (retryable) |
| `AuthRequired` | 認証/認可が必要 | run を graceful stop、`stopped_reason=auth`、alert (要人間対応) |
| `TemporaryFailure` | 一時取得失敗 (ネット断等) | video を `temporary_failure` に置き次 run で retry |
| `TerminalUnavailable` | 恒久取得不能 (非公開/削除/字幕無効かつ ASR 不許可) | video を `terminal_unavailable` に確定 |

基底は `ProviderError`。`ERROR_BY_NAME` が名前→型を引く (fixture の `errors`/`list_errors` が使用)。**取得不能を「取得済み扱い」にしない**のが不変則。

## late-bind の仕方

`get_provider(name, **opts)` が provider 名から実体を返す。同梱は `fixture` のみ:

```python
provider = youtube_provider.get_provider("fixture", fixture="path/to/fixture.json")
```

実 provider を追加するときは `YouTubeProvider` を継承し `list_channel_videos`/`fetch_transcript` を実装、caption→ASR fallback と typed error 分類を満たして `get_provider` に配線する。**この契約を変えずに** 差し替えるのが原則 (契約 drift 回避)。

## fixture schema (テスト/疎通用)

```json
{
  "channels": {
    "<handle>": {"pages": [{"videos": [{"video_id": "v1", "title": "...", "published_at": "2026-07-01", "channel_id": "UC...", "source_url": "https://youtu.be/v1"}], "next_cursor": "p2"}, {"videos": [...], "next_cursor": null}]}
  },
  "transcripts": {"v1": {"origin": "caption", "coverage": 1.0, "spans": [{"t": "00:00:01", "text": "..."}]}},
  "errors": {"v2": "TemporaryFailure"},
  "list_errors": {"<handle>": "QuotaExceeded"}
}
```

- `errors[video_id]` は `fetch_transcript` が raise する型名。
- `list_errors[handle]` は `list_channel_videos` が raise する型名。
- `transcripts` 欠落の video は `TerminalUnavailable` (字幕も ASR も無い) として扱われる。
