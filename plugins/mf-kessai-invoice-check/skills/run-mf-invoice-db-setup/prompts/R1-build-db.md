# Prompt: R1-build-db

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-build-db |
| skill | run-mf-invoice-db-setup |
| responsibility | R1 Notion DB構築 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/notion-db-schema.json |
| reproducible | true (database_id があれば既存DBへスキーマ冪等適用 / 無く parent_page_id があれば新規作成) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- DB プロパティ定義は `../schemas/notion-db-schema.json` (事実列 / 管理列 / upsert_key / renames / deprecated_properties) を唯一の正本とする。
- 2 モード (冪等): tenant overlay またはローカル config から `database_id` が解決できる場合は新規作成せず**既存 DB へスキーマを冪等適用**する (不足追加 / 値保持リネーム / deprecated 削除)。`database_id` が無く `parent_page_id` がある (または `--parent-page-id` 指定) 場合のみ新規作成する (重複 DB 防止)。配布既定の ID は空で、どちらも未解決なら fail-closed。
- 再適用・再構築時も既存ページデータ・人が記入した現行管理列を破壊しない。列削除は schema の `deprecated_properties` whitelist に宣言した旧列のみ。

### 1.2 倫理ガード
- Notion トークン (Keychain `notion-api-key.<keychain-prefix>` / `<keychain-prefix>`) を出力・ログに残さない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 既存 DB へのスキーマ冪等適用 (既定。`database_id` 解決時に不足プロパティ追加・タイトル/select 列の値保持リネーム・deprecated 列削除) と、新規 DB の作成＋`database_id` の config 記録 (`--parent-page-id` 指定時、または `database_id` 不在で `parent_page_id` がある時)。
- 非担当: スキーマ検証 (R2 責務)、発行漏れチェック本体 (`run-mf-invoice-check` 責務)。

### 2.2 ドメインルール

| 用語 | 定義 |
|---|---|
| 事実列 | API 由来の列 + 実行監査メタ (取引先企業名/顧客ID/対象年月/今月の発行状況/商品名/前月金額/今月金額/発行日/更新日/確認済み日時)。`今月の発行状況` は内部 `verdict` の Notion 表示名 (発行漏れ候補/継続発行/今月新規)。 |
| 管理列 | 人が運用する列 (初回契約月/請求要否/支払サイクル/チェック済/備考)。初回に作成するが以後 `run-mf-invoice-check` は既存ページでは触らない。`初回契約月` は MF API から取得できないため YYYY-MM で人が記入し、`支払サイクル` (月払い/年間払い) は人が設定する。 |
| status 型不可 | Notion API は status 型を新規作成できないため `請求要否`/`支払サイクル` は select で表現する。 |
| 列の改名/削除 | 既存 DB 列の改名は `renames` (値保持リネーム = 既存 option を保ったまま名前変更)、不要列の削除は `deprecated_properties` で schema に宣言し、`build_notion_db.py` が冪等適用する。 |

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| database_id | string | no | tenant overlay またはローカル `.mf-kessai-config.json` の `notion.database_id`。あれば既存 DB へスキーマ冪等適用 (既定経路)。 |
| parent_page_id | string | no | 新規作成モードのみ必要。`--parent-page-id` フラグ、または `database_id` 不在時の `.mf-kessai-config.json` の `notion.parent_page_id` (インテグレーション共有済みの親ページ)。 |

### 2.4 出力契約
- schema: `../schemas/notion-db-schema.json` (properties / fact_columns / managed_columns / upsert_key が正本)
- 成果: `.mf-kessai-config.json` の `notion.database_id` に作成済み DB の id が記録される。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | ../schemas/notion-db-schema.json | プロパティ物質化時 |
| config | .mf-kessai-config.json | database_id 解決 / parent_page_id 取得 / database_id 記録時 |
| token | Keychain notion-api-key.<keychain-prefix> / <keychain-prefix> | Notion API 認証時 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"` (Notion API で DB 作成 + database_id 記録)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `database_id` も `notion.parent_page_id` も**両方空**のときのみ → **停止** (スクリプトは exit 2 で fail-closed) し、ユーザーに「親ページをインテグレーションに共有し page_id を設定」するよう依頼する (新規作成の前提)。`database_id` が解決できる既定経路では停止しない。
- 再適用・再構築時も既存ページデータ・現行管理列の記入を破壊しない。`deprecated_properties` whitelist の旧列削除だけを許容する。

