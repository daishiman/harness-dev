---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「マネーフォワード掛け払いの前月↔今月発行状況比較レポート」改善構想を、6 component (C01 skill `run-mf-invoice-report` / C02 sub-agent `mfk-report-verifier` / C03 slash-command `run-mf-invoice-report` / C04 hook `guard-mfk-no-reinvent` (既存 in-place 拡張) / C05 script `mfk_period_report.py` (薄い差分エンジン) / C06 script `notion_report_sink.py` (月次レポート DB 冪等 sink)) の観点から目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` (checklist C1〜C12) を確定させる。

> **2026-07-10 実運用フィードバック是正 (4 要件・後段 /capability-build で実装)**: ユーザー提供フローチャートを分類の SSOT とし、(要件1) 継続発行=今月あり×前月あり=月契約の権威ある正常ゆえ漏れチェックは必ず正常✓ (『金額あるのにチェックが入らない』の根治=C05 STATE_CONTINUED を GAP_OK・C06 が period_diff『継続発行』を構造的正常マーカーへ加え cross-run guard を bypass)、(要件2) 出力先の確実な着地=明示 DB pin (config `report_database_id`) を第一級 (step 0) に最優先し未設定時のみ構造的同定へ fallback・phantom DB 新規作成を抑止 (『出力先が指定先でない』の根治)、(要件3) MF実績あり×シート契約なし=要マスタ登録は正常✓ (C05 `_orphan_rows` を GAP_OK へ反転)、(要件4) 両月なしでも 月払い×アクティブ×2ヶ月以上未発行は『先月・今月・12ヶ月以内』の請求問題確認の安全網として要対応 surface を維持する。詳細 SSOT=goal-spec constraints の [決定・2026-07-10] 4 件 + checklist C6/C7/C10/C12。

## 背景
既存 `run-mf-invoice-reconcile` は当月双方向照合のみを担い、前月↔今月の時間軸比較・12 ヶ月遡りによるイレギュラー分類・月次レポート DB への冪等再実行という新次元を持たない。本改善はこの新次元を「対称に 5 種を 1 つずつ埋める」のでなく「改善デルタが要する機能クラスタ (収集/分類/検証/冪等 sink/再発明遮断)」を先に列挙し新規 or 既存改修でラベリングしてから 6 実体へ分解する (Goodhart 回避)。同一構想は常に同一 `plan_dir=plugin-plans/mf-kessai-invoice-check/` へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- プラグイン構想 (前月↔今月比較レポート・4 イレギュラー分類・冪等再実行・月次レポート DB) が入力として与えられている。
- 既存プラグイン資産 (`lib/mfk_reconcile.py` 照合エンジン・`lib/mfk_api.py` 参照専用 GET・`lib/notion_reconcile_sink.py` 非破壊 upsert パターン・請求確認シート) が利用可能で再利用対象と確認されている。
- 6 component の kind 割当 (skill×1/sub-agent×1/slash-command×1/hook×1(既存拡張)/script×2) が判明している。

## ドメイン知識
plan 全体の用語 (2 軸直交/component_kind 5 種/月帰属/イレギュラー4分類/冪等上書き) は index `## ドメイン知識` を参照。本フェーズ固有の差分: 要件定義段階では checklist C1〜C12 それぞれがどの component に帰着するかの初期対応 (RTM) を index「受入確認」章の対応表として仮固定する。出力設計は **明示 pin 優先 + 単一恒久 report DB の既存確認 + 冪等上書き (Design D)** であり、C06 sink は明示 pin (config `report_database_id`) を step0 で最優先し、未設定時のみ指定ブロック/見出し周辺の既存 DB を `in-block` → `under-heading` → `page` の順で探し存在すれば更新する。明示 pin なし かつ 既存未発見時は phantom を作らず警告停止し、新規 report DB 作成 (指定ページ『請求書発行チェック』(report_parent_page) 直下) は明示 opt-in 時のみ行う (要件2)。Notion API は database 作成の親に block_id を指定できないため新規作成はページ直下だが、UI でトグル内または見出し直下に置かれた既存 DB の更新は可能とする。レポート列は取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 8 列とし、先月の金額と今月の金額を並置して比較可能にする (C1 更新)。特に C7 (同月内の日々追加=行キー {対象月×取引先×商品} で重複行 0・継続発行=権威ある正常✓) と C10 (明示 pin 優先→既存 DB 更新→pin なし+未発見は phantom 抑止) と C12 (要マスタ登録=正常✓) は C06/C05 が所有する要件であることをここで明示する。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1〜C11/constraints/handoff_targets) の確定。
- target_plugin_slug=`mf-kessai-invoice-check` と plan_dir の確定値。
- C1〜C11 各要件のどの component が担うかの初期対応表 (index 受入確認章と対応・C7/C10→C06)。

## スコープ外
- component 分解の確定・build_target/依存 DAG の設計 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` の checklist C1〜C12 (C10=既存 report DB 優先更新+明示 pin/phantom 抑止・C12=要マスタ登録=正常✓) が全て非空で purpose「前月↔今月比較レポートの冪等生成」から導出されている。
- [ ] 2026-07-10 実運用フィードバック 4 要件 (継続=正常✓/出力先 pin/要マスタ登録=正常✓/フローチャート SSOT+安全網) が goal-spec の checklist (C6/C7/C10/C12) と constraints ([決定・2026-07-10] 4 件) の両層へ反映されている。
- [ ] target_plugin_slug が ASCII kebab (`mf-kessai-invoice-check`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 対象 component C01〜C06 (`component-inventory.json`)。後続 P02 (この goal-spec を component 分解の入力とする)。
