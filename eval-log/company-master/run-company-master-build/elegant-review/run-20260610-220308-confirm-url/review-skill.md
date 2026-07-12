# elegant-review レポート: 確認用URL全項目化+フォールバック多段化 (run-20260610-220308-confirm-url)

- 対象: plugins/company-master (scope_mode=skill 内の出典仕様+取得戦略) / 実施: 2026-06-10 / loop_count: 2
- 要求1: 全6属性について「値をどこで検証できるか」(由来+URL) を Notion ページ本文に記述 (AI 取得情報の人間検証可能性)
- 要求2: 取得できない項目は別パターンで取得できるまで手段を尽くす (誤値>>空欄・確度の正直さは不変)
- フロー: Phase 1 reset → Phase 2 並列3分析 (30/30 思考法) → Phase 3 executor F (出典系)+G (フォールバック系) 直列×各2周 → 実機 E2E → 独立 approver **approve**

## verdict: 4条件全 PASS (pytest 69 / repo 83 passed・30 paradigm coverage OK)

## 設計の核 (Phase 2 収束)

1. **provenance record**: `source_by_field {field: {origin, url}}`、origin enum 5値 {gbizinfo, ken_all, web, user_input, none}。source_urls は列順派生 (後方互換)
2. **2階建て provenance**: strong=per-value 取得元 URL (gBizINFO 詳細ページ/Web hit)、weak=固定検証ページ (日本郵便郵便番号検索)、URL 無し由来=正直なラベル (「ユーザー入力(URLなし)」)。「全項目に URL」の原理的不可能性を正直に解消
3. **現行バグ発見→修復**: backfill の本文無条件全置換により既存出典 URL が喪失し本文が虚偽化する構造欠陥 → 既存本文パース+**URL 非減少マージ** (列の既存非空保護と対称化)+pagination+同期失敗の顕在化
4. **fallback tier 正本** (data-sources.md): tier1 gBizINFO (検索パターン複数化) → tier2 KEN_ALL+jigyosyo 第二索引 → tier3 WebSearch (URL 必須) → tier4 空欄+備考引き継ぎ。tier→確度ラベル上限と属性×許可段ホワイトリスト (postal=Web不可等) を validate が機械照合 (確度昇格=Goodhart を機械遮断)
5. **「取得できるまで動く」の正しい実装**: 無限探索でなく「定義済み有限段を尽くし、missing_fields+attempts ({field,source,pattern,result,reject_reason}) で人間へ正直に引き継ぐ」。同一 (source,pattern) 再試行禁止・MAX_ATTEMPTS_PER_FIELD=3・backfill 2パス運用 (--web-findings)
6. **信頼キー不変条項**: Web 由来住所 (address_provenance=web) では 2 要素一致でも自動確定禁止・再 resolve 最大1回・法人番号不一致なら候補列挙へ降格 (誤同定増幅ループの遮断)

## 実機 E2E (2026-06-10, 実トークン)

- upsert created → ページ本文に**全6属性の由来+検証URL** が出力されることを確認 (gBizINFO 3属性=法人詳細ページURL / 会社名=ユーザー入力ラベル / 未取得=未確定ラベル) → テスト行 archive
- **外部事象の発見**: 日本郵便の zip 直 DL (ken_all.zip/jigyosyo.zip/県別/大小文字違い) が HTTP 404。同サイト HTML=200・他ドメイン zip=取得可 → プログラム DL 遮断 (または配信障害) と判断。**遮断回避は実装せず**、設計どおりの縮退 (attempts に具体的理由→空欄+備考→missing_fields 引き継ぎ) が実機で機能することを確認
- 404 対処 (2周目): `refresh-ken-all --from-file <zip>` の手動取り込み口 / stale キャッシュ縮退 (DL 不能でも既存キャッシュで継続) / doctor の KEN_ALL 診断 (WARN+ブラウザ手順提示) / `ken_all_unavailable` 備考でデータ未取得と逆引き不能を区別

## 変更規模

- executor F: 12 ファイル (スキーマ正本・伝搬・マージ・テンプレ・validate・テスト 50 passed)
- executor G: 17 ファイル (tier 正本・jigyosyo・attempts・2パス・契約文書・テスト 62→69 passed)
- 全テスト: tests/test_company_master.py 69 + tests/test_plugin_lint_coverage.py 14 = 83 passed

## 残課題 (low)

1. backfill 要確認行再検索の冷却 TTL (attempts 引き継ぎ+同一試行スキップが一次抑止。実測待ち)
2. 実 zip での import_from_file 実機確認 (人間のブラウザ DL が必要。doctor→取り込み→逆引きで確認可能)
3. 日本郵便 郵便番号 API (2025-05 提供開始・要利用登録) への移行 — optional tier として open_issues #5 管理
