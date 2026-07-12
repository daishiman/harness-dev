# Phase 2 確定設計 directive (3 分析 SubAgent の収束結果)

## 要求
- 要求1: Notion 本文の確認用URLを全項目化 — 全属性について「その値をどこで検証できるか」の URL を本文に記述 (AI 取得情報の人間検証可能性)
- 要求2: per-field フォールバック多段化 — 一次手段で取得できない項目は別パターンで取得を試み、手段を尽くしてから空欄+引き継ぎ。誤値>>空欄と確度ラベルの正直さは不変

## 確定設計 (3 agent 一致)

### A. 出典スキーマ (論点思考: これが決まれば残りが従属導出)
- record に `source_by_field: {field: {origin, url}}` 新設。origin enum = {gbizinfo, ken_all, web, user_input, none}
- `source_urls` は source_by_field から ATTRIBUTE_FIELDS 固定順 (columns.md 列順) で導出する派生値に降格 (後方互換)
- 2階建て provenance: strong=per-value 取得元 URL (gBizINFO detail_page_url / Web hit URL)、weak=固定検証手段 URL (日本郵便 郵便番号検索 https://www.post.japanpost.jp/zipcode/)、URL 無し由来=ラベル (ユーザー入力)
- 表示語彙は機関名+一般名 (KEN_ALL→「日本郵便 郵便番号データ」、gBizINFO→「経済産業省 gBizINFO」)。本文の属性名・順序は columns.md 列定義と一致
- 取得日時・クエリは本文に書かない (冪等 byte 安定のため機械層 replay JSONL へ)

### B. 現行バグ修復 (因果関係分析 rank1 — 要求1 の前提)
- backfill は web_findings 無しで enrich を呼ぶため source_urls が常に空 → sync_confirm_url_body の無条件全置換で既存出典 URL が喪失し「ネット検索由来の値はありません」という虚偽本文になる
- 修復: 本文同期を「URL 非減少マージ」へ — 同期前に既存『確認用URL』節をパースし、保護された既存セルの出典は保持・今回更新したフィールドの出典のみ差替 (列の既存非空保護と対称)
- sync_confirm_url_body に pagination (has_more/next_cursor)。同期失敗は黙認せず action=body_failed として顕在化+replay 退避

### C. 伝搬配線 (システム思考: 1 パッチで貫通、継ぎ接ぎ禁止)
- resolve: entity に source_url (detail_page_url) を追加。candidates/旧 replay は .get() 既定で後方互換
- wrapper (company_master.py) / backfill (merge_entity_defaults): source_url を enrich へ伝搬
- ken_all.lookup_postal: source_url に日本郵便 郵便番号検索の固定 URL を実装 (現状常に空)
- enrich: 6属性すべてに origin を必ず付与 (company_name=user_input 含む)。gBizINFO 3属性に strong URL、postal に weak URL、phone に web URL

### D. テンプレ・正本改訂 (同一 PR で 6 面同期)
- confirm-url-template.md: bullet を「- {列名一致属性名}（{表示由来}）: {URL}」/ URL 無し「- 属性名: 由来ラベル（URLなし）」の 2 形式へ。footer『公的データ由来のためURL不要』と body_no_urls『全項目が公的データ由来』の断定文言を廃止 (全属性空欄の未確定行用の文言に変更)
- columns.md: 「公的データ由来値: URL 不要」ルールを撤廃し per-field 出典規則へ改訂
- validate (g): 新形式 record (source_by_field あり) のみ「全6属性 origin 必須・origin=web は url 必須」、旧形式は現行検査へ縮退 (後方互換 gating)
- byte 一致テストの期待値をテンプレ md から導出 (SSOT 導出化) し同時更新
- 回帰テスト追加: 「既存本文 URL あり×新 source_urls 空→同期後も URL 非減少」

### E. フォールバック多段化 (要求2)
- data-sources.md に fallback tier 表を正本化: tier1 gBizINFO=公的データで確認済み / tier2 KEN_ALL+jigyosyo=公的データ取得 / tier3 WebSearch=ネット検索(要確認)+URL必須 / tier4 全滅=空欄+未確定+備考引き継ぎ。手段→確度ラベル上限の機械照合を validate へ追加 (昇格禁止=Goodhart 遮断)
- 属性×段ホワイトリスト: phone=Web可 / postal_code=KEN_ALL+jigyosyo (Web 不可) / hojin_bango・official_name・address=gBizINFO 検索パターン複数化+Web は要確認止まり
- enrich/resolve 出力に missing_fields[] + attempts[] ({field, source, pattern, result, reject_reason}) を追加し replay JSONL へ併記。agent は attempts に無い (source, pattern) のみ次試行する gap-driven 単調前進。MAX_ATTEMPTS_PER_FIELD=3
- 停止条件: 有限1巡・同一 (source,pattern) 再試行禁止・確度昇格禁止。失敗時は試行履歴を備考定型 placeholder + replay JSONL で人間へ引き継ぐ (「取得できるまで動く」=有限の定義済み段を尽くし、無限探索は人間裁定へ明示移譲)
- 信頼キー不変条項: Web 由来住所での再 resolve は自動確定禁止 (address_provenance=web は確度上限ネット検索(要確認)・法人番号が初回と不一致なら候補列挙へ降格)。再 resolve は最大1回
- jigyosyo.zip (大口事業所個別番号 https://www.post.japanpost.jp/zipcode/dl/jigyosyo/zip/jigyosyo.zip) を ken_all.py へ第二索引として追加 (open_issues#1 一意確定律速の直接対策。トヨタ町 471-8571 等の事業所個別番号が引けるようになる)
- gBizINFO 検索パターン複数化: 正規化名・法人格除去名での再照会 (normalize 共有正本を使用、Python 決定論層)
- backfill に --web-findings 受け口 (page_id キーの属性別候補マップ) + dry-run で「Claude 介入が必要な行リスト」出力の 2 パス運用
- backfill 再検索の冷却: 要確認行の Web 再検索はマーカー/TTL で重複実行を抑止
- 国税庁法人番号公表サイト API は optional tier (トークン発行 2週〜1.5月のため既定無効・Keychain 鍵在時のみ・doctor で SKIP 表示) — 本ラウンド対象外、open_issues へ登録

### F. 契約文書更新
- SKILL.md: 出力契約 (per-field 出典)・フォールバック原則・実行経路表 (backfill の Claude 介入 2 パス)・チェックリスト
- agents/company-master-enrich-attributes.md: web_findings 契約の全項目化+gap-driven 試行+確度上限
- agents/company-master-resolve-identity.md / prompts/R1: source_url 出力契約・address_provenance・信頼キー不変
- agents/company-master-notion-upsert.md: 入力契約
- README: 本文の見方 (6属性の検証 URL)