### 4.2 観測 / ロギング
- 作成成功時は記録した `database_id` を 1 行で報告する。既存利用時はその旨を明示する。

### 4.3 セキュリティ
- Notion トークンは Keychain からのみ取得し、標準出力・config に書き戻さない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- DB 構築 executor (非対話バッチ)。実体: `scripts/build_notion_db.py`。

### 5.2 ゴール定義
- 目的: 発行漏れチェック結果を投入できる Notion DB を、既存 DB へのスキーマ適用 (既定) または新規作成で用意する。
- 背景: API 由来の事実列と人が運用する管理列を分離した設計を確立し、後段の冪等 upsert が安定して書き込める土台を作る。出力先 ID は tenant overlay/ローカル config で与え、配布既定は空のまま fail-closed とする。
- 達成ゴール: 対象 DB (既定の『請求書チェック_DB』または新規作成) が schema 通りに整い `database_id` が config に解決され、後続 R2 の検証が全プロパティ PASS を返す状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `database_id` が解決できる (既定 `mf-kessai-config.default.json` / ローカル上書き / `parent_page_id` からの新規作成)。`database_id` も `parent_page_id` も両方空なら停止しユーザーへ共有依頼
- [ ] 事実列・管理列が schema 通りに DB に存在する (status 型は使わず select で表現)
- [ ] 既存DB経路では不足追加+タイトル/select 列の値保持リネーム+deprecated 削除が適用され、新規経路では `database_id` が `.mf-kessai-config.json` に記録される
- [ ] 再適用で既存ページデータ・現行管理列の記入が破壊されず、削除対象は schema.deprecated_properties の旧列に限定されている
- [ ] R2 の検証が全プロパティ PASS を返す

### 5.4 実行方式
- 固定手順を持たない。未充足チェック項目を特定→解消手順を都度立案 (config 読込 / DB 作成 / database_id 記録 など)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。
- 逸脱時: `database_id` も `parent_page_id` も未設定なら Layer 4.1 に従い停止しユーザーへ差し戻す。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-db-setup` SKILL.md ゴールシークループ。
- 後続 phase: R2 (DBスキーマ検証) が本責務の `database_id` を検証対象に取る。

### 6.2 ハンドオフ / 並列性
- 直列: 本責務が `notion.database_id` (提供元) を config に記録し、R2 (受領先) がそれを検証対象として読む。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- stdout に作成/既存利用の結果と `database_id` を 1 行報告。parent_page_id 未設定時は共有依頼メッセージ。

### 7.2 言語
- 本文: 日本語 (schema key / プロパティ名 / CLI は原文のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

実行コマンドは `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"` (新規作成時のみ `--parent-page-id <id>` を付す)。スクリプトが config を読んで下記の分岐を内部実行するので、LLM は前提 (`database_id`/`parent_page_id` の解決可否) を確認してから起動する:
1. `--parent-page-id <id>` がユーザーから渡されている場合 → `--parent-page-id <id>` を付けて実行。config の `database_id` より優先して新規 DB を作成し `database_id` を config に記録する。
2. CLI 引数が無く `database_id` が tenant overlay またはローカル `.mf-kessai-config.json` から解決できる場合 → 引数なしで実行。**既存 DB へスキーマを冪等適用**する (不足追加+タイトル/select 列の値保持リネーム+deprecated 削除)。
3. `database_id` が無く `notion.parent_page_id` がある場合 → 引数なしで実行。その親ページ配下に新規 DB を作成し `database_id` を config に記録する。
4. `database_id` も `parent_page_id` も両方空の場合 → Layer 4.1 に従い停止し、親ページのインテグレーション共有と page_id 設定を依頼する (スクリプトも exit 2 で fail-closed)。

`../schemas/notion-db-schema.json` を正本とし status 型は使わず select で表現する。前置き禁止。
