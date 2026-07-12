# Sink Contract v1.0

全adapterが実装すべき統一インタフェース。

## CLI Contract

```
sink_<name>.py --payload <payload.json> --params <params.json> [--dry-run]
```

stdin で payload を受けることも許可:
```
cat payload.json | sink_<name>.py --params <params.json>
```

現実装では `--payload` と `--params` のファイル引数を正規経路とする。stdin payload は将来互換の許容形であり、未対応adapterでは実装しなくてよい。

## Payload Schema (input)

```json
{
  "schema_version": "1.0",
  "kind": "string",
  "title": "string",
  "body": "string (markdown)",
  "metadata": {
    "tags": ["string"],
    "timestamp": "ISO8601",
    "source_skill": "string"
  },
  "attachments": [
    {"name": "string", "path": "string", "mime": "string"}
  ]
}
```

## Result Schema (stdout output)

```json
{
  "status": "success | failure",
  "adapter": "string",
  "location": "string (URL or absolute path)",
  "external_id": "string (opaque)",
  "errors": ["string"]
}
```

## Exit codes

- `0`: success
- `1`: validation error (payload不正)
- `2`: secret取得失敗 (Keychainに鍵がない)
- `3`: 外部API失敗
- `4`: fallback成功 (本来の出力先は失敗、fallbackに退避)

## 必須挙動

1. **stdout純度**: 最終JSON以外をstdoutに出さない。debug/progressはstderrへ
2. **secret非漏洩**: error messageに secret を含めない (sanitize必須)
3. **idempotency**: 同じ payload + params の再実行で副作用が増えないことを目標とし、未対応adapterは `on_conflict` の実装範囲を明記する
4. **fallback対応**: `dispatch.py` が routing の `fallback` を解釈して退避する。adapter内fallbackは必須ではない
5. **dry-run対応**: `--dry-run` 時はAPI呼出しせず、resolveされたparamsを返す

## Current implementation notes

- `dispatch.py` は `--kind <task_kind> --payload <payload.json> [--dry-run]` を受け取り、`resolve_route.py` と `sink_<name>.py` を順に呼ぶ。
- 個別adapterは `--payload <payload.json> --params <params.json> [--dry-run]` を受ける。
- fallback exit code `4` は契約上の予約値である。現実装の `dispatch.py` は primary/fallback の結果配列をJSONで返すため、呼び出し側は `results[*]` を確認する。
- Notion/Sheets/Slack/HTTP は外部APIの仕様差があるため、idempotency は adapter ごとに実装範囲を明記する。

## on_conflict ポリシー

| 値 | 挙動 |
|---|------|
| `error` | 既存があればfailure返却 |
| `update` | 既存をupdate (external_idで一意性判定) |
| `append` | 別エントリとして追記 |
| `skip` | 既存があればno-op (success返却) |

## Adapter固有のparams

`adapter-registry.json` の `params_schema` で宣言。各adapter実装は params 検証を行う。
