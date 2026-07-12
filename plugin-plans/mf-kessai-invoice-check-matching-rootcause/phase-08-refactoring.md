---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: false
  reason: 根治は既存関数への最小差分修正+純関数SSOT分離(C01-C05)であり、それ自体がRC是正の設計。別途新規リファクタ対象を持たないためN/A
---

# P08 — refactoring (改善)

## 適用除外 (N/A)
本フェーズは適用外 (`applicability.applicable: false`)。理由: 確定6要因の根治は既存関数 (`scripts/reconcile_invoices.py` の `collect_mf`、`scripts/mfk_period_report.py` の `compare_periods`/`classify_period_transition`、`scripts/notion_report_sink.py` の `_prefer_action`、`lib/mfk_reconcile.py` の `_boundary_customers`) への最小差分修正と、新規純関数 SSOT (C02 `mfk_customer_id_resolve.py` / C05 `mfk_verdict_export.py`) への責務分離そのものであり、それ自体が本 plan の設計 (P02/P05) で既に「重複を作らない」形に確定している。既存ロジックの重複排除 (`lint-ssot-duplication.py` 起点の作業) を要する独立したリファクタ対象を本 plan 固有には持たない。SSOT 重複回避の担保は各 route の `required_file_edits` (既存関数への差分修正・二重実装を残さない設計) と `hooks/guard-mfk-no-reinvent.py` sanctioned basename 登録で既に達成される。本フェーズは section 床を免除される (phase-lifecycle.md §8 `applicability` 既定表)。

## 参照情報
component-inventory.json C01-C05 の `required_file_edits` (委譲縮退の設計根拠) / `plugins/mf-kessai-invoice-check/hooks/guard-mfk-no-reinvent.py` / phase-lifecycle.md §8 P08 セル / io-contract.md §9 `applicability` 既定
