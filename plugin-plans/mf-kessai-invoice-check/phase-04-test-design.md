---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop の C01 (`run-mf-invoice-report`) の受入基準を test-first に導出して `feedback_contract` の inner/outer criteria として固定し、C05 (`mfk_period_report.py` 分類エンジン) のテスト観点、C06 (`notion_report_sink.py` 単一恒久 report DB sink) の「既存 DB 解決 + 未存在時のみ新規作成 + 月内冪等」テスト観点、C02 (sub-agent 二段確認) の検証観点、C04 (hook 拡張) の遮断/非遮断テスト観点を実装前に設計する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。goal-spec checklist C2〜C5 (12 ヶ月遡り/年契約/トライアル/契約終了) は分類エンジン C05 の `verify_by:test` 対象、C7 (同月内の日々追加=upsert 主キーで重複行 0) と C10 (既存 report DB 優先更新・未存在時のみ新規作成) は sink C06 の `verify_by:test` 対象であり、両者の単体テスト設計が本フェーズの中心になる (skill へ畳むと C7/C10 の test 対象が消える=幻テスト化を防ぐ)。

## 前提条件
- P03 の design-gate を通過している。
- C01/C05/C06 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
inner/outer criteria の定義 (index参照)。本 plan 固有の差分: C05 のテスト設計は「対象月決定(例: 2026-07-02 実行なら今月=2026-06分・先月=2026-05分)→前月+今月の取引先×商品集合突合→差分該当取引先のみ 12 ヶ月遡り」の 3 段階処理を固定する。状態遷移は、今月あり×前月あり=正常:継続発行、今月あり×前月なし=12ヶ月前の年契約から月額自動切替の可能性確認、今月なし×前月なし=対象外(元々請求なし)、今月なし×前月あり=年契約期間内/商品名トライアル完了/契約完了(請求ナシ(YYMM 終了)等)/該当なしなら発行漏れ候補(要対応)の全分岐をカバーする。候補取得は取引先単位、分類照合は取引先×商品単位、必要時のみ契約IDで disambiguate することも固定テストに含める。加えて (a) 契約完了は既存 mfk_reconcile.has_end_basis/_END_BASIS_PAT(確認内容の『請求ナシ』『(YYMM終了)』注記検出)→ verdict SUPPRESS_ENDED を入力に取り自由文を再パースしないこと(根拠なき終了月は REVIEW_ENDED_NO_BASIS で抑制しない安全弁の保全)、(b) 年契約正常化は既存 SUPPRESS_ANNUAL/MATCH_ANNUAL を一次源とし 12 ヶ月ルックバックは既存判定を上書きせずコメント根拠補強に限定すること(precedence)。★年契約の非請求月(前月あり今月なし)は今月 verdict が出ず curr=None になるため、年契約抑制を curr.verdict 単独で判定せず prev.verdict ∈ {MATCH_ANNUAL,SUPPRESS_ANNUAL}・12ヶ月履歴の年契約一括・DB1 支払サイクル(年間払い/年間一括更新)のいずれかを一次トリガーにすること(GAP-C05-ANNUAL-STOPPED)。回帰テスト=金子金物型ケース(prev=MATCH_ANNUAL 180万・curr 不在)が『前月あり今月なし(年契約周期)』=GAP_OK に落ち、要対応に誤爆しないことを test_mfk_period_report で機械検証する、(c) トライアル判定は canon 前の生商品名/MF 明細 desc を見ること(canon 4 値後は信号消失)、(d) 前月↔今月集合の突合キーは既存 mfk_reconcile.normalize/extract_names で表記揺れを吸収し継続契約が偽の前月あり今月なしへ誤分裂しないこと、(e) 継続発行(今月あり×前月あり)行も全 emit し非 emit は今月なし×前月なしのみであること、をテスト観点に含める。C06 のテスト設計は Design D として、(1) **出力先 DB 解決**: 指定見出しのトグル配下 DB (`in-block`)・プレーン見出し2直下 DB (`under-heading`)・ページ直下既存 DB (`page`)・未存在時のページ直下新規作成 (`page-created`) を fake-store で検証する、(2) **既存 DB 更新優先**: 既存 DB があれば POST /databases を呼ばず更新対象にする、(3) **対象月列の後付け**: 旧 7 列 DB には `_ensure_db_schema` が対象月列を PATCH 追加する、(4) **月内冪等**: 同月内で同一主キー {対象月×取引先×商品} を 2 回投入しても単一 DB へ 1 行に収束し重複行が出ない、(5) **別月共存**: 別 target_month は同じ DB 内で別行として保持する、(6) **先月の金額/今月の金額列充足**、(7) **列順・title 固定**: [取引先名, 対象月, 漏れチェック, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] と一致する、(8) **非破壊マージ**: run-1={A,B}→run-2={A,C} の順に投入後、DB が {A,B,C} を保持し以前 run の行が削除されないこと(clear-then-insert と区別可能・deleted=0)、の観点をカバーする。C02 は sub-agent ゆえコード単体テストでなく「真の漏れを問題ないと誤って隠していないか」の二段確認観点を設計する。C04 は既存 hook への拡張ゆえ、新規 classify/compare/period_diff の Write/Edit を exit2 で遮断しつつ既存 R1-R3/allowlist の挙動を壊していないことを両方テストする。

