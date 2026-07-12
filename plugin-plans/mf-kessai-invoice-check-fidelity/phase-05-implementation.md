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
全 7 buildable component を後段 builder へ委譲して実体化(既存ファイルの modify + C05/C06 の新規 script)し、P04 で設計した criteria を満たす(Green)状態にする。build routing は `component-inventory.json` の依存 top-sort 順(C05→C06→C03→C04→C01→C02、C07 は C06 依存)に実行する。

## 背景
本改善は既存プラグインへの増分のため、build は「新規生成」ではなく「既存 SSOT の modify + 2 script(C05/C06)の新設」が中心になる。MF API の GET 専用維持(`lib/mfk_api.py` に POST/PATCH/DELETE を実装しない)と突合ロジック再発明禁止(`mfk_reconcile.normalize/extract_names` 等の再利用)を constraints として厳守する。実 build 自体は本 plan の範囲外(run-skill-create/run-build-skill/`harness-creator/scripts/build-script-route.py` へ委譲)。script route は `plugin-scaffold` という planner 語彙だけでは実行完了にならず、`executor_hint` の script builder で required_file_edits まで処理する。

**C05 統合配線 (amount-gate 根治の実装手順)**: `scripts/mfk_actuals.py`(C05)を新規の純関数モジュールとして切り出し、build_mf_index を基盤に取引先×商品粒度の `{issued: bool, actual_amount: int|null, supply_state, canceled_at}` を当月/先月それぞれ抽出する。build_mf_index が既に確定保持する active/inactive_canceled/inactive_pending/excluded の三分別+canceled_at を supply_state へそのまま写像し、actual_amount は active 供給に限定する(inactive の金額は取消前額であり実発行額ではないため actual_amount には昇格させず、supply_state 側で判別可能にする=取消明細を issued 化して漏れ隠蔽を再生産しない)。既存 `lib/mfk_reconcile.py` の `find_mf_match`/`classify` はこの C05 を import し、全 status(match/typo/mismatch/no_supply/inactive)の verdict 行へ `actual_amount` + reliable issued フラグを焼く。**carrier は一意化する**: canonical carrier は行 top-level の `actual_amount`(新フィールド)単一に固定し、`find_mf_match` の `evidence:None` は**据え置く(evidence 修復はしない)**。理由=`scripts/reconcile_invoices.py:348` の `build_sink_rows` が `matched_amount=_ev(evidence,'amount')` を読むため、`evidence` を書き換えると別 skill `run-mf-invoice-reconcile` の DB2 `matched_amount` が `REVIEW_AMOUNT_MISMATCH` 行で変化し温存制約に違反する(carrier を evidence にすると温存境界を割る)。したがって金額空白の主因である現行 `amount_mismatch` / `no_supply` の `evidence=None` は、`evidence` を埋めるのではなく verdict 行 top-level `actual_amount` を添付して解消する(C05 route の `required_file_edits` として `lib/mfk_reconcile.py` を必ず変更するが、`evidence` byte は不変・legacy `evidence.amount`/`amount` は READ 専用の後方互換で WRITE しない)。加えて `supply_state∈{inactive_canceled,inactive_pending}` の行は `issued=False`/`actual_amount=null` を強制し、`_is_issued`/`_amount_of` の `evidence.amount` fallback を `supply_state==active` に限定して取消前額の issued 化(偽陰性再生産)を隔離する。`scripts/mfk_period_report.py`(C03)も同じ C05 を直接 consume し、flowchart の判定入力(D1/D2/D3)を MF実績由来に切替える。**D3(金額列常時表示)の実現には `_amount_of` の金額源優先順位の反転が必須**である: 現行実装(mfk_period_report.py:173)は期待単価(現行単価/amount/expected_amount等)を優先し evidence.amount へ fail-soft する順だが、これを canonical `actual_amount` 優先・legacy `evidence.amount`/`amount` は境界で正規化・期待額はオーバーレイ表示(金額差コメント)へ降格する順に反転する。evidence を単に埋めるだけでは優先順位が変わらず根治にならない。lib/mfk_reconcile.py 自体の build_target(`plugins/mf-kessai-invoice-check/lib/mfk_reconcile.py`)は本 plan の component として独立管理しないが、C05 route の `required_file_edits` と completion_gate でブロックする。

**C06 fetch trace 配線 (最新性確認の実装手順)**: `scripts/mfk_fetch_audit.py`(C06)は network=false の監査器であり、ページング metadata を自力生成しない。`lib/mfk_api.py` に GET 専用を保った `iter_all_with_trace` 相当の adapter を追加し、各ページの `pagination.has_next` / `pagination.end` / `pagination.total` / `items_count` / request params / issue_date range を `fetch_trace` として保持する。R1 collect または `scripts/reconcile_invoices.py` は curr/prev/lookback 取得時にこの trace を保存して C06 へ渡す。C06 route は `lib/mfk_api.py` / `reconcile_invoices.py` / `prompts/R1-collect.md` / `guard-mfk-no-reinvent.py` を `required_file_edits` とし、`mfk_fetch_audit.py` 単体生成だけでは完了にしない。

