# Prompt: R2-verify-schema

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-verify-schema |
| skill | run-mf-invoice-db-setup |
| responsibility | R2 DBスキーマ検証 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/notion-db-schema.json |
| reproducible | true (read-only、同一 DB 状態に対し同一判定) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- read-only: DB を一切変更しない (プロパティの追加・改名・削除をしない)。
- 期待プロパティの正本は `../schemas/notion-db-schema.json` (properties / fact_columns / managed_columns / upsert_key)。

### 1.2 倫理ガード
- Notion トークン (Keychain `notion-api-key.<keychain-prefix>` / `<keychain-prefix>`) を出力・ログに残さない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 作成済み DB が設計通りのプロパティを持つか機械検証 (drift 検知)。
- 非担当: DB 作成・修正 (R1 責務)、欠落の自動補填 (DB を変更しないため非担当)。

### 2.2 ドメインルール

| 用語 | 定義 |
|---|---|
| 期待プロパティ | schema の properties に定義された事実列＋管理列。これが揃っていれば PASS。 |
| drift | schema と DB の差分。schema にあり DB に無い欠落、および `deprecated_properties` にある既知の旧サマリ/集計列の残存は FAIL。DB にのみある未知の追加列は警告。 |

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| database_id | string | yes | `.mf-kessai-config.json` の `notion.database_id`。R1 が記録した検証対象 DB。 |

### 2.4 出力契約
- schema: `../schemas/notion-db-schema.json` (期待プロパティ正本)
- 成果: 全期待プロパティ存在、かつ deprecated 旧サマリ/集計列の残存なしで PASS。drift があれば欠落・残存旧列・追加列を差分として明示。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | ../schemas/notion-db-schema.json | 期待プロパティ照合時 |
| config | .mf-kessai-config.json | database_id 取得時 |
| token | Keychain notion-api-key.<keychain-prefix> / <keychain-prefix> | Notion API 認証時 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py"` (Notion API で DB プロパティを取得し schema と照合)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 欠落プロパティあり → FAIL。欠落を提示し `build_notion_db.py` の再実行または手動追補をユーザーに案内する。
- `deprecated_properties` にある既知の旧サマリ/集計列 (例: `全体トータル`) が残存 → FAIL。`build_notion_db.py` の再実行で削除するよう案内する。
- DB にのみ存在する未知の追加列は警告に留め、失敗扱いにしない (ユーザーが手動追加した列を尊重)。

### 4.2 観測 / ロギング
- PASS/FAIL と、FAIL 時の欠落プロパティ・残存旧列・警告 (未知の追加列) を差分として報告する。

### 4.3 セキュリティ
- Notion トークンは Keychain からのみ取得し、DB を変更せず標準出力に資格情報を残さない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- スキーマ検証 executor (非対話バッチ、read-only)。実体: `scripts/verify_db_schema.py`。

### 5.2 ゴール定義
- 目的: 作成済み DB が設計通りのプロパティを持つことを機械保証し、後段 upsert の書き込み先 drift を未然に検知する。
- 背景: 手動編集や R1 の不完全実行でプロパティが欠落すると upsert が失敗する。作成後に正本と照合する検証層が必要。
- 達成ゴール: schema の全期待プロパティが DB に存在し、deprecated 旧サマリ/集計列が残らず PASS となる状態。drift があれば差分が明示され差し戻し可能な状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] schema の事実列・管理列が全て DB に存在する (PASS)
- [ ] 欠落があれば欠落プロパティが差分として提示されている (FAIL)
- [ ] deprecated 旧サマリ/集計列が残っていれば FAIL として提示されている
- [ ] DB にのみある未知の追加列は警告に留まり失敗扱いになっていない
- [ ] DB を一切変更していない (read-only)

### 5.4 実行方式
- 固定手順を持たない。未充足チェック項目を特定→解消手順を都度立案 (config から database_id 取得 / DB プロパティ取得 / schema 照合 など)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。
- 逸脱時: 欠落検知時は Layer 4.1 に従い FAIL として欠落を提示し R1 へ差し戻す。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-db-setup` SKILL.md ゴールシークループ (R1 の後段)。
- 後続 phase: PASS なら完了。FAIL なら R1 (build) へ差し戻す。

### 6.2 ハンドオフ / 並列性
- 直列: R1 (提供元) が記録した `notion.database_id` を本責務 (受領先) が検証対象に取る。FAIL 時は欠落差分を R1 へ返す。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- stdout に PASS/FAIL。FAIL 時は欠落プロパティ、追加列があれば警告を提示。

### 7.2 言語
- 本文: 日本語 (schema key / プロパティ名 / CLI は原文のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`.mf-kessai-config.json` の `notion.database_id` を検証対象に `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py"` を実行せよ。DB は変更しない (read-only)。`../schemas/notion-db-schema.json` の全期待プロパティが存在し、`deprecated_properties` の旧サマリ/集計列が残っていなければ PASS。欠落または deprecated 残存があれば FAIL とし、欠落プロパティ/残存旧列を提示して `build_notion_db.py` 再実行または手動追補を案内する。DB にのみある未知の追加列は警告に留め失敗扱いにしない。前置き禁止。
