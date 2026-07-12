---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
全11 componentのharness coverageをkind別≥80%まで拡充する。

## 背景
harness coverage は品質の最低ラインを機械保証する仕組み。計画段階で現状値を焼くと Goodhart 化する (数値合わせが目的化する) ため、min=80 の閾値と kind 別パス観点のみを契約し、実測は build 後に行う。この二層分離が「≥80% を満たす設計」を要件化しつつ数値水増しを防ぐ。

## 前提条件
- P05 で全 component が build_target に実体化されている。
- 各 component が harness_coverage ブロック (min/kind_pass) を携帯している。
- kind 別パス観点 (script→行カバレッジ / skill loop→criteria 検証+content-review / agent・command→機能テスト+content-review) を参照できる。

## ドメイン知識
- kind 別カバレッジ観点: script=行カバレッジ / skill loop=criteria 検証+content-review / agent・command=機能テスト+content-review (正本は harness-coverage-spec)。
- Goodhart 回避の不変条件: 計画には閾値 (min=80) と観点のみを焼き、現状実測値は焼かない (数値合わせの目的化を防ぐ)。

## 成果物
- 全11 componentのharnessテスト実行ログ。

## スコープ外
- purpose 受入の判定 (P07・カバレッジ緑≠受入充足)。
- criteria 自体の変更 (P04 へ差し戻し)。
- 閾値の変更 (harness-coverage-spec が正本・plan 側で上書きしない)。

## 完了チェックリスト
- [ ] 全 component の harness_coverage.min≥80 が実測で満たされ、kind_pass の観点が緑になる。
- [ ] 現状値を計画に焼かず、閾値と観点のみを契約として保持している。

### 受入例
11 componentすべてでkind別min 80と各acceptance fixtureが緑になる。

### 事前解決済み判断
現状実測値はplanへ焼かず、閾値と観点だけを契約する。

## 参照情報
- harness-coverage-spec (6 種別 × 二軸・kind 別パス)。
- 対象 component C01-C11。
- 後続 P07 (acceptance-criteria)。
