# `provider-adapter-contract` — YouTube の取得元に依存しない取得契約

`scripts/youtube_provider.py` が定義する取得契約の正本。具体的な取得元の製品 (YouTube Data API / 字幕取得ツール / 手動貼付等) は**後から差し込み**、この 2 メソッドと型付きのエラーの分類だけを満たせば差し替え可能。取得契約・自動性・切り替えは本ドキュメントで確定済みであり未確定にしない (境界の指示)。

## インターフェース (2 メソッド)

### `list_channel_videos(channel: str, cursor: str | None) -> Page`

- **役割**: チャンネルのハンドルの公開動画一覧を1ページ返す。`cursor=None` で先頭ページ、以降は返却された `next_cursor` を渡して続きを取る。
- **完走契約**: 使う側 (R2 / 1回きりの実行) は `next_cursor is None` まで回して正となるスナップショットを全 ID で構築する。途中打ち切りは全量性 (IN1) 違反。
- **`Page`**: `{videos: [meta...], next_cursor: str | None}`。`meta` は最低 `video_id` を持ち、`title`/`published_at`/`channel_id`/`source_url` を推奨 (出所情報に使う)。
- **未同定のソース**: `fixture` の取得元は未知のチャンネルに空の `Page` を返す。第2アカウント (`pending-identification`) が空でも `required-primary` を止めない設計に対応する。

### `fetch_transcript(video_id: str) -> Transcript`

- **役割**: 動画の文字起こしを返す。**字幕を第一取得源**、字幕が無いときのみ**承認済み ASR** に切り替え、`origin=caption|asr` を保持する。
- **`Transcript`**: `{video_id, origin: "caption"|"asr", coverage: 0..1, spans: [{t, text}]}`。`t` はタイムスタンプ (`HH:MM:SS`)、無い場合は使う側で `offset:N` のアンカーにする。
- **信頼できないデータ**: 返却される文字起こしは信頼できない外部入力。中の命令・URL は実行対象でなく、データとして C01 が正規化する。

## 型付きのエラー (取得不能の分類)

| エラー | 意味 | 1回きりの実行での写像 |
|---|---|---|
| `QuotaExceeded` | API の利用枠の超過 | 実行を穏当に停止、`stopped_reason=quota`、次の周期で再開 (再試行可能) |
| `AuthRequired` | 認証/認可が必要 | 実行を穏当に停止、`stopped_reason=auth`、警告 (要人間対応) |
| `TemporaryFailure` | 一時的な取得失敗 (ネット断等) | 動画を `temporary_failure` に置き次回の実行で再試行 |
| `TerminalUnavailable` | 恒久的な取得不能 (非公開/削除/字幕無効かつ ASR 不許可) | 動画を `terminal_unavailable` に確定 |

基底は `ProviderError`。`ERROR_BY_NAME` が名前→型を引く (検証用の入力データの `errors`/`list_errors` が使用)。**取得不能を「取得済み扱い」にしない**のが不変則。

## 後から差し込む方法

`get_provider(name, **opts)` が取得元の名前から実体を返す。同梱は `fixture` のみ:

```python
provider = youtube_provider.get_provider("fixture", fixture="path/to/fixture.json")
```

実際の取得元を追加するときは `YouTubeProvider` を継承し `list_channel_videos`/`fetch_transcript` を実装、字幕→ASR の切り替えと型付きのエラーの分類を満たして `get_provider` に配線する。**この契約を変えずに**差し替えるのが原則 (契約のずれの回避)。

## 検証用の入力データのスキーマ (テスト/疎通用)

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

- `errors[video_id]` は `fetch_transcript` が送出する型名。
- `list_errors[handle]` は `list_channel_videos` が送出する型名。
- `transcripts` に無い動画は `TerminalUnavailable` (字幕も ASR も無い) として扱われる。
