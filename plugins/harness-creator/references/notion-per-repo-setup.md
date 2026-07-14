# Per-Repository Notion Setup

harness-creator / skill-intake プラグインは複数 repository に symlink で共有される。
各 repo が **自分の Notion workspace / DB / API key** に書き込めるよう、
**repo-root の `.notion-config.json`** に identity を集約する。

スキーマ構造（properties 定義）は plugin 側 SSOT に閉じ、
DB ID / API key 解決のみ per-repo に分離する **shape vs identity** の分離原則。

---

## 1. セットアップ手順 (推奨: 1 コマンド)

新しい repository に harness-creator / skill-intake を symlink した後、以下を実施。

### 1.1 設定ファイル生成 (init script)

```bash
python3 scripts/build-notion-config.py
```

これにより `.notion-config.json` が **repo-slug namespacing 付き** で生成される
(`keychain_service: notion-api-key.<slug>` / `keychain_account: <slug>`)。
slug は `git remote get-url origin` の basename から自動推定 (`--slug foo` で上書き可)。

> **なぜ repo-slug 必須か**: Keychain の `(service, account)` は macOS グローバル名前空間。
> 複数 repo が同一 `notion-api-key` を使うと、symlink 共有された skill が
> **意図しない repo のトークン** を引いてしまう。slug 名前空間化で物理的に防ぐ。

完成後 `.notion-config.json` を編集し、3 つの Notion DB ID を埋める
(`<your-*-db-id>` を実 ID に置換)。ファイルは `.gitignore` 対象なので commit されない。

### 1.2 API トークン登録 (macOS Keychain)

init script の Next steps 出力に表示されるコマンドをそのまま実行 (slug が反映済み):

```bash
security add-generic-password \
  -s notion-api-key.<slug> -a <slug> \
  -w "secret_xxxxxxxxxxxx" -U
```

CI など Keychain が無い環境では env `NOTION_TOKEN` を fallback として利用可能。

### 1.1' (代替: 手動セットアップ)

init script を使わない場合は以下:

```bash
cp .notion-config.example.json .notion-config.json
# <REPLACE_WITH_REPO_SLUG> を実 slug に手で置換
# <your-*-db-id> を実 DB ID に手で置換
```

### 1.3 Notion DB 用意

`doc/notion-schema/*.schema.json` の properties 定義に従って、
Notion 側に 3 つの DB を作成する。

```bash
python3 scripts/sync-notion-schema.py --apply
```

このコマンドが各 DB の properties を schema と一致させる（idempotent）。

### 1.4 動作確認

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/harness-creator}/scripts/notion_config.py"
```

`.notion-config.json` の内容と loaded path が表示されれば OK。

---

## 2. 解決順序

DB ID (`notion_config.get_db_id(key)` SSOT):

1. `--database-id` CLI フラグ（個別スクリプト）
2. env (key-specific): `INTAKE_NOTION_DATABASE_ID` / `NOTION_DB_SKILL_LIST` / `NOTION_DB_IMPROVEMENT_REQUEST`
3. `<repo-root>/.notion-config.json` の `databases.<key>.db_id` (env `NOTION_CONFIG_PATH` で任意パス可)
4. schema 内 `database_id_default`（廃止予定、null）

token (`notion_config.get_token()` SSOT, `notion_http._resolve_token()` 経由):

1. env `NOTION_TOKEN`
2. Keychain (`.notion-config.json` の `keychain_service` / `keychain_account` を尊重)
3. legacy fallback: `keychain_get_secret.get_secret()` (env `INTAKE_KEYCHAIN_SERVICE/ACCOUNT` 経由)

> repo-root 探索は `.git` AND harness marker (`.notion-config.json` / `.notion-config.example.json` / `marketplace.json`) を要求する。
> submodule や別 repo の `.git` を上向きに辿って **誤って他 repo の config を盗み読む** ことを防止。

---

## 3. 設定が無い場合の挙動

config 未設定 repo で Notion 系スクリプトを実行すると、
**`[notion_config] WARN: ... not found ...` を stderr に出して exit 0** で終わる。

これにより、Notion 連携を使わない repo でも harness-creator/skill-intake を symlink して
他機能だけ利用できる。明示的に失敗させたい場合は config に偽値を入れず、
スクリプトに `--require-notion` を渡す（必要に応じて将来追加）。

---

## 4. ファイル所在

| 役割 | 場所 | tracked |
|---|---|---|
| Config 実体 | `<repo-root>/.notion-config.json` | NO (gitignore) |
| Config 雛形 | `<repo-root>/.notion-config.example.json` | YES |
| Loader SSOT | `plugins/harness-creator/scripts/notion_config.py` | YES |
| Loader symlink | `plugins/skill-intake/scripts/notion_config.py` → 上記 | YES (symlink) |
| Schema 正本 | `doc/notion-schema/*.schema.json` (db_id を含まない) | YES |
| Setup 手順 | このファイル | YES |

---

## 5. 既存リポジトリの移行

旧仕様（schema 内 `db_id` 直書き）からの移行:

```bash
# 1. 現状の db_id を抽出
grep '"db_id"' doc/notion-schema/*.schema.json

# 2. .notion-config.json を作成（上記 1.1 参照）

# 3. schema から db_id 行を削除（手動 or sed）

# 4. 動作確認
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/harness-creator}/scripts/notion_config.py"
python3 scripts/sync-notion-schema.py --check
```
