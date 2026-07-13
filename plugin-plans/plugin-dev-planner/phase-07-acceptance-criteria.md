---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
purpose 由来の受入観点 (task-graph が既存 2 軸を置換せず第 3 の射影として機能すること・discovered-task が構造変更級で二段受理を経ること・task-graph が canonical であること) を二値の受入基準として index.md の「受入確認」章へ列挙する。

## 背景
C1-C19 の各 checklist は build 後の見方を持つ必要があり、本 phase はその確認方法を確定する。

## 前提条件
- P06 の harness_coverage 設計が確定している。

## ドメイン知識
- 受入観点は index.md の「受入確認」章で C1-C19 ごとに確認方法とcriteria idを対にする。

## 成果物
- 受入観点の一覧設計 (index.md 「受入確認」章の元データ)。

## スコープ外
- index.md の実ファイル記述 (P12 相当、本 plan では index.md 生成時に反映)。

## 完了チェックリスト
- [ ] C1-C19 全てに build 時の確認方法が存在する。

### 受入例
（本 phase は縮小要件対象 (REDUCED_REQUIREMENT_PHASES) のため、見出し直下の本文は簡略形で足りる。）

### 事前解決済み判断
（本 phase は縮小要件対象のため、見出し直下の本文は簡略形で足りる。）

## 参照情報
- P06 (test-run)。
- 後続 P08 (refactoring)。
