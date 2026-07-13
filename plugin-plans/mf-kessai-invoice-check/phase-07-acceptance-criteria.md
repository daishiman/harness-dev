---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
C01 (`run-mf-invoice-report` skill) の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「前月↔今月の発行状況を比較して真の発行漏れだけを残した冪等レポートを生成する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは goal-spec checklist C1〜C12 (index「受入確認」章対応表) を purpose 由来の受入観点で二値判定する成果物評価であり、実行 (criteria-test の実走) は build フェーズが担う。

## 前提条件
- P06 で harness テストが緑。
- C01 の output_contract と `feedback_contract.criteria` が確定している。
- purpose「前月↔今月比較レポートの冪等生成」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
AC (受入基準) と品質ゲートの区別 (index参照)。本 plan 固有の差分: 冪等の観測は 2 軸で行う。(1) 月内冪等 (C7): 同一対象月で 2 営業日目・3 営業日目相当のデータを連続投入し、単一恒久レポート DB が入力同定 {取引先×契約ID×商品}・stored key (対象月,取引先名,商品名) で重複行 0 に収束し日々追加されることを観測する(8列固定に契約ID列なし=契約ID非永続ゆえ契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上=漏れ隠蔽防止)。(2) 出力先 DB 解決 (C10・Design D + 明示 pin): 明示 pin (config `report_database_id`) を step0 で最優先し、未設定時のみ `report_toggle_block` が指す指定見出しを起点に既存 report DB を トグル配下 DB・プレーン見出し直下 DB・ページ直下既存 DB の順で探索して更新対象にする。明示 pin なし かつ どれも無ければ phantom を作らず警告停止し、指定ページ『請求書発行チェック』(report_parent_page)直下への新規作成は明示 opt-in 時のみ行う(要件2)。トグル見出しでもプレーン見出し2でも同じ論理キーで受け、`db_location` (pinned/in-block/under-heading/page/page-created) で実際の解決結果を観測する。加えて (3) 非破壊マージ (C11): 以前 run で書いた行や別月行が今回入力に無くても単一 DB から削除されず全情報が保持されること (clear-then-insert でないこと) を観測する。

## 成果物
- C01 の AC 判定結果 (PASS/FAIL の二値、C1〜C11 対応)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C1: レポートが取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 8 列を『この左→右の順で』全行で持ち、title(=ページ作成/ページ名)プロパティ=取引先名・列7=テキスト説明・金額は税抜と判定できる (先月・今月の金額が並置され比較可能)。
- [ ] C2〜C5: 7月2日実行時に今月=6月分・先月=5月分として扱い、取引先×商品集合の4状態(継続発行/前月なし今月あり/元々請求なし/前月あり今月なし)と年契約周期(既存 SUPPRESS_ANNUAL 一次源)/年→月自動切替/トライアル完了(canon 前の生商品名)/契約終了(既存 has_end_basis→SUPPRESS_ENDED)の各イレギュラーが根拠コメント付きで正しく分類されると判定できる。
- [ ] C6〜C8: 分類不能な差分のみが真の発行漏れとして漏れチェックに残り、C02 (sub-agent) が誤隠蔽を検出し、C7 (同月内の日々追加=入力同定 {取引先×契約ID×商品}・stored key (対象月,取引先名,商品名) で重複行 0・契約ID非永続ゆえ契約ID違いは要対応優先 collapse で漏れを隠さない・C06 sink 所有) が満たされると判定できる。
- [ ] C9: MF API 参照専用維持と新規 classify/compare 再実装遮断が判定できる。
- [ ] C10: **明示 DB pin (config `report_database_id`) が step0 で最優先** され、明示 pin 時はその DB へ確実に着地すると判定できる。未設定時のみ指定見出し (`report_toggle_block`) に紐づく report DB を構造同定 (トグル配下 DB=`db_location=in-block`、プレーン見出し2直下 DB=`under-heading`、ページ直下既存 DB=`page`) で既存確認し更新対象にする。**明示 pin なし かつ 既存 report DB 未発見時は phantom DB を作らず警告停止** し、新規作成 (`page-created`) は明示 opt-in 時のみと判定できる (database は block_id 親で作成不可だが既存 DB の更新は可能・『出力先が指定先でない』の根治・C06 sink 所有)。
- [ ] C11: 単一恒久 DB への上書きが非破壊マージで、以前 run で書いた行や別月行が今回入力に無くても削除されず全情報が保持されると判定できる (run-1={A,B}→run-2={A,C}→{A,B,C}・clear-then-insert でない・C06 sink 所有)。
- [ ] C12: MF実績あり×請求確認シートに契約なし=要マスタ登録行が正常✓ (漏れチェック=✓) で emit され赤 (要対応) にならず、コメントに『要マスタ登録(シートへ契約追加 or MF顧客ID登録で名寄せ恒久化)』が付くと判定できる (C05 `_orphan_rows` を `GAP_OK`・C06 sink 所有)。
- [ ] 要件1 (継続発行=権威ある正常✓の cross-run 訂正): 継続発行 (両月あり) 行が前 run で赤 (要対応☐) だった場合でも、今 run で両月ありなら cross-run safe guard/reliable_issued 未確定に妨げられず正常✓へ訂正されると判定できる (C06 が `period_diff`『継続発行』を `_STRUCTURAL_NORMAL_MARKERS` に含める・『金額あるのにチェックが入らない』の根治)。
- [ ] 要件4 (両月なし安全網 surface): 両月なしでも 月払い×アクティブ×2ヶ月以上未発行 (年契約/契約完了/トライアル/対象外除外) の行が安全網として要対応 surface され、フローチャートの対象外に落ちて黙殺されないと判定できる (C05 `_classify_both_absent`)。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01。後続 P08 (refactoring)。
