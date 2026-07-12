# Per-Repository Notion Setup

harness-creator / skill-intake プラグインは 2 通りで利用される:
**(A) 単独 install** (`plugins/skill-intake/` のみ導入) と
**(B) monorepo / 複数 repo 共有** (vendoring 実体を各環境に同梱)。
ヒアリングシートの出力先 DB は固定値として `notion-config.fixed.json` に同梱する。
別DBへ向ける環境だけ `.notion-config.json` に identity を集約する (単独 install は
plugin-root 直下、repo 共有は repo-root 直下、または env `NOTION_CONFIG_PATH` で任意パス)。

スキーマ構造（properties 定義）は plugin 側 SSOT に閉じ、
DB ID / API key 解決のみ per-environment に分離する **shape vs identity** の分離原則。

---

## 1. セットアップ手順

> **単独 install (A) の方はこちら**: 同梱の固定DB既定値は**保守者チーム専用**
> (外部ワークスペースの Integration からは書き込めない = 403)。
> 外部ワークスペースへ出力する場合は §1.1 → §1.2 → §1.4 を実施。
> 保守者チーム (社内 express 経路) のみ §1.2 → §1.4 で足りる。
> `scripts/build-notion-config.py` / `sync-notion-schema.py` は **repo 保守者専用**で
> 単独 install には同梱されないため使いません。

### 1.1 設定ファイル生成 (自分のワークスペースの DB へ出力する場合は必須)

同梱の固定DB既定値 (`notion-config.fixed.json`) は保守者チーム専用で、外部ワークスペースの
Integration からは書き込めない (403)。外部利用では本節の `.notion-config.json` 作成が必須。

```bash
# plugin-root (または repo-root) 直下に作成。保守者チーム (社内 express 経路) のみ不要。
cp .notion-config.example.json .notion-config.json
# <your-parent-page-id> / <your-parent-page-url> を DB を置く親ページに置換
# <your-*-db-id> を実 DB ID に置換
# (repo 共有運用の repo-root 雛形では <REPLACE_WITH_REPO_SLUG> も任意の識別子に置換)
```

`skill-intake` 単独 install では、固定設定は plugin-root の
`plugins/skill-intake/notion-config.fixed.json` に同梱される。雛形は
`plugins/skill-intake/.notion-config.example.json` にあり、自分のワークスペースへ
出力する場合に使う (必要キーのみの最小構成)。
カレントディレクトリが plugin-root でない場合は次のように明示する。

```bash
cp plugins/skill-intake/.notion-config.example.json plugins/skill-intake/.notion-config.json
```

env で渡す場合は `.notion-config.json` を作らず
`export NOTION_CONFIG_PATH=/path/to/config.json` でも可。`.notion-config.json` は
`.gitignore` 対象なので commit されない。

> **(B) repo 共有運用の保守者向け (1 コマンド)**: monorepo 内なら
> `python3 scripts/build-notion-config.py` で **repo-slug namespacing 付き** config を
> 自動生成できる (`keychain_service: notion-api-key.<slug>` / slug は `git remote` から推定、
> `--slug foo` で上書き)。**なぜ slug 必須か**: Keychain の `(service, account)` は macOS
> グローバル名前空間で、複数 repo が同一 service 名を使うと共有 skill が**意図しない
> repo のトークン**を引くため、slug 名前空間化で物理的に防ぐ。本スクリプトは単独 install **未同梱**。

### 1.2 API トークン登録 (macOS Keychain)

```bash
read -rs NOTION_TOKEN_INPUT
security add-generic-password \
  -s notion-api-key.<keychain-prefix> -a <keychain-prefix> \
  -w "$NOTION_TOKEN_INPUT" -U
unset NOTION_TOKEN_INPUT
```

(repo 共有運用では service/account を `notion-api-key.<slug>` / `<slug>` に置換。)
CI / dry-run など Keychain が無い環境でのみ、`INTAKE_ALLOW_ENV_TOKEN=1` を明示した上で
env `NOTION_TOKEN` を fallback として利用可能。通常運用では `NOTION_TOKEN` は読まない。

### 1.3 Notion DB 用意

`doc/notion-schema/*.schema.json`（repo 共有運用時）の properties 定義に従って、
Notion 側に 3 つの DB を作成する。単独 install のヒアリングシートは
`notion-config.fixed.json#databases.hearing-sheet.db_id` を既定値として使う。
別DBへ向ける場合は既存 DB の ID を §1.1 の config に記入すれば足りる。

DB を新規作成する場合は、`.notion-config.json#parent_page`（または
env `INTAKE_NOTION_PARENT_PAGE_ID`）で指定した親ページ配下に作成する。これにより
各 DB がユーザー指定の Notion ページへ集約され、別ページへの誤作成を防ぐ。
同梱 `notion-config.fixed.json` の `parent_page` は**意図的に空**であり、DB 新規作成には
`.notion-config.json#parent_page.page_id` へ**ご自身の Notion ページ ID の指定が必須**。
未指定、または `databases.*.db_id` と同一の ID（親が DB を指す誤設定）の場合、
`create_notion_database.py --mode=create` は exit 2 で fail-closed する。

> repo 保守者は monorepo 内で `python3 scripts/sync-notion-schema.py --apply`
> により各 DB の properties を schema と idempotent に一致させられる（単独 install 未同梱）。

