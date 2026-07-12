# 31 — Output Routing & Adapter Architecture（出力先routing/adapter基盤）

最終更新: 2026-05-18

## 1. 目的

成果物の **出力先** (Notion / Google Sheets / 任意HTTP API / Local file / Slack / Linear / S3 等) と **タスクロジック** (何を作るか) を直交分離し、新出力先の追加を **adapter追加のみで完結** させる (Open/Closed 原則)。本章は Hexagonal Architecture (Ports & Adapters) の Claude Code Skill 環境での実装方針を定義する。

## 2. 問題提起

出力先ごとに Skill を分割すると **M × N 爆発** を起こす:

```
タスク種別 M = {task-spec, meeting-minutes, design-doc, audit-log, alert, ...}
出力先 N = {notion-DB-A, notion-DB-B, sheets, local, slack, http, ...}
```

`out-notion-task-spec`, `out-notion-meeting`, `out-sheets-meeting` … と作るとSkill数が M×N で爆発し、出力先変更時に全Skillの修正が必要になる。

**正しい分離**: タスクロジック (port) と出力アダプタ (adapter) は別関心。port は1つ、adapter は出力先ごとに1つ。

## 3. アーキテクチャ

```
┌───────────────────────────────────────────┐
│  workflow skills (run-*)                   │  ← タスクロジックのみ
│  例: run-task-spec, run-meeting-minutes   │     (何を作るか)
└───────────────────────────────────────────┘
              │ 完成payload + task_kind
              ▼
┌───────────────────────────────────────────┐
│  ref-output-routing (port skill)           │  ← output-routing.json を引いて出力先解決
└───────────────────────────────────────────┘
              │ {adapter, params, fallback, multi}
              ▼
┌───────────────────────────────────────────┐
│  scripts/adapters/sink_*.py (adapters)     │  ← Sink Contract v1.0 実装
│  - sink_local   : Write tool / FS         │
│  - sink_http    : 任意HTTP API             │
│  - sink_notion  : Notion API              │
│  - sink_sheets  : Google Sheets v4 API    │
│  - sink_slack   : Slack webhook           │
│  - sink_<NEW>   : 新規追加はここのみ       │
└───────────────────────────────────────────┘
              │ secret取得 (subprocess内)
              ▼
┌───────────────────────────────────────────┐
│  macOS Keychain (security CLI)             │  ← APIキー唯一の信頼境界
└───────────────────────────────────────────┘
```

## 4. Sink Contract v1.0

全adapterが満たす統一インタフェース。

### CLI契約

```
sink_<name>.py --payload <payload.json> --params <params.json> [--dry-run]
```

### Payload Schema (入力)

```json
{
  "schema_version": "1.0",
  "kind": "<task_kind>",
  "title": "<string>",
  "body": "<markdown>",
  "metadata": {
    "tags": ["string"],
    "timestamp": "ISO8601",
    "source_skill": "<skill_name>"
  },
  "attachments": [{"name": "...", "path": "...", "mime": "..."}]
}
```

### Result Schema (stdout出力)

```json
{
  "status": "success | failure",
  "adapter": "<name>",
  "location": "<URL or absolute path>",
  "external_id": "<opaque ID>",
  "errors": ["<sanitized message>"]
}
```

### Exit codes

| Code | 意味 |
|---|---|
| 0 | success |
| 1 | validation error (payload不正) |
| 2 | secret取得失敗 |
| 3 | 外部API失敗 |
| 4 | fallback成功 (本来失敗→退避成功) |

### 必須挙動

1. **stdout純度**: 最終JSON以外をstdoutに出さない (debug/progressはstderr)
2. **secret非漏洩**: error message に secret を含めない (sanitize必須)
3. **idempotency**: 同一 payload+params の再実行で副作用が増えない (on_conflict制御)
4. **fallback対応**: 本処理失敗時に params.fallback で指定されたadapterへ自動退避
5. **dry-run対応**: API呼出しなしでresolve結果を返却

## 5. 設定ファイル

### 5.1 `.claude/config/output-routing.json.example`

