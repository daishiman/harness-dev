# External intelligence normal-runtime contract

`external-intelligence-runtime-v1` は、Claude Code と Codex が通常の artifact 生成時に共用する provider-neutral sidecar 契約である。request / state / output の正本は `run-build-skill/schemas/external-intelligence-runtime.schema.json`、実行 adapter は `run-build-skill/scripts/build-external-intelligence-runtime.py`、永続化 engine は `run-build-skill/scripts/build-external-intelligence.py` だけとする。

## 実行フロー

1. `search` は project scope の薄い index だけを検索する。候補は score threshold 1.0 以上、最大5件、summary 512 bytes/件、候補JSON 4,096 bytes以下である。
2. `adopt` は直前stateの `candidate_ids` にある明示選択IDだけを `show` する。detailは4,096 bytes/件、16,384 bytes/応答以下とし、実際に選択・取得できたentryだけ `reuse` を記録する。
3. `finish` は再利用可能な新規構造を0または1件だけ `capture` する。exact/高類似は既存entryへmergeし、曖昧類似は `pending_duplicate` にquarantineする。1実行で複数captureは契約不正とする。

Claude Code / Codex は同じrequest/state/output shapeを使い、相違は `runtime` フィールとengine eventのagent監査情報だけである。provider別の別index・別entry・別scoreを作らない。

## Fail-soft 境界

memoryは artifact generatorの必須依存ではない。中央engineが未install、stateが未生成・破損、または5秒でtimeoutした場合、adapterは `status=continue` / exit 0 と `memory_absent|memory_unavailable|memory_corrupt|memory_timeout` warningを返す。artifact生成は継続し、知見を見つけた、再利用した、または保存したと推定しない。request contract自体の不正だけは `invalid_request` / exit 2 である。

token telemetry が実測で得られない時は、outputを `status=unavailable`, `estimated=false`, token数 `null` に固定する。ファイル文字数やsearch結果から token・cache率・quota消費を推定しない。

## Scope / install 境界

- adapterは `--scope project` だけを中央engineへ渡す。`HARNESS_INTELLIGENCE_HOME`, plugin data, XDG/OS user stateをsubprocess環境から除去し、user scopeを自動混入しない。
- Git projectはGit common dir、非Git projectは `<project>/.harness/external-intelligence/v1` に保存する。installed plugin package自体がproject rootの場合は書き込まずwarning continuationとする。
- 中央編集正本は配布可能な `skill-governance-adapters` の engine / adapter / schema / contract / caller 各1件だけとする。Harness Creator 自体は `NEVER_DISTRIBUTE` を維持し、後方互換用の薄い engine / adapter 転送ファイルと contract pointer だけを持つ。projection SHA pin はこの配布正本をfail-closedに束縛する。skillごと・pluginごとの長いengine複製は作らない。
- `skills-full` と `skills-intake` はどちらも `skill-governance-adapters` を含み、同pluginの `UserPromptSubmit` callerが通常runtimeの入口になる。さらに全consumer pluginが公式 `plugin.json.dependencies` で同providerを宣言するため、個別installも同一marketplaceからproviderを自動導入・有効化する。memoryが実行時に破損/タイムアウトした場合だけ `warning-continue` とし、user memory fallbackは作らない。

## Projection pointer

全plugin projectionの `external_intelligence_runtime` は次のexact keysを持つ。

```json
{
  "contract_id": "external-intelligence-runtime-v1",
  "adapter_ref": "plugin:skill-governance-adapters/scripts/build-external-intelligence-runtime.py",
  "adapter_sha256": "<raw adapter bytes SHA-256>",
  "engine_ref": "plugin:skill-governance-adapters/scripts/build-external-intelligence.py",
  "engine_sha256": "<raw engine bytes SHA-256>",
  "schema_ref": "plugin:skill-governance-adapters/schemas/external-intelligence-runtime.schema.json",
  "contract_ref": "plugin:skill-governance-adapters/references/external-intelligence-runtime-contract.md",
  "policy_sha256": "<raw schema bytes SHA-256>",
  "caller_ref": "plugin:skill-governance-adapters/hooks/build-external-intelligence-context.py",
  "caller_sha256": "<raw caller bytes SHA-256>",
  "caller_manifest_ref": "plugin:skill-governance-adapters/.claude-plugin/plugin.json",
  "caller_event": "UserPromptSubmit",
  "default_scope": "project",
  "standalone_behavior": "warning-continue"
}
```

`policy_sha256` / `engine_sha256` / `adapter_sha256` / `caller_sha256` は各配布実体のraw bytesに対するSHA-256である。callerは `caller_manifest_ref` の `caller_event` へ登録され、`adapter_ref` を実行しなければならない。pointerだけが存在し実行者がいない状態はlintで拒否する。