### 1.4 動作確認

```bash
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/notion_config.py
```

`.notion-config.json` の内容と loaded path が表示されれば OK。

---

## 2. 解決順序

Config ファイル (`notion_config.find_config_path()` SSOT — **ファイル単位の先勝ち**):

1. env `NOTION_CONFIG_PATH` が指すファイル（不在なら fail-closed。別 config へフォールバックしない）
2. repo-root 直下の `.notion-config.json`
3. plugin-root 直下の `.notion-config.json`
4. plugin-root の `notion-config.fixed.json`

> **重要**: 上書き config ファイル (1〜3) が見つかった場合、そのファイル**のみ**が有効になり、
> `notion-config.fixed.json` への**キー単位フォールバックは行われない**。上書き config には
> 必要キー（`databases.hearing-sheet.db_id` 等）を**すべて**記載すること。

DB ID (`notion_config.get_db_id(key)` SSOT):

1. `--database-id` CLI フラグ（個別スクリプト）
2. env (key-specific): `INTAKE_NOTION_DATABASE_ID` / `NOTION_DB_SKILL_LIST` / `NOTION_DB_IMPROVEMENT_REQUEST`
3. 上記で解決された**単一の** config ファイルの `databases.<key>.db_id`
4. 未設定なら exit 2（schema 内 `database_id_default` へはフォールバックしない）

Parent Page ID (`notion_config.get_parent_page_id()` SSOT):

1. env `INTAKE_NOTION_PARENT_PAGE_ID`
2. 上記で解決された**単一の** config ファイル内で `parent_page.page_id` →
   `parent_page.page_url` → `parent_page_id`（旧互換）の順（同一ファイル内のキー間フォールバックのみ）
3. 未設定なら DB 作成系は exit 2（任意の別ページへフォールバックしない）。同梱
   `notion-config.fixed.json` の `parent_page` は空のため、DB 新規作成には `.notion-config.json`
   等での親ページ指定が必須。`databases.*.db_id` と同一の ID も親ページとして拒否される（§1.3）。

`app.notion.com` の URL は、query `p` / `page_id` があれば path より優先して page ID として解釈する。

token (`notion_config.get_token()` SSOT, `notion_http._resolve_token()` 経由):

1. Keychain (`.notion-config.json` の `keychain_service` / `keychain_account` を尊重)
2. legacy fallback: `keychain_get_secret.get_secret()` (env `INTAKE_KEYCHAIN_SERVICE/ACCOUNT` 経由)
3. CI / dry-run 限定: `INTAKE_ALLOW_ENV_TOKEN=1` のときだけ env `NOTION_TOKEN`

`NOTION_CONFIG_PATH` を明示した場合、そのファイルが存在しなければ fail-closed する。別 repo / plugin-root の config へ自動フォールバックしない。

> repo-root 探索は `.git` AND harness marker (`.notion-config.json` / `.notion-config.example.json` / `marketplace.json`) を要求する。
> submodule や別 repo の `.git` を上向きに辿って **誤って他 repo の config を盗み読む** ことを防止。
> marker を持つ repo-root が見つからない **単独 install** 環境では、`$CLAUDE_PLUGIN_ROOT`
> (無ければ plugin 実体位置) 直下の `.notion-config.json` にフォールバックする。

---

## 3. 設定が無い場合の挙動

publish / schema 検証など Notion に副作用を持つスクリプトは、DB ID / token が欠けると
exit 2 で停止する。silent skip はしない。Notion 連携を使わない環境では、Notion 系
コマンドを起動しない。

---

## 4. ファイル所在

`notion_config.py` は **symlink ではなく vendoring 実体** として各 plugin に同梱される
(byte 一致は repo 保守側の `scripts/lint-intake-vendored-ssot.py` が CI で強制。単独 install
では検証相手の正本が無いため lint は対象外＝maintainer-only)。

| 役割 | 場所 | tracked |
|---|---|---|
| 固定 Config 実体 | plugin-root 直下の `notion-config.fixed.json` | YES |
| 上書き Config 実体 | repo-root か plugin-root 直下の `.notion-config.json` | NO (gitignore) |
| Config 雛形 | `.notion-config.example.json` | YES |
| Loader (vendored 実体) | `plugins/skill-intake/scripts/notion_config.py` | YES |
| Schema 正本 | `doc/notion-schema/*.schema.json` (db_id を含まない) | YES |
| Setup 手順 | このファイル | YES |

> **配布スコープ**: 上表のうち単独 install 配布物に含まれ runtime で必要なのは
> Loader (vendored) と Config (各自用意) のみ。`scripts/lint-intake-vendored-ssot.py` /
> `sync-intake-vendored.sh` / `build-notion-config.py` / `sync-notion-schema.py` は
> **repo 保守者専用 (monorepo 内のみ動作)** で、単独 install には不要・未同梱。

---

## 5. 既存リポジトリの移行 (repo 保守者向け)

旧仕様（schema 内 `db_id` 直書き）からの移行:

```bash
# 1. 現状の db_id を抽出
grep '"db_id"' doc/notion-schema/*.schema.json

# 2. .notion-config.json を作成（上記 1.1 参照）

# 3. schema から db_id 行を削除（手動 or sed）

# 4. 動作確認
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/notion_config.py
python3 scripts/sync-notion-schema.py --check
```
