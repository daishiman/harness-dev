# Phase 1 俯瞰レポート (思考リセット・俯瞰)

> 親 context を一旦リセットし、対象を fresh に再読込した一次観察。判定は行わず Phase 2 へ橋渡しする。

## 対象と前提
- 対象: plugins/company-master（worktree task-20260626-071909-wt-4・**未コミット変更**が検証対象）
- 既存 run `20260626-confirm-url-name-merge` が R1-R5 を実装済みと主張（verdict 全PASS）。本 run はその完了を二段確認する位置づけ。

## 関連ファイル列挙（役割）
| パス | 役割 |
|---|---|
| scripts/confirm_url.py | 確認用URLページ本文テンプレ展開（SSOT=confirm-url-template.md をパース）。会社名bullet統合(_merged_company_entry)・R5抑止 |
| scripts/enrich_company.py | 属性補完。`PHONE_SEARCH_BASE`(:103) 電話Google検索URL生成・postal検証URL付与(:307) |
| scripts/postal_api.py | `JAPANPOST_VERIFY_URL`(:73) 郵便番号固定検証URL SSOT |
| scripts/notion_upsert.py | Notion upsert。title=official_name優先(:305)・正式名称列廃止・preflight_schema(:177) |
| scripts/backfill.py | 空欄補完・`--migrate-company-title` 移行モード |
| scripts/validate_company_master.py | 検証ルール（郵便URL固定必須:295・7列構成） |
| references/confirm-url-template.md | 確認用URL本文 文言の唯一の正本（md SSOT） |
| references/notion-db-schema.json | live preflight 照合スキーマ。forbidden に正式名称(:21) |
| references/company-master-columns.md | 7列定義の正本 |
| references/data-sources.md | 郵便/電話URLの出典規約 |
| skills/*/SKILL.md, README.md, agents/*.md | 仕様・運用記述の追従対象 |

## R1-R5 一次観察（実装箇所）
- R1 郵便番号固定URL: `postal_api.py:73` = `https://www.post.japanpost.jp/`。validate:295 で固定URL必須を機械検査。confirm_url サンプル:371 も一致。
- R2 電話番号 無料Web検索: `enrich_company.py:103` `PHONE_SEARCH_BASE="https://www.google.com/search?q="` → `phone_search_url()`(:106) で `"番号"` 完全一致検索を quote。有料DB依存なし。
- R3 会社名title=正式名称: `notion_upsert.py:305` `title_value = f.get("official_name") or f.get("company_name","")`。build_properties/patch_empty_cells 双方で official 優先。
- R4 正式名称列削除: schema から列除去 + `forbidden_properties`(:21) に登録。**live DB 実測=正式名称列なし・preflight PASS**（orchestrator GET 確認済）。
- R5 本文に余計記述なし: `confirm_url._merged_company_entry` が origin=user_input/none かつURLなしの会社名bullet を None で抑止。template.md:33 にも明記。

## 第一印象の懸念点（Phase2 で検証する仮説・判定はしない）
1. **C1矛盾**: 既存 implementation-spec D4 は「正式名称を forbidden に今は追加しない」と記述。現状 schema は forbidden に正式名称を含む。live削除済なら整合だが、doc(spec)とコードの記述が表面上ねじれていないか。
2. **C1矛盾**: SSOT 単一定義性。JAPANPOST_VERIFY_URL / PHONE_SEARCH_BASE が複数箇所に literal 再定義されていないか（confirm_url サンプルやテストの literal は許容範囲か）。
3. **C2漏れ**: doc 層（columns.md / data-sources.md / SKILL.md / README）が 8→7列・電話URL無料化・会社名統合に全て追従しているか（コード追従漏れ）。
4. **C3整合性**: 会社名bullet統合の境界（official_name 取得済だが title が通称のまま、user_input+URLなし、none）の挙動が template.md 記述・validate・テストで一貫しているか。
5. **C4依存**: `--migrate-company-title` 移行モードと alt_key(通称ベース不変) の依存、backfill が旧正式名称列を読む best-effort 経路が live列削除後に破綻しないか。テストが緑か。
