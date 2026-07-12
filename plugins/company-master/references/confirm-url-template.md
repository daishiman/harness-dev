# 確認用URL ページ本文 定型テンプレート (正本)

> 確認用URL は Notion DB のプロパティ列ではなく**ページ本文**に固定テンプレートで出力する (DB 冗長化回避・100% 同一テンプレ SSOT)。
> 本文は自由記述禁止。各属性の取得由来 (`source_by_field`) と検証用URLを下表の要素から決定論的にレンダリングする。**会社名 bullet は official_name(登記名) の出典を統合し、正式名称の独立 bullet は持たない** (会社名/住所/郵便番号/法人番号/電話番号 の最大 5 bullet)。
> 本ファイルが唯一の正本 (SSOT)。`scripts/confirm_url.py` がパースして展開する。コードに文言を二重定義しない。
> 取得日時・検索クエリは本文に書かない (冪等 byte 安定のため機械層 replay JSONL へ記録する)。

## template_key → 要素マッピング

| template_key | 値 |
|---|---|
| `heading` | `確認用URL（手動検証用）` |
| `intro` | `各属性の値の取得由来と検証用URLの一覧です。値の正確性を手動で確認する際に参照してください。` |
| `bullet_with_url` | `{attribute}（{origin_label}）: {url}` |
| `bullet_no_url` | `{attribute}: {origin_label}（URLなし）` |
| `body_no_fields` | `取得由来を記録した属性がありません（全属性が未確定）。` |

## origin → 表示由来マッピング

`source_by_field[field].origin` の enum 5値と本文表示語彙 (機関名+一般名) の対応。コードに語彙を二重定義しない。

| origin | 表示由来 |
|---|---|
| `gbizinfo` | `経済産業省 gBizINFO` |
| `japanpost` | `日本郵便 郵便番号データ` |
| `web` | `ネット検索` |
| `user_input` | `ユーザー入力` |
| `none` | `未確定` |

## レンダリング規約

- 属性の bullet は 2 形式: URL有り = `bullet_with_url`、URL無し由来 (ユーザー入力 / 未確定など) = `bullet_no_url`。「公的データ由来のためURL不要」のような断定文言は使わない。
- 本文 bullet の属性名・順序は会社名 → 住所 → 郵便番号 → 法人番号 → 電話番号 と一致させる。**会社名 bullet は official_name(登記名) の出典 (gBizINFO 検証 URL) を統合する**。正式名称の独立 bullet は廃止。official_name の出典が無く、かつ会社名が `user_input` または `none`(いずれも URL なし) のときは会社名 bullet を出さない (R5: 『会社名: ユーザー入力（URLなし）』は出力しない)。既存ページ本文に旧『正式名称: URL』bullet が残っていても、再同期時は会社名へ正規化・統合し正式名称の独立 bullet を復活させない。
- `source_by_field` がある行のページ本文 (heading_2 → intro → bullet×5。official_name 由来で会社名を統合した例):

  ```
  ## 確認用URL（手動検証用）

  各属性の値の取得由来と検証用URLの一覧です。値の正確性を手動で確認する際に参照してください。

  - 会社名（経済産業省 gBizINFO）: https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123
  - 住所（経済産業省 gBizINFO）: https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123
  - 郵便番号（日本郵便 郵便番号データ）: https://www.post.japanpost.jp/
  - 法人番号（経済産業省 gBizINFO）: https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1234567890123
  - 電話番号（ネット検索）: https://www.google.com/search?q=%2203-1234-5678%22
  ```

- 記録すべき由来が 1 件も無い行 (全属性が `none` で URL も無い未確定行) のページ本文 (heading_2 → body_no_fields):

  ```
  ## 確認用URL（手動検証用）

  取得由来を記録した属性がありません（全属性が未確定）。
  ```

## 運用ルール

- 入力の正本は `source_by_field` (= `{field: {origin, url}}`)。`source_urls` は `source_by_field` から列順に導出される派生値で、現行形式は `{attribute, origin, url}` (3キー)。旧2キー形式 (`{attribute, url}`) も後方互換で受理する (origin 欠落時は由来不明の URL を `web` 扱い)。
- 2階建て provenance: per-value 取得元 URL (gBizINFO 法人詳細ページ) を strong、固定検証手段 URL (日本郵便トップ https://www.post.japanpost.jp/ / 番号埋め込み Google 検索) を weak とし、URL 無し由来は表示由来ラベルのみ記す。
- create 時はページ本文へ append、update/backfill 時は既存『確認用URL（手動検証用）』セクションを**パースして URL 非減少マージ**のうえ置換する: 今回取得した出典のみ差し替え、既存本文にあって今回 URL を提示できない属性の出典は保持する (既存非空セル保護と対称。出典 URL を本文同期で喪失させない)。
