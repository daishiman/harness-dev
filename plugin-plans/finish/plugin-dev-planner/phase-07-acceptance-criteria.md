---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
P06 のテスト実行結果を goal-spec.checklist (C1-C12) と C01 の `feedback_contract.criteria` (IN1-IN6/OUT1/OUT2)・C02 の genuine 判定結果 (C8/C12・plan-findings.json bucket) に照らして判定し、purpose (plugin-dev-planner の harness-creator 仕様への完全準拠、および層A/層B の生成品質) が満たされたかを確定する。

## 背景
本 plan の受入正本は index.md の「## 受入確認」節が宣言する受入観点であり、その裏付けは C01 の feedback_contract.criteria が criteria-test として実行された結果 (機械層) と、C02 の R1-evaluate.md が genuine 判定した結果 (意味層・C8/C12) である。本 phase は build 後にこの照合を行う仕様である。P07 は判定行為中心の gate 系 phase であり縮小要件 (受入例/事前解決済み判断は簡略形) を適用する。

## 前提条件
- P06 のテスト実行結果 (exit code・件数、および C02 の fork evaluator 実行結果) が揃っている。

## ドメイン知識
- **判定基準**: IN1 (target_plugin_slug 不一致検出)・IN2 (entry_points/inventory 突合検出)・IN3 (曖昧語彙 denylist violation 検出・C6。ignored_context は説明/否定例として別集計し FAIL にしない)・IN4 (`_PHASE_SECTION_HINT` 完全一致検出・C7)・IN5 (受入例サブ節存在検出・C10)・IN6 (事前解決済み判断サブ節存在検出・C11)・OUT1 (既存テスト退行なし・C9)・OUT2 (harness-coverage 12 軸自己適用・C3) の 8 criteria が全て PASS し、かつ C02 の genuine 判定 (C8: phase 本文の具体度・C12: 受入例/事前解決済み判断の実効性) が plan-findings.json へ critical な曖昧箇所指摘なしで記録されたとき、goal-spec.checklist の C1-C12 全項目を `done: true` へ更新する。
- **部分達成時の扱い**: criteria のいずれかが FAIL、または C02 の genuine 判定が具体的な曖昧箇所指摘を伴う場合、該当する checklist 項目は `done: false` のまま残し、指摘箇所に応じて P08 (refactoring) または P05 (implementation) への差し戻しを検討する (C8/C12 の指摘は該当 phase 本文の P05 差し戻しが基本経路)。

## 成果物
- goal-spec.checklist の done フラグ更新結果 (build 後の実施記録)。
- 受入観点 (IN1-IN6/OUT1/OUT2) それぞれの PASS/FAIL 判定記録。
- C02 の genuine 判定結果 (C8/C12) の記録。

## スコープ外
- 判定基準そのものの変更 (index.md の受入確認節が正本・本 phase は照合のみ)。

## 完了チェックリスト
- [ ] IN1 (target_plugin_slug 不一致検出) が PASS。
- [ ] IN2 (entry_points/inventory 突合検出) が PASS。
- [ ] IN3/IN4 (曖昧語彙 denylist・未カスタマイズ完全一致検出・C6/C7) が PASS。
- [ ] IN5/IN6 (受入例・事前解決済み判断サブ節存在検出・C10/C11) が PASS。
- [ ] OUT1 (既存テスト退行なし・C9) が PASS。
- [ ] OUT2 (harness-coverage 12 軸自己適用・C3) が PASS。
- [ ] C02 の genuine 判定 (C8/C12) が critical な曖昧箇所指摘なしで plan-findings.json に記録されている。
- [ ] goal-spec.checklist の C1-C12 全項目が `done: true` へ更新されている。

### 受入例 (満たす例 / 満たさない例・判定行為ゲート簡略形)
- 満たす例: IN1-IN6/OUT1/OUT2 の PASS/FAIL 判定と C02 の genuine 判定結果が本ファイルの完了チェックリストへ記録され、C1-C12 の done フラグ更新が goal-spec.json へ反映される。
- 満たさない例: 一部 criteria の判定を省略したまま C1-C12 の done フラグを一括で true に更新する。

### 事前解決済み判断
- 分岐点: C8/C12 の FAIL (曖昧箇所指摘あり) をどの phase への差し戻しとするか → 判断: 指摘箇所が phase 本文の記述精度に起因する場合は P05 (implementation) へ、設計方針そのものへの疑義の場合は P02/P03 へ差し戻す (指摘内容に応じて選択する二経路とする)。

## 参照情報
- `index.md` (## 受入確認)。
- `component-inventory.json` (C01.feedback_contract.criteria / C02.responsibilities)。
- `goal-spec.json` (checklist)。
- 後続 P08 (refactoring)。
