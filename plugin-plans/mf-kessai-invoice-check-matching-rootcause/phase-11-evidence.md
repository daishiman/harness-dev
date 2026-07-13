---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: 
---

# P11 — evidence (検証)

## 目的
スクショ非保有の Markdown 主体 harness (照合層根治後の mf-kessai-invoice-check) が、5 要素 (lint exit0 / schema parity / build-trace coverage / content-review verdict / coverage JSON) + 手動検証 (実 Notion/MF 当月データ) で完了を証明できる状態にする。

## 背景
旧「evidence (スクショ)」を replace し Markdown evidence 5 要素へ写像する (phase-lifecycle.md §7 P11行)。本 plan 固有の追加要求として、症状再現 3 社 (2nd Community株式会社/HOSONO株式会社(細野)/paws有限会社) の当月請求が build 後の実運用で正しく取得・表示・チェックされ、実レポートで「今月金額=null かつ忠実発行済み」の偽発行漏れが0件になることを、機械 evidence だけでなく人手の手動検証観点としても明記する。

## 前提条件
C01-C07 全 component の quality_gates (P09 確定) + harness_coverage (P06 確定)。goal-spec C12 (ゴールデンfixture凍結) が回帰テストとして機能する設計になっていること。

## ドメイン知識
5 要素の定義は io-contract.md §10 が正本: lint exit0 ログ/schema parity/build-trace coverage 全 PASS/content-review verdict (PASS)/`eval-log/coverage/skills/<plugin>__<skill>.json`。手動検証はこの 5 要素を補完する追加観点であり代替ではない (両輪)。

## 成果物
(1) 5 要素 evidence の build 後観測方法の宣言。(2) 手動検証項目=「実 Notion/MF で 2nd Community株式会社/HOSONO株式会社/paws有限会社の当月請求金額が正しく取得・表示され、漏れチェック列が正しい判定になっており、偽発行漏れが0件であること」を目視確認する受入手順。

## スコープ外
evidence 実測 (lint/coverage 実走・Notion 実データ確認の実施自体) は build 後の運用担当・L4 評価者へ委譲する。本フェーズは evidence 観点の確定に留まる。

## 完了チェックリスト
- [ ] lint exit0 ログ・schema parity・build-trace coverage・content-review verdict (PASS)・coverage JSON の 5 要素が C01-C07 各々で観測可能な設計になっている
- [ ] goal-spec C12 のゴールデンfixture (paws/2nd Community/HOSONO 再現+偽発行漏れ7社→0件) が pytest 回帰として凍結される設計になっている
- [ ] 手動検証項目「実 Notion/MF で 2nd Community株式会社/HOSONO株式会社/paws有限会社の当月金額が正しく取得・表示・チェックされ偽発行漏れが0件であること」が本フェーズの evidence として明記されている

## 参照情報
io-contract.md §10 / goal-spec.json C12 / phase-lifecycle.md §8 P11 セル
