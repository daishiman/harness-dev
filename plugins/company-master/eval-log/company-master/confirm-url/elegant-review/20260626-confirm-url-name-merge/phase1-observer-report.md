# Phase 1 俯瞰レポート (elegant-reset-observer)

## 改善要件 (R1〜R5)
- R1: 郵便番号確認用URL を `https://www.post.japanpost.jp/`（日本郵便トップ）固定にする
- R2: 電話番号確認用URL を Google検索の番号埋め込みクエリ `https://www.google.com/search?q="<電話番号>"` 固定にする
- R3: Notion「会社名」タイトルに正式名称(official_name)を格納
- R4: 「正式名称」DBプロパティを削除し会社名へ統合
- R5: 確認用URL本文の「会社名: ユーザー入力（URLなし）」bullet を出力しない（厳守）

## 影響ファイルと箇所
**R1**: postal_api.py:72(JAPANPOST_VERIFY_URL一次), :455/:479(source_url), validate_company_master.py:103(独立再定義), :273-276(url等価検査), enrich_company.py:302, confirm_url.py:335, confirm-url-template.md:44/60, columns.md:32, data-sources.md:35, tests:79/176/335/367/1656/1710/1743/1856
**R2**: enrich_company.py:196-217(verify_phone), :335(source_by_field phone), Googleクエリ定数は不在=新規SSOT要, confirm-url-template.md/columns.md:33/data-sources.md:36(web由来=strong/URL必須), tests:327/344-345
**R3/R4(不可分)**: notion_upsert.py:59-60(COL定数)/289-290(title=company_name)/311-312/256-257, validate_company_master.py:105(ATTRIBUTE_FIELDS)/110-113(JP_COL_MAP)/96-102(FIELD_ALLOWED_ORIGINS)/307-321(列構成検査), enrich_company.py:251-258/83, confirm_url.py:53/57-64, backfill.py:131-147, resolve_company.py, normalize.py(alt_key), notion-db-schema.json:5-21/22(forbidden), 正式名称/official_name/8列が122箇所26ファイル
**R5**: confirm_url.py:159-197(build_entries)/265-267/301-303/307-324, confirm-url-template.md:41, columns.md:37, tests:223(存在アサート=反転必須)

## 第一印象の懸念点 (8点)
1. JAPANPOST_VERIFY_URL SSOT二重定義(postal_api:72 + validate:103)。R1で片方のみ変更すると validate(g) が全postal行を reject。
2. R3/R4 と R5 の意味衝突: 会社名へ official_name(gBizINFO検証URL有) を統合する一方、R5で会社名bulletを消すと登記名のgBizINFO検証URLが本文から失われうる。R3後の会社名表示由来(user_input or gbizinfo)が未確定。
3. company_name の三役: (a)Notion title (b)alt_key=法人番号未確定行の代替キー (c)source_by_field user_input由来。title に official_name を入れると用途分岐。
4. 「6属性」「8列」前提の連鎖: R4が「列のみ削除(属性は会社名統合)」か「属性ごと削除」かで 6→5属性/8→7列 の更新範囲と forbidden_properties 追加要否が変わる。
5. 既存Notionデータ後方互換: live行は 会社名=通称/正式名称=登記名。物理削除+R3で意味混在。preflight_schema が正式名称列不在を要求→列削除前に書くと preflight FAIL の順序依存。
6. R1方向性(具体→粗): `.../zipcode/` の方が用途に具体的。トップへ変えると手動再検証性が論点。
7. R2 URL正規化/SSOT: `q="<電話番号>"` のダブルクォート(%22)エンコード要否。origin=web の意味が strong根拠ページ→固定検索クエリへ変質し doc 記述と整合崩れ。
8. テスト破壊確実: test:367(リテラル等価), test:223(存在アサート反転), R2/R3/R4 で多数スタブ破壊。変更と同一PRでテスト更新必須。