## 前提条件
- P04 で C01 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている(mode=update)。
- 後段 builder(run-skill-create / run-build-skill / harness-creator/scripts/build-script-route.py)が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順(C05→C06→C03→C04→C01→C02、C07 は C06 依存でどこでも可)。
- builder_status: 4 script route(C03/C04/C05/C06)は `plugin-scaffold`(contract-only・`gap_ref: GAP-SCRIPT-BUILDER`・executor_hint=`plugins/harness-creator/scripts/build-script-route.py`)、C01 は `run-skill-create`(executor-backed)、C02/C07 は `run-build-skill`(executor-backed)。
- 既存ロジック保全: `find_mf_match`/`classify`/`normalize`/`extract_names`/`has_end_basis`/`_classify_stopped`/`build_mf_index` は再利用し、ゼロから作り直さない。C05 は新規追加だが、これらの既存関数を呼び出す側であり置き換えるものではない。
- fetch fidelity の部分欠損時の中間状態: C06 が 12ヶ月ルックバック窓の部分取得(一部月の pagination 不完全)を検出した場合、fail-closed 全停止ではなく該当行を「漏れ断定保留=要確認」へ降格し、D1 裏取りは「未確認」に留めて真の新規と断定しない(per-customer 差分アラートで total 偶然一致による欠落見落としも防ぐ)。当月分自体の fidelity 違反(pagination NG/count不一致)は従来通り fail-closed で下流を止める。
- 既存 verdict の温存確認: `SUPPRESS_ANNUAL`(年契約抑制)・`MATCH_ENDED_FINAL`(契約終了最終請求判定)・J1名寄せ偽陰性封鎖は本改善の前後で不変であることを P04 の characterization fixture で凍結し、C05/C03 の modify がこれらを退行させないことを実装完了条件に含める。

## 成果物
- 全 7 component の実体(C01 skill・C02 agent・C03/C04/C05/C06 script・C07 command)が build_target に生成(modify/新設)された状態。
- `lib/mfk_reconcile.py` が C05(`scripts/mfk_actuals.py`)を consume する統合配線の modify。
- `lib/mfk_api.py`/R1 collect が C06(`scripts/mfk_fetch_audit.py`)へ pagination_trace を渡す fetch trace 配線の modify。
- `envelope-draft/plugin.json` を基にした plugin manifest(version 0.3.0 維持)。

## スコープ外
- カバレッジ拡充・テスト網羅(P06)。
- purpose 受入判定(P07)・SSOT 重複整理(P08)。
- 既存 `run-mf-invoice-reconcile`・年間前払い抑制・契約終了最終請求判定ロジックの変更(温存対象・触れない)。

## 完了チェックリスト
- [ ] 依存 top-sort 順(C05→C06→C03→C04→C01→C02, C07)に全 component が build され、C01 の criteria が Green(受入テスト PASS)になる。
- [ ] build 実体パスが inventory の build_target と一致する(C05 は新規 `plugins/mf-kessai-invoice-check/scripts/mfk_actuals.py` として生成される)。
- [ ] `lib/mfk_reconcile.py` の find_mf_match/classify が C05 を consume し、全 status に `actual_amount`/issued evidence を添付する統合配線が実装されている。
- [ ] `lib/mfk_api.py`/R1 collect が page metadata を捨てず `fetch_trace` を C06 へ渡し、C06 の pagination/total/stale 監査が実データで実行できる。
- [ ] MF API が GET 専用のまま維持され、hooks/guard-mfk-readonly.py / guard-mfk-no-reinvent.py の二層が機能し続ける。
- [ ] `_amount_of` の金額源優先順位が MF実績(`actual_amount`)優先・期待額オーバーレイ後へ反転されている(期待額優先のままではないことを確認)。
- [ ] STATE_NEW 裏付けなし(12ヶ月ルックバックに年契約一括なし/未実行)で `gap_check` を `GAP_ACTION`(☐要確認)へ flip し、裏付けありのみ `GAP_OK` 維持する(D1)ことが C03 route の completion_gate で機械固定されている(当月 fidelity NG=exit1 で fail-closed・lookback 部分欠損=exit3 は要確認降格の三値と整合)。
- [ ] `SUPPRESS_ANNUAL`/`MATCH_ENDED_FINAL`/J1名寄せの既存verdictが改修前後で不変(P04 characterization fixture が回帰なく PASS)。

## 参照情報
- `handoff-run-plugin-dev-plan.json`(build routing・mode=update) / `component-inventory.json`(依存 DAG)。
- 対象 component C01-C07。
- 後続 P06(test-run)。
