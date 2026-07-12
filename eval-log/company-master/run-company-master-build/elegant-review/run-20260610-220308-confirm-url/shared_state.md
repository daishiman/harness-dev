# shared_state (Phase 1 → Phase 2)

現行は Web 検索由来の電話番号 URL のみ source_urls 経由で本文へ出力。gBizINFO の detail_page_url は wrapper/backfill で破棄、KEN_ALL は source_url 常に空。要求1=per-field 出典 URL 全項目化(enrich/resolve 伝搬・テンプレ5文言・validate(g)・backfill 全置換による URL 喪失・URL 無し由来の表現・byte 一致テストの6面に波及)。要求2=per-field フォールバック多段化(取得失敗時に Web 検索等の別パターンで取得できるまで試行、ただし誤値>>空欄と確度ラベルの正直さは不変)。
