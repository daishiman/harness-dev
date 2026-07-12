---
name: ref-output-routing
description: 管理して成果物の出力先を切り替えたいとき、新しい出力先アダプタを追加したいときに使う。
disable-model-invocation: false
argument-hint: "<task_kind>"
arguments: [task_kind]
allowed-tools:
  - Read
  - Bash(python3 *)
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-18
version: 0.1.0
# context-budget: routing解決のみ。具体的なAPI実装はadapterスクリプトに完全委譲。
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs: [prompts/R1-search-summarize.md]
---

# ref-output-routing

## Purpose & Output Contract

**タスクロジックと出力先を直交分離する。** workflow skill は本スキルに `task_kind` を渡すだけで、出力先 (Notion DB / Sheets / Local / HTTP / Slack 等) を意識しない。新出力先の追加は adapter 追加のみで完結する (Open/Closed原則)。

**入力**: `task_kind` (例: task-spec, meeting-minutes, audit-log)
**出力**: 
```json
{
  "adapter": "notion|sheets|local|http|slack",
  "params": {...},
  "fallback": "local",
  "multi": false
}
```
**完了条件**: `output-routing.json` から該当route解決 → adapter名とparams返却 → workflow側が `dispatch.py` 経由でadapterを起動。

## Sink Contract (全adapter共通)

### 入力payload (workflow → adapter)
```json
{
  "schema_version": "1.0",
  "kind": "<task_kind>",
  "title": "<string>",
  "body": "<markdown>",
  "metadata": {
    "tags": [],
    "timestamp": "ISO8601",
    "source_skill": "<skill_name>"
  },
  "attachments": []
}
```

### 出力result (adapter → workflow)
```json
{
  "status": "success|failure",
  "adapter": "<name>",
  "location": "<URL or path>",
  "external_id": "<opaque ID>",
  "errors": []
}
```

## 設定ファイル (3点)

1. `.claude/config/output-routing.json` — task_kind → adapter マッピング正本
2. `.claude/config/adapter-registry.json` — 利用可能adapter宣言
3. macOS Keychain — APIキー等の秘匿情報 (リポジトリには絶対保存しない)

## Key Rules

1. **API key は絶対にClaude context に乗らない**: adapter scriptが subprocess 内で Keychain から取得し、HTTP呼出しに直接使う。Claude は key を見ない。
2. **output-routing.json にはIDのみ**: database_id, spreadsheet_id 等の非機密IDは記載可。トークン/secret は `keychain:{{SECRET_NAMESPACE}}/<account>` 形式で参照のみ記載。`env:` / `file:` は使わない。
3. **adapter追加はJSON登録のみ**: コード変更なしで `adapter-registry.json` に登録すれば `output-routing.json` で使える (Open/Closed)。
4. **multi-sink対応**: `adapters: [notion, local]` で複数同時出力可能。
5. **fallback必須**: 各routeに `fallback: local` 推奨。外部API障害時にローカル退避でwork継続。

## 使い方 (workflow側)

```bash
# Step 1: routing解決
python3 scripts/adapters/resolve_route.py --kind task-spec
# 出力: {"adapter":"notion","params":{"database_id":"..."},"fallback":"local"}

# Step 2: 解決されたadapter起動
python3 scripts/adapters/dispatch.py \
  --kind task-spec \
  --payload payload.json \
# 出力: {"status":"success","location":"{{OUTPUT_ROUTE}}","external_id":"..."}
```

## adapter 追加手順 (例: Linear連携)

1. `scripts/adapters/sink_linear.py` を作成 (Sink Contract準拠)
2. `.claude/config/adapter-registry.json` に追加:
   ```json
   {
     "name": "linear",
     "script": "scripts/adapters/sink_linear.py",
     "requires_secret": true,
     "params_schema": {
       "team_id": { "type": "string", "required": true },
       "token_ref": { "type": "string", "required": true }
     }
   }
   ```
3. `.claude/config/output-routing.json` の該当 task_kind に `"adapter": "linear"` を指定
4. Keychainに API key を登録: `security add-generic-password -s {{SECRET_PREFIX}}-linear -a api-key -w <KEY>`

**workflow Skill のコード変更はゼロ**。adapter script 追加、registry、routing のJSON更新のみで新出力先が量産可能。

## Gotchas

1. **API keyをroutingに直書きしない**: `params: { token: "sk-..." }` は禁止。必ず `params: { token_ref: "keychain:{{SECRET_NAMESPACE}}/<account>" }` で参照のみ。
2. **output-routing.jsonのコミット**: 非機密ID (database_id等) はコミット可だがレビュー必須。tokenが紛れていないか lint で検証。
3. **fallback先のpath**: ローカルフォールバックの保存先は `eval-log/` 等のrepo内に固定。外部書き出しは禁止。
4. **adapter内部のstdout汚染禁止**: adapter は最終JSON以外を stdout に出さない。debug は stderr へ。Claude が adapter出力を読むためstdoutにkey/secretが混入すると context漏洩。
5. **Sheets/HTTP のスキーマ互換**: 同じpayloadを異なるadapterで処理できるか lint で確認 (`schema_version` 不一致を検出)。

## Additional Resources

- `references/sink-contract.md` — Sink Contract詳細仕様
- `references/security-model.md` — APIキー管理モデル (Keychain中心)
- `.claude/config/output-routing.json.example` — routing雛形
- `.claude/config/adapter-registry.json` — adapter宣言正本
- `scripts/adapters/` — adapter実装群
- `scripts/secrets/README.md` — Keychain登録手順