`task_kind → adapter` マッピング雛形。プロジェクト固有値を入れた実設定は `.claude/config/output-routing.json` とする。**secret本体は絶対書かない**。`keychain:service/account` 形式の参照のみ。

```json
{
  "schema_version": "1.0",
  "defaults": {
    "adapter": "local",
    "fallback": "local"
  },
  "routes": {
    "task-spec": {
      "adapter": "notion",
      "params": {
        "database_id": "<DB_ID>",
        "on_conflict": "update",
        "token_ref": "keychain:xl-skills-notion/api-token"
      },
      "fallback": "local"
    },
    "design-doc": {
      "adapters": ["notion", "local"],
      "params": {
        "notion": { "database_id": "<DB>", "token_ref": "keychain:xl-skills-notion/api-token" },
        "local": { "path": "doc/", "format": "markdown" }
      }
    }
  }
}
```

### 5.2 `.claude/config/adapter-registry.json`

利用可能adapter宣言。新adapter追加時はここに1ブロック追加するだけで output-routing JSON から使える。

```json
{
  "adapters": [
    {
      "name": "notion",
      "script": "scripts/adapters/sink_notion.py",
      "requires_secret": true,
      "params_schema": {
        "database_id": { "type": "string", "required": true },
        "token_ref": { "type": "string", "required": true },
        "on_conflict": { "type": "string", "enum": ["error", "update", "append", "skip"] }
      }
    }
  ]
}
```

## 6. APIキー管理 (Keychain中心)

### 6.1 原則

1. APIキーは **Claude (LLM) context に絶対に乗せない**
2. **リポジトリ配下の任意のファイルに平文保存しない** (`.env` も禁止)
3. **macOS Keychain を唯一の信頼境界とする**
4. adapter script が subprocess 内で取得し、HTTP呼出しに直接使う

### 6.2 データフロー

```
[Keychain] ──security CLI──→ [adapter subprocess env]
                                      │
                                      ├─→ HTTP API (Authorization header)
                                      │
                                      └─→ stdout (statusのみ、keyは含まず)
                                              │
                                              ▼
                                          [Claude]
```

Claude は adapter の **stdout (JSON status)** しか見ない。key は subprocess の境界を越えない。

### 6.3 登録手順

```bash
security add-generic-password \
  -s xl-skills-<service> \
  -a <account> \
  -w "<SECRET>"
```

### 6.4 やってはいけない経路

| ❌ NG | 理由 |
|---|---|
| Claude が `security ... -w` を Bash直実行 | stdout に key が出てcontextに乗る |
| `.env` / config JSON に key 平文 | リポジトリ/履歴/バックアップに残る |
| HTTP error response を sanitize せず stdout 出力 | error body に key が混入する可能性 |
| `echo "Bearer $KEY"` 等のdebug | shell history に残る |

### 6.5 監査

`scripts/secrets/audit_secret_leak.py` を pre-commit / CI で実行し、平文secret混入を検知する。

## 7. 命名規約との連動

5prefix × 4軸 (`06`) に従う:

| 要素 | 命名 | prefix | 軸 |
|---|---|---|---|
| port skill | `ref-output-routing` | ref | 辞書型 |
| adapter scripts | `scripts/adapters/sink_<name>.py` | scripts配下 | ワークフロー外の実装 |
| config files | `.claude/config/output-routing.json` / `.json.example` | config配下 | 設定 |

adapter は Skill ではない (workflow ではないため)。`scripts/adapters/` 配下のヘルパー扱い。新adapter追加で Skill ツリーは膨らまない。

## 8. 他章との関係

| 章 | 関係 |
|---|---|
| **04** invocation-permissions | `dispatch.py` / adapter 実行だけを allow し、`security find-generic-password -w` の直接実行は deny する |
| **05** layering | adapter は scripts/ 層 (最内側)、ref-output-routing は ref/ 層、workflow skills は run/ 層。一方向依存維持 |
| **22** cross-platform | macOS Keychain は本章前提。Windows対応は `credential manager` + `cmdkey` への adapter差し替えで対応 (TODO) |
| **28** script-execution-model | adapter scripts はネットワーク/secret例外分類。Sink Contract と stdout/secret制約を満たす場合だけ許可 |
| **29** rubric-composition | adapter-registry.json は L1 (プロジェクト共通) 層に置き、複数プロジェクトで再利用可能 |
| **30** paradigm-analogy | Hexagonal Architecture / Ports & Adapters に対応 (Cockburn 2005) |