**2026-07-10 実運用フィードバック 4 要件の Red 観点 (spec-first 規律の回復・phase-05 が test 帰属を宣言する Red 側 locus をここに置く)**:
- **要件1 (継続発行=権威ある正常✓)**: `STATE_CONTINUED` (今月あり×前月あり) が `GAP_OK` (正常✓) で emit されること、`period_diff` が正規トークン『継続発行』で出て C06 `_STRUCTURAL_NORMAL_MARKERS` と **byte 一致** すること、前 run で要対応☐だった継続発行行が今 run で両月ありなら cross-run guard/reliable_issued 未確定に妨げられず正常✓へ訂正されることを、C05 producer→C06 sink の **marker seam 統合テスト** で機械検証する (各 unit 緑では捕捉不能)。
- **要件2 (出力先の確実な着地)**: `resolve_report_db` が config `report_database_id` の明示 pin を **step0** で最優先すること、未設定時のみ構造同定へ fallback すること、明示 pin なし+既存未発見時は `page-created` を作らず警告停止 (phantom abort) することを fake-store で検証する。
- **要件3 (要マスタ登録=正常✓)**: `_orphan_rows` (MF実績あり×シート契約なし) の `gap_check` が `GAP_OK` で emit され、コメントに『要マスタ登録(シートへ契約追加 or MF顧客ID登録で名寄せ恒久化)』が保持され、漏れ(要対応☐)にならないことを検証する。
- **要件4 (フローチャート SSOT+安全網)**: 4 状態分類がユーザー提供フローチャートに一致し、両月なしの `_classify_both_absent` が母集団入力源 (アクティブ月払い契約マスタ=支払サイクル列 or C01 R1-collect 供給) から 月払い×アクティブ×2ヶ月以上未発行 のみを要対応 surface し、契約なし/非月次を真の対象外 SKIP と判別することを検証する (月払い/年契約判別は DB1 支払サイクル配線を前提)。

