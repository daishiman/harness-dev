# Phase 3 実装スペック (確定設計判断 + 実装DAG)

3アナリストの収束結論に基づく確定判断。ユーザー明示要件(R1-R5)は尊重し、技術的衝突のみ解消する。

## 確定設計判断 (D1-D6)

- **D1 会社名統合モデル = (X1,Y1)**: 正式名称はDB列のみ削除、source_by_field provenance としては official_name を残す。title 表示値 = `official_name or company_name`(フォールバック)。company_name フィールド・alt_key 素材・user_input origin は温存。
- **D2 R5精密化**: 確認用URL本文の会社名bulletは「origin=user_input かつ URLなし」の時のみ抑止。official_name(gbizinfo, gBizINFO URL)がある場合は会社名bulletとして残す(消すのでなく付け替える)。独立『正式名称』bulletは廃止し会社名へ統合。→ bullet最大5本(会社名/住所/郵便番号/法人番号/電話番号)。
- **D3 R2 origin**: phone は origin=web 維持、url = google検索クエリ(固定手段・weak)。doc の web 定義を「per-value根拠URL または 固定検索URL」へ更新。
- **D4 forbidden/preflight順序**: 正式名称を forbidden_properties に**今は追加しない**。schema の必須プロパティから外すのみ(preflight は正式名称列の有無に関わらずPASS)。live列の物理削除はユーザー実施(ユーザー明言)。
- **D5 R1方向**: ユーザー明示指定の通りトップURL `https://www.post.japanpost.jp/` 採用。doc文言を整合更新。検証性低下は受容済みtrade-off(smell・PASSを妨げない)。
- **D6 移行**: コードは新規行+backfillで対応。backfill は移行期に旧『正式名称』列(存在すれば)を official_name として読み title へ反映可能にする(既存行の登記名保全)。live列削除はユーザー実施。

## 実装DAG (順序厳守・依存ありは直列)

```
0. SSOT統一: validate_company_master.py の JAPANPOST_VERIFY_URL 独立定義(:103)を削除し
   `from postal_api import JAPANPOST_VERIFY_URL`(または既存import形式に合わせる)。
        │
   ┌────┴────┐
1. R1        2. R2
postal_api.py:72  google検索URL生成ヘルパをSSOT定義(1箇所)。
= "https://www.   `'https://www.google.com/search?q=' + quote('"'+phone+'"')` 相当。
  post.japanpost.jp/"  urllib.parse.quote で %22+番号を決定論エンコード(byte安定)。
                  enrich.py:335 phone の url=ヘルパ(phone値)、origin=web 維持。
        │            │
        └─────┬──────┘
3. R3/R4/R5 (結合・順序厳守):
   - notion_upsert build_properties: title = official_name or company_name。
     COL_OFFICIAL_NAME への書き込み停止(列削除)。
   - extract_existing_fields / backfill.row_from_page: title→official_name(フォールバックcompany_name)。
     旧『正式名称』列が live に存在すれば official_name として読む(移行・best-effort)。
   - select_backfill_targets: company_name(通称) を空欄判定対象から除外(無限backfill防止)。
   - confirm_url: build_entries で company_name/official_name を1エントリ統合
     (official_nameあれば 会社名ラベル+gbizinfo origin/URL、無ければ user_input→D2で抑止)。
     正式名称単独bullet廃止。ATTRIBUTE_FIELDS/FIELD_LABELS を会社名統合形へ更新。
   - validate: ATTRIBUTE_FIELDS/JP_COL_MAP/列構成検査(expected_cols)を 8→7列へ。
     FIELD_ALLOWED_ORIGINS["company_name"] に gbizinfo 追加(cap=公的データで確認済みと整合)。
     official_name 関連検査を整理。
   - schema: notion-db-schema.json から 正式名称 プロパティ除去(forbiddenには追加しない=D4)。
        │
4. docs: columns.md(8→7列, 会社名=登記名優先/通称非永続化明記),
   confirm-url-template.md(bullet例を会社名統合形へ, origin web定義更新, 郵便URL文言),
   data-sources.md(郵便/電話URL文言), SKILL.md(『会社名と正式名称を別属性保持』invariant撤回明記),
   README(列数/プロパティ説明)。
        │
5. tests: 破壊テスト全更新(7列, 会社名bullet反転=ユーザー入力行を出さない, 郵便URLリテラル,
   official_name origin, phone url=google, source_urls派生順, len==5/7 等)。
        │
6. pytest 実行(tests/test_company_master.py)で緑確認。失敗が出たら修正して再実行。
```

## 不変条件 (壊してはならない)
- JAPANPOST_VERIFY_URL は単一定義のみ(grep で1箇所)。
- alt_key の入力は常に通称(company_name)ベース(同一企業→同一キーの安定性)。
- preflight は移行期(live に正式名称列が残存)でもPASS(forbidden未追加)。
- 確認用URL本文に「会社名: ユーザー入力（URLなし）」は二度と出ない(R5厳守)。
- official_name の gBizINFO 検証URLは本文から失われない(会社名bulletへ統合)。
- render の決定論性(同一入力→byte一致)を維持。

## スコープ外(ユーザー実施)
- live Notion DB の『正式名称』プロパティ物理削除(ユーザー明言)。
- live 既存行への移行backfill実行(コードは対応するが実行は運用判断)。
