---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「タスク台帳を Notion DB へ冪等同期する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが冪等同期という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose「タスク台帳を Notion DB へ冪等同期する」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 冪等の観測方法: 同一台帳で二回実行し、二回目の追加/更新件数 0 を観測する (C01/C03 の outer criterion)。
- fail-closed: 判定不能・異常時に安全側 (拒否) へ倒す性質 (C11 hook の受入観点)。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01/C03: 同期・初期投入後に台帳差分/全件が Notion へ反映され、二回目実行の追加/更新が 0 件 (冪等) と判定できる。
- [ ] C02: 既知の発行漏れを注入して reconcile が全件検出すると判定できる。
- [ ] C11: 破壊的操作が hook で fail-closed に阻まれると判定できる。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C11。
- 後続 P08 (refactoring)。