## 成果物
- C01 の `feedback_contract.criteria` (inner+outer 各 1 件以上) が inventory に確定した状態。
- C05 のテスト設計 (`test_mfk_period_report` が満たすべきケース一覧・据置)。
- C06 のテスト設計 (`test_notion_report_sink` の Design D 出力先 DB 解決(in-block/under-heading/page/page-created)/対象月列後付け/月内冪等 upsert 主キー/別月共存/先月の金額/今月の金額列充足のケース一覧)。
- C02/C04 の検証観点確定。実装前は全て未達 (Red)。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの実行 (P06・kind 別観点はそちらで扱う)。
- C03 (slash-command) の受入 (output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] C01 の criteria が purpose 由来で inner「8 列 (取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメント) が『この左→右の順で』全行で埋まる(title=取引先名・列7=テキスト説明・金額税抜)。C05 producer キー(gap_check/target_month/amount/period_diff 等)→C06 8列写像は ROW_CONTRACT SSOT で固定し、C05 実出力→C06 を実 pipe で貫通する seam 統合テストで 8列全充足を機械検証する(各 unit 緑では捕捉不能)」・outer「同月内 2 回連続実行で重複行 0・非破壊マージで以前 run/別月行が消えない (日々追加・C06 sink が所有)・明示 pin (`report_database_id`) を step0 で最優先し、未設定時のみ指定見出しに紐づく既存 DB を優先更新し、明示 pin なし かつ 既存未発見時は phantom を作らず警告停止する(新規作成は明示 opt-in 時のみ・要件2)」を持つ。
- [ ] C05 のテスト設計が対象月決定(7月2日実行なら今月=6月分・先月=5月分)、取引先×商品集合の4状態(継続発行/前月なし今月あり/元々請求なし/前月あり今月なし)、差分該当取引先限定の 12 ヶ月遡り、年契約周期/年→月切替/トライアル完了/契約終了/発行漏れ候補(要対応)の全分岐をカバーし、契約完了=既存 has_end_basis→SUPPRESS_ENDED 消費(自由文非再パース)・年契約=既存 SUPPRESS_ANNUAL 一次源(遡りは補強のみ)・トライアル=canon 前の生商品名・突合キー=既存 normalize 再利用を含む。★curr=None×prev-verdict 各値の**分岐カバレッジ**を C05 完了条件の hard gate とする(年契約 prev=MATCH_ANNUAL→GAP_OK[金子金物型] / 契約完了 prev=MATCH_ENDED_FINAL→正常 / 隔月・単発 prev=MATCH_MONTHLY は保全テスト :242 と衝突ゆえ prev.verdict では分離せず入力層 curr-present 化で是正)。行カバレッジは既存 curr-present テストで素通りし金子金物型回帰の欠落を捕捉できないため、分岐カバレッジで幻テスト化を防ぐ(C06 の link coverage backstop と対称)。
- [ ] C06 のテスト設計が Design D 出力先 DB 解決(in-block/under-heading/page/page-created)・既存 DB 更新優先・対象月列後付け・月内冪等 (入力同定 {取引先×契約ID×商品}・stored key (対象月,取引先名,商品名) で 2 回投入 1 行収束。8列固定に契約ID列なし=契約ID非永続ゆえ契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上=漏れ隠蔽防止)・別月共存・--apply は --verified 必須(未指定 exit2)・先月の金額/今月の金額列充足・列順とtitle固定(取引先名=title・build_property 踏襲)・非破壊マージ(run-1={A,B}→run-2={A,C}で{A,B,C}保持=以前行が消えない)の観点をカバーする。
- [ ] C02 (誤って漏れを問題ないと隠していないかの二段確認) と C04 (新規 classify/compare/period_diff 遮断・既存 R1-R3 非破壊) の検証観点が確定し、実装前は criteria が未達 (Red) であることが確認できる。
- [ ] (2026-07-10 4 要件) 要件1 (STATE_CONTINUED→GAP_OK + period_diff『継続発行』marker seam byte 一致 + cross-run 正常✓訂正)・要件2 (report_database_id step0 pin + phantom abort)・要件3 (_orphan_rows GAP_OK + 名寄せコメント保持)・要件4 (_classify_both_absent 母集団入力源 + 月払い判別) の Red 観点が設計され、実装前は未達 (Red) であることが確認できる。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01 (report skill) / C02 (verifier) / C04 (guard hook 拡張) / C05 (分類エンジン) / C06 (冪等 sink)。
- 後続 P05 (implementation)。
