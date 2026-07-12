---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件)

## 目的
2026-07-09 の全段実データ調査で確定した独立6要因 (C1 収集billing-statusフィルタ/C2 R1-collect非決定論[構造的主因]/C3 STATE_NEW過剰要対応/C4 prev取消の継続性欠落/C5 代理店collapse/C6 MF顧客ID結合) を、7 component (C01-C07) への分解要件として固定する。PR#85(0.4.0)で確立した MF実績第一級・evidence据え置き・GET専用API・fetch fidelity fail-closed を後退させないことを要件の不変前提にする。証拠の正本は improvement-handoff.json。

## 背景
前回 plan (plugin-plans/mf-kessai-invoice-check-fidelity) は表示・判定層 (_amount_of/_is_issued の actual_amount 優先反転) を根治したが症状は継続した。実データ調査(実レポートDB=ユーザー提示URL・月スコープ忠実 reconcile(2606/2605)・両月 C03 通しの三点突合)で、C05/C03/reconcile は正しく動くのに下流の R1 が発行済み社の当月行を落とす(curr=None)ため症状が続くことを実証し、当初仮説2つ(名寄せ英字/カナ境界ミスが主因・REVIEW_QTY_MISMATCH=54 の系統的期待明細数バグ)を実データで否定した(3社ともシート名は MF側と normalize 一致・QTY_MISMATCH の月スコープ実測は1〜2件)。ユーザー承認済みの「全6要因根治」方針として同時に扱う。

## 前提条件
- goal-spec.json の checklist C1-C13 と improvement-handoff.json の findings(C1-C6)/retractions が確定している。
- 実 plugin mf-kessai-invoice-check の該当コード行 (scripts/reconcile_invoices.py:277 collect_mf / scripts/mfk_period_report.py compare_periods・classify_period_transition / scripts/notion_report_sink.py _prefer_action / lib/mfk_reconcile.py _boundary_customers / skills/run-mf-invoice-report/prompts/R1-collect.md) が参照可能。
- 姉妹 plan plugin-plans/mf-kessai-invoice-check-fidelity (表示・判定層根治済み・0.4.0/PR#85) との責務境界 (本 plan=発行漏れレポート根治の増分に限定) が合意されている。

## ドメイン知識
- C1 収集 billing-status: scripts/reconcile_invoices.py:277 collect_mf が /billings/qualified を status=invoice_issued 限定で取得し、account_transfer_notified 等へ進んだ発行済み請求を落とす(paws 6月=account_transfer_notified・55000税込=実在)。名前非依存・再発性。
- C2 R1-collect 非決定論[構造的主因]: curr-verdicts を吐く決定論スクリプトが不在で、R1-collect の LLM 手組みが発行済み社の当月行を落とす。実レポートで 2nd Community/HOSONO は今月金額=null(curr=None)だが忠実 reconcile では MATCH_MONTHLY。PR#85 修正は全て R1 の下流ゆえ R1 が落とす限り直らない=「前回直したのに直らない」真因。今月金額=null かつ要対応13件中7件が忠実では発行済み。
- C3 STATE_NEW 過剰要対応: mfk_period_report.py の STATE_NEW が curr.verdict=MATCH_ANNUAL(reconcile が年契約と判定済)を正常根拠に使わず lookback 未供給で全要対応化(『100億ThinkTank利用料』等 約25件)。
- C4 prev取消の継続性欠落: compare_periods/_is_issued が prev=REVIEW_CANCELED(前月発行→取消)を「発行なし」と同一視し継続契約を NEW 誤判定(2nd Community 5月分7/3取消)。
- C5 代理店/複数エンドクライアント: 1商品に複数契約(（○○様）異額)を持つ代理店で compare_periods の (取引先,商品) setdefault が幻の NEW+STOPPED を生成し notion_report_sink collapse が発行済み実額を隠す(HOSONO/マルブン等)。
- C6 MF顧客ID 0%: シート665行全て MF顧客ID 空で _boundary_customers の ID優先経路が未使用=全契約が名前依存。ユーザー要望(MF側取引先idで判断)の恒久解。
- 不変前提: MF掛け払いAPIは GET 参照専用を維持し (guard-mfk-readonly.py)、突合ロジックは lib/mfk_reconcile.py / scripts/mfk_actuals.py / scripts/mfk_period_report.py を再利用する (guard-mfk-no-reinvent.py allowlist・再発明しない)。

## 成果物
- 7 component (C01-C07) 分解要件の確定 (各 purpose/責務境界が goal-spec checklist C1-C13 と improvement-handoff findings C1-C6 に対応する状態)。
- 姉妹 plan mf-kessai-invoice-check-fidelity との責務境界の明示合意 (本 plan は発行漏れレポート根治限定、表示・判定層は再変更しない)。

## スコープ外
- component 分解の具体的 inputs/outputs/依存 DAG 設計 (P02 へ委譲)。
- 設計の合否判定 (P03 design-gate へ委譲)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] goal-spec.json の checklist C1-C13 が全て component-inventory.json のいずれかの component (C01-C07) へ紐づいている (要求→component の traceability)。
- [ ] 確定6要因 (C1 収集/C2 R1決定論/C3 NEW分類/C4 取消継続/C5 代理店collapse/C6 顧客ID) それぞれに対応する component が要件として確定している (C1→C01, C2→C05, C3/C4/C5(classify)→C04, C5(sink)→C03, C6→C02, 検証→C06, 配線→C07)。
- [ ] 当初仮説の否定 (名寄せ英字/カナ境界主因・QTY_MISMATCH=54系統バグ) が retraction として記録され、名寄せ堅牢化は C6(潜在対策)へ降格されている。
- [ ] 姉妹 plan mf-kessai-invoice-check-fidelity との責務境界 (本 plan=発行漏れレポート根治限定・表示判定層は変更しない) が明示されている。

## 参照情報
- goal-spec.json (checklist C1-C13/constraints/background の確定6要因記述)。
- improvement-handoff.json (findings C1-C6/retractions/plan_impact=実データ調査の証拠正本)。
- component-inventory.json (C01-C07)。
- 実 plugin scripts/reconcile_invoices.py・scripts/mfk_period_report.py・scripts/notion_report_sink.py・lib/mfk_reconcile.py・skills/run-mf-invoice-report/prompts/R1-collect.md。
- 後続 P02 (design)。
