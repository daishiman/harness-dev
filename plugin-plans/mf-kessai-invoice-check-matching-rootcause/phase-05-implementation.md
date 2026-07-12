---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全7 component を後段 builder へ委譲して実体化し、P04 で固定した criteria を満たす (Green) 状態にする。build 順は依存 top-sort (C01→C02→C04→C03→C05→C06→C07) であり phase 順ではない。

## 背景
本フェーズは確定6要因の最小差分修正方針 (component-inventory.json の build_target/required_file_edits が SSOT) を宣言する到達状態であり、実コードそのものはここに書かない。修正は後段 builder (plugin-scaffold=C01-C05、run-build-skill=C06、run-skill-create=C07) が担う。証拠の正本は improvement-handoff.json。

## 前提条件
- P04 で C01-C07 の criteria が Red で確定している。
- 後段 builder (plugin-scaffold/run-build-skill/run-skill-create) が利用可能。
- 実 plugin 該当ファイル (scripts/reconcile_invoices.py・scripts/mfk_period_report.py・scripts/notion_report_sink.py・lib/mfk_reconcile.py・lib/notion_sheet_writeback.py・skills/run-mf-invoice-report/prompts/R1-collect.md・R3-verify.md 等) への required_file_edits が確定済み。

## ドメイン知識
実装対象=各 component の build_target・修正方針 (詳細は component-inventory.json required_file_edits がSSOT):
- C01 mfk_collect_status.py (収集是正・reconcile_invoices.py modify): collect_mf(:275-279) の /billings/qualified 取得を status=invoice_issued 限定でなく発行後 status(account_transfer_notified 等)も含める。billing.status を carrier/fetch_audit へ開示。transaction.status=passed の月帰属フィルタは不変。
- C02 mfk_customer_id_resolve.py (顧客ID解決・新規): mf_index から会社名→MF顧客ID 解決マップを GET 専用で構築し一意確定分を backfill 提案。書込みは既存 notion_sheet_writeback を --apply 下で再利用(新 write surface なし)。_boundary_customers が ID優先を発火できるよう配線。
- C03 notion_report_sink collapse 保全 (notion_report_sink.py modify): _prefer_action(:290-303)/_merge_action_comments で collapse 時に reliable_issued の発行済み実額を要対応・null行が上書きしないよう保全(発行済み実額保全 ∧ 漏れ隠蔽なし)。
- C04 mfk_period_report.py (分類是正・modify): (C3) STATE_NEW へ curr.verdict=MATCH_ANNUAL の正常化 short-circuit を追加。(C4) compare_periods/_is_issued へ prev の『発行後取消』(REVIEW_CANCELED/inactive_canceled+canceled_at)を継続性上 prev_issued 相当に扱う分岐を追加(supply_state=none とは区別)。(C5 classify側) _needs_disambiguation/_match_key を endclient（○○様）/契約ID 粒度へ拡張し (取引先,商品) setdefault の幻遷移を止める。PR#85 の MF実績第一級は後退させない。
- C05 mfk_verdict_export.py (R1決定論producer・新規・構造的主因): R1-collect の LLM 手動直列化を `reconcile()`(C01/C04 適用済)直接呼び出しの決定論 producer へ置換し、全 rec(GAP/SUPPRESS 含む)+orphans を carrier 4種(actual_amount/reliable_issued/supply_state/canceled_at)込みで curr/prev-verdicts へ無損失直列化(curr=None を出さない)。差分該当社の 12ヶ月lookback fetch も担う。
- C06 mfk-report-verifier (検証軸・修正): 偽発行漏れ(curr脱落の発行済み裏取り)/collapse隠蔽/MATCH_ANNUAL過剰要対応 の軸を additive 追加する。
- C07 run-mf-invoice-report (配線・修正): R1-collect 実行指示を C05 呼び出しへ置換し carrier 明記 + STATE_NEW該当社への --lookback-12mo 供給、R4-render の sink collapse を C03 保全へ更新(冪等upsert骨格は不変)。
- build 順 top-sort: C01→C02→C04→C03→C05→C06→C07。guard-mfk-no-reinvent.py の sanctioned basename 登録が新規 script(C02/C05)で required。

## 成果物
- 全7 component の実体 (build_target) が生成/修正された状態 (Green)。
- 実 plugin 該当ファイルへの required_file_edits 反映 (委譲先実行結果)。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT重複整理 (P08)。
- 表示・判定層 (`_is_issued`/PR#85 で確立したロジック) 自体の再変更 (スコープ外・非後退維持のみが対象)。R4-render の冪等upsert骨格 (C03 collapse保全以外は不変)。

## 完了チェックリスト
- [ ] 依存top-sort順 (C01→C02→C04→C03→C05→C06→C07) に全component がbuildされ、P04 criteria が Green (受入テストPASS) になる。
- [ ] 確定6要因の最小差分修正 (required_file_edits) が実plugin該当行 (reconcile_invoices.py:277、mfk_period_report.py compare_periods/classify_period_transition、notion_report_sink.py:290-303、R1-collect.md、lib/mfk_reconcile.py _boundary_customers) に反映されている。
- [ ] evidence (DB2 matched_amount)・GET専用API・fetch fidelity fail-closed ゲート・MF実績第一級が変更されず温存されている。

## 参照情報
- component-inventory.json (build_target/required_file_edits/依存DAG)。
- improvement-handoff.json (findings C1-C6=修正方針の証拠正本)。
- goal-spec.json constraints。
- 後続 P06 (test-run)。
