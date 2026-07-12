# Notion 企業マスタ 7列定義 + ページ本文 (正本)

> 企業マスタ DB は **計7列のみ**で構成する: 5属性 + 『情報の確かさ』+ 『備考』。
> **正式名称は独立列を廃止し会社名(title)へ統合する**: 会社名タイトルは gBizINFO 登記名(official_name)を優先表示し、無ければ入力通称(company_name)を表示する。company_name(通称)・official_name(登記名)はともに record の `source_by_field` (出所層) に provenance として保持するが、DB 列は会社名(title)1つに統合する (表示層と出所層の分離・別属性を別 DB 列で持つ不変条件は撤回)。
> 確認用URL は DB プロパティ列ではなく**ページ本文**へ固定テンプレートで出力する (`confirm-url-template.md` 正本)。
> `source` 列・`last_verified` 列・`確認用URL` 列・`正式名称` 列は追加禁止 (出所区別は『情報の確かさ』列が兼ね、正式名称は会社名へ統合)。
> DB ID はリテラル直書きせず `notion_config.get_db_id('company-master')` で解決する。

## 列定義

| 列名 | Notion型 | 内容 | フォーマット規約 |
|---|---|---|---|
| 会社名 | title | gBizINFO 登記名(正式名称)を優先表示・無ければ入力通称。通称は alt_key/同定用に `source_by_field` で保持するが独立列は持たない | — |
| 住所 | rich_text | 所在地 | 都道府県起点に正規化 |
| 郵便番号 | rich_text | 郵便番号 | 〒なし・ハイフン込み 8文字 `NNN-NNNN` |
| 法人番号 | rich_text | gBizINFO 確定 13桁 | 13桁数字 (信頼キー) |
| 電話番号 | rich_text | 代表電話 | ハイフン区切り (例 `03-1234-5678`)。形式チェックのみ・正確性は非保証 |
| 情報の確かさ | select | 各行の確度 | 下記 4ラベル固定 (英語enum禁止) |
| 備考 | rich_text | 取得失敗原因 | `remarks-templates.md` の定型文言のみ。複数失敗は改行区切り |

## ページ本文: 確認用URL (per-field 出典規則)

確認用URL は DB プロパティ列ではなく**ページ本文**へ固定テンプレートで出力する (DB 冗長化回避・100% 同一テンプレ SSOT)。テンプレートの唯一の正本は `references/confirm-url-template.md`、展開は `scripts/confirm_url.py` (`render_blocks` / `render_text`) が担う。

**全項目化**: 本文には各属性について「その値をどこで検証できるか」(取得由来 + 検証用URL) を記述する (AI 取得情報の人間検証可能性)。出典の正本は record の `source_by_field` (= `{field: {origin, url}}`, 6 属性 = company_name/official_name/address/postal_code/hojin_bango/phone_number)。**会社名 bullet は official_name(登記名) の出典を統合して 1 本にまとめ、正式名称の独立 bullet は持たない**。`source_urls` は `source_by_field` から**列順**で導出される派生値 (後方互換)。各 field 値は dict で拡張可能 (フォールバック多段化が `attempts` 等を併設できる)。

- **origin enum (5値固定)** と表示語彙 (機関名+一般名。byte 確定値は `confirm-url-template.md` 正本):

  | origin | 表示由来 | 検証用URL |
  |---|---|---|
  | `gbizinfo` | 経済産業省 gBizINFO | 法人詳細ページ URL (per-value・strong) |
  | `japanpost` | 日本郵便 郵便番号データ | 日本郵便トップ (郵便番号検索の入口) の固定 URL `https://www.post.japanpost.jp/` (weak。URL 単独で値を再確認できないことは受容済み trade-off) |
  | `web` | ネット検索 | per-value 根拠ページ URL または固定検索手段 URL (電話番号は番号埋め込み Google 検索 URL)。**URL 必須** |
  | `user_input` | ユーザー入力 | URL なし (由来ラベルのみ) |
  | `none` | 未確定 | URL なし |

- 本文 bullet の属性名・順序は会社名 → 住所 → 郵便番号 → 法人番号 → 電話番号 と一致させる (会社名 bullet は official_name の検証 URL を統合する。正式名称の独立 bullet は廃止)。bullet は `- 属性名（表示由来）: URL` / URL 無し由来は `- 属性名: 表示由来（URLなし）` の 2 形式 (断定文言「公的データ由来のためURL不要」は使わない)。
- **会社名 bullet の R5 抑止**: official_name(登記名) の検証 URL が無く、会社名が `user_input` かつ URL なしのときは会社名 bullet を本文に出さない (『会社名: ユーザー入力（URLなし）』は出力しない)。official_name に gBizINFO 検証 URL があれば会社名 bullet として統合表示する (出所を失わない)。
- 全属性が `none` で記録すべき由来が無い未確定行は、定型の未確定文言 1 行を出す (正本: `confirm-url-template.md` の `body_no_fields`)。
- create 時はページ本文へ append、update/backfill 時は既存『確認用URL（手動検証用）』セクションを**パースして URL 非減少マージ**のうえ置換する: 今回取得した出典のみ差し替え、既存本文にあって今回 URL を提示できない属性の出典は保持する (既存非空セル保護と対称。出典 URL を本文同期で喪失させない)。同一入力での再同期は byte 一致 (冪等)。
- 取得日時・検索クエリは本文に書かない (冪等 byte 安定のため機械層 replay JSONL へ記録する)。

## 『情報の確かさ』値域 (4ラベル固定)

1. `公的データで確認済み`
2. `公的データ取得`
3. `ネット検索(要確認)`
4. `未確定(要確認)`

英語のコード値は使わず日本語ラベルのみを使用する。

行全体の確度 (`derive_overall_certainty`) は**最も弱い属性に合わせる保守的設計**とする: 1 属性でも空欄・未確定があれば行全体を『未確定(要確認)』へ倒す。これは誤値混入のコストが空欄のコストより遥かに大きい (誤値 >> 空欄) という非対称コスト原則の意図的な反映であり、「確度を高く見せる」方向の変更は禁止。

## 整合ルール (deterministic_checks 対応)

- 非空の郵便番号は `^\d{3}-\d{4}$` (8文字) に一致する。
- 非空の電話番号はハイフンを含む数字列 (形式のみ・正確性は非保証)。
- 非空の住所は都道府県名で始まる。
- 非空の法人番号は 13桁数字。
- 全行に『情報の確かさ』列があり、値は 4ラベルのいずれか (英語enum値は 0件)。
- いずれかの属性が空欄の行は『情報の確かさ』が『未確定(要確認)』かつ『備考』に定型文言が入っている。
- per-field 出典 (後方互換 gating): `source_by_field` がある新形式 record は**全6属性に origin** (enum 5値) があり、`origin=web` の属性は url 非空である。`source_by_field` の無い旧形式は『ネット検索(要確認)』行の `source_urls` 非空検査へ縮退する。
- upsert 一意キーは gBizINFO 確定 13桁法人番号。空/未確定法人番号でのキー衝突を起こさない。
