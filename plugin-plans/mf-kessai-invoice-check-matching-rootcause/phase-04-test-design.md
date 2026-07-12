---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト)

## 目的
確定6要因の受入基準を test-first で導出し、症状再現の MF実績ゴールデンfixture (paws=C1収集脱落/2nd Community=C2 curr=None+C4 prev取消/HOSONO=C2+C5 代理店collapse=goal-spec C12) と「今月金額=null かつ忠実発行済み=偽発行漏れ7社→0件」回帰を tests/ へ凍結する設計を固定する。実装前は criteria が未達 (Red) であることを確認する。

## 背景
症状は3社の実在取引先で確認済みのため、これらを golden fixture として凍結し pytest 回帰化することが受入の核になる。C07 の feedback_contract (IN1=inner/OUT1,OUT2=outer) は purpose 語彙由来の criteria として既に inventory に確定しており、本フェーズはこれを Red として固定する。

## 前提条件
- P03 の design-gate を通過している。
- C01-C07 の goal/checklist/quality_gates/feedback_contract が inventory に確定済み。
- C07 の feedback_contract.criteria (IN1/OUT1/OUT2) が参照できる。

## ドメイン知識
- 症状再現ゴールデンfixture (C12): paws有限会社 (C1 billing=account_transfer_notified 収集脱落再現)・2nd Community株式会社 (C2 curr=None 脱落 + C4 prev=REVIEW_CANCELED 誤NEW再現)・HOSONO株式会社 (C2 脱落 + C5 代理店複数エンドクライアント同一商品collapse再現)・MATCH_ANNUAL新規群 (C3 過剰要対応再現) の当月MF実績+期待レポート行。
- Red = 実装前 (改修前コード) でこれら3社の当月金額が誤って「今月なし」/GAP空白/orphan非表示になることを確認する状態。
- tests_min=80 が各 script component (C01-C05) 共通の harness_coverage 下限。
- C07 の inner/outer criteria: IN1 (carrier=actual_amount/reliable_issued/supply_state 貫通の seam test) が inner、OUT1 (3社golden fixture回帰全件PASS)/OUT2 (既存verdict・MF実績第一級の characterization 非後退) が outer。

## 成果物
- C01-C06 各 script/sub-agent の RC対応回帰観点 (tests_min=80 準拠) の確定。
- C07 feedback_contract (IN1/OUT1/OUT2) が Red として固定された状態。
- tests/ 凍結対象 (3社golden fixture+期待レポート行) の設計。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの実行 (P06・kind別観点はそちらで扱う)。
- 非skill component の実行時受入 (output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] C12 (paws/2nd Community/HOSONO golden fixture+期待レポート行+偽発行漏れ7社→0件) が tests/ 凍結対象として設計され、改修前は失敗 (Red) することが確認できる。
- [ ] C01 (収集是正)/C02 (顧客ID解決)/C03 (collapse保全)/C04 (NEW/取消/代理店分類是正)/C05 (R1決定論) 各々に、要因対応の回帰観点が二値で設計されている。
- [ ] C07 の feedback_contract IN1 (carrier貫通seam test)/OUT1 (golden fixture全件PASS)/OUT2 (既存verdict・MF実績第一級の非後退characterization) が purpose 語彙由来で Red として固定されている。

## 参照情報
- component-inventory.json C01-C07 (quality_gates/feedback_contract)。
- goal-spec.json checklist C12 (golden fixture)・C10 (MF実績第一級非後退)・C11 (fetch fidelity非後退)。
- 後続 P05 (implementation)。