## 9. cross-platform制約

| OS | secret store | 状態 |
|---|---|---|
| macOS | Keychain (`security` CLI) | 本章でサポート (デフォルト) |
| Windows | Credential Manager (`cmdkey` / `Get-Credential`) | 未対応 (TODO: keychain_helper.py に分岐追加) |
| Linux | libsecret / Secret Service (`secret-tool`) | 未対応 (TODO) |

将来対応時は `keychain_helper.py` の `get_secret()` が OS判定で `security` / `cmdkey` / `secret-tool` のいずれかを subprocess 起動する。Sink Contract は不変。

## 10. 拡張シナリオ

| ユースケース | 対応 |
|---|---|
| Notion DB-A → DB-B 移行 | output-routing.json の database_id 変更のみ |
| 新規Slack通知追加 | output-routing.json に新route追加 |
| 監査ログをS3に送る | `sink_s3.py` 追加 + registry登録 + route追加 |
| 同じ成果物をNotion+ローカル両方へ | `adapters: [notion, local]` で multi-sink |
| Notion API仕様変更 | sink_notion.py 1ファイルのみ修正 (workflow Skill 修正ゼロ) |
| 新出力先 (Linear等) 追加 | sink_linear.py + registry 1ブロック + Keychain登録 |

## 11. 注意点 (Gotchas)

1. **`token_ref` の参照記法統一**: `keychain:<service>/<account>` 以外は受け付けない。`env:` / `file:` 等の追加は新規スキーマでOpen-ended にしすぎない
2. **dispatch.py のtimeout**: 各adapter 60秒。長時間API呼出しは非同期化 (将来課題)
3. **multi-sink の失敗ポリシー**: 1adapter失敗時に他adapterを続行するか中断するかを output-routing.json で `on_partial_failure` 指定 (デフォルト: 続行)
4. **stdout汚染防止**: adapter内 `print()` は最終JSON1回のみ。Pythonの `logging` は stderr handler 限定
5. **rate limit**: HTTP系adapterに最小限のretry/backoff を入れる (将来課題)
6. **MCP併用**: Claude Code環境ではNotion/Drive MCPが利用可能。シンプルなケースはMCPを直接呼ぶ方が軽い。routingで一元管理したい場合のみ本章のadapterを使う

## 12. 実装一覧

| ファイル | 役割 |
|---|---|
| `.claude/skills/ref-output-routing/SKILL.md` | port skill本体 |
| `.claude/skills/ref-output-routing/references/sink-contract.md` | Sink Contract v1.0仕様 |
| `.claude/skills/ref-output-routing/references/security-model.md` | Keychain設計詳細 |
| `creator-kit/config/output-routing.json.example` | routing雛形 |
| `creator-kit/config/adapter-registry.json` | adapter登録正本 |
| `scripts/adapters/resolve_route.py` | routing解決 |
| `scripts/adapters/dispatch.py` | 統合dispatcher |
| `scripts/adapters/sink_local.py` | ローカル保存 |
| `scripts/adapters/sink_http.py` | 任意HTTP |
| `scripts/adapters/sink_notion.py` | Notion |
| `scripts/adapters/sink_sheets.py` | Google Sheets |
| `scripts/adapters/sink_slack.py` | Slack webhook |
| `scripts/secrets/keychain_helper.py` | Keychain読取りライブラリ (直接実行禁止) |
| `scripts/secrets/audit_secret_leak.py` | 平文secret混入検知 |
| `scripts/secrets/README.md` | 登録手順 |

## 13. ロードマップ (TODO)

- [ ] Windows / Linux secret store サポート (keychain_helper分岐)
- [ ] adapter rate-limit / retry / backoff の共通化
- [ ] multi-sink の `on_partial_failure` policy 実装
- [ ] adapter単体テスト (mock HTTP / mock Keychain)
- [ ] OpenAPI generator (HTTP adapter の params から自動派生)
