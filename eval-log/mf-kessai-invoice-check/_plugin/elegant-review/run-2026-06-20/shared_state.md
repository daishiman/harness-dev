# shared_state (Phase 1 → Phase 2 ファンアウト中継 / 200字以内)

mf-kessai-invoice-check(3skill)。発行漏れ=前月−今月発行を customer_id×対象年月キーで Notion 冪等 upsert。レビュー主眼=「毎月上書きで過去月の完了/未完了が失われる」懸念。重要事実:月次別キー+月次サマリ行(__monthly_summary__×対象年月,0件月も)+ページ本文へ実行履歴追記+管理列不可侵で履歴保持は既に実装済(notion_invoice_sink.py / README:198 / SKILL Key Rule4)。よって主眼は「実装済の検証・認識ギャップ解消・真の残課題発掘」。前回 run-2026-06-19 で4条件 PASS。
