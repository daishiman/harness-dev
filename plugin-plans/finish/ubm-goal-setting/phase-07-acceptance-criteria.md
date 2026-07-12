---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 完了
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C15, C16, C17, C18, C19]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「北原さん式ゴールセッティングの目標設定・振り返り対話とナレッジ差分同期を1 pluginへ移植する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが目標設定・振り返り対話とナレッジ同期という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose「北原さん式ゴールセッティングの目標設定・振り返り対話とナレッジ差分同期を1 pluginへ移植する」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 統一ハイブリッド構造21項目の観測方法: 週報/月報/期報を生成し validate-goal-output.py が全21項目・NG表現0件・やらないこと3項目以上を検証して PASS することを観測する (C16 の outer criterion)。
- fail-closed: `UBM_VAULT_ROOT` 配下の Write/Edit/MultiEdit で、許可リスト (目標設定保存先・Daily.md embed 更新先) に入らないパスを安全側 (拒否) へ倒す性質 (C04 hook の受入観点)。vault 外と `UBM_VAULT_ROOT` 未設定時は保護対象外として素通しする。

## 成果物
- C16 (run-ubm-goal-setting): 週報/月報/期報の目標設定・振り返り対話を生成し、統一ハイブリッド構造21項目を満たし validate-goal-output.py が PASS することの判定結果。
- C17 (run-ubm-knowledge-sync): 既知の更新済みソースを投入し detect-knowledge-updates.py が検知、knowledge-extractor が6カテゴリへ分類し router.json/registry.json が同期完了することの判定結果。
- C04 (ubm-write-path-guard): `UBM_VAULT_ROOT` 配下の許可外パスへの破壊的書き込みが hook で fail-closed に阻まれることの判定結果。
- C01-C03/C05-C13/C15/C18-C19: 各 component の output_contract が満たされ受入テストが二値で PASS することの判定結果。
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C16: 週報/月報/期報を生成し validate-goal-output.py が PASS すると判定できる。
- [ ] C17: 既知の更新済みソースを投入し detect-knowledge-updates.py が検知、knowledge-extractor が6カテゴリへ分類すると判定できる。
- [ ] C04: 破壊的操作が hook で fail-closed に阻まれると判定できる。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C19 (全 18 component)。
- 後続 P08 (refactoring)。
