---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
全 7 component の harness coverage を ≥80%(kind 別)まで拡充し、症状①〜⑦を各1件以上再現する MF実績ゴールデン fixture 回帰を含めてテストを実行し緑にする。計画段階では現状カバレッジ数値を焼かず、min=80 の閾値と kind_pass の見方のみを契約する。

## 背景
harness coverage は品質の最低ラインを機械保証する仕組み。本改善はユーザーが「再現性・精度・品質」を最重要要件として明示しているため、ゴールデン fixture 回帰(C1-C7 相当の症状再現)と fetch fidelity gate(C2)の両方が緑であることを確認する。計画段階で現状値を焼くと Goodhart 化するため、閾値と観点のみを契約する。

## 前提条件
- P05 で全 component が build_target に実体化されている。
- 各 component が harness_coverage ブロック(min/kind_pass)を携帯している。
- 症状①〜⑦の MF実績ゴールデン fixture + 期待レポート行が `tests/` に凍結可能な状態。

## ドメイン知識
- kind 別カバレッジ観点: script(C03-C06)=行カバレッジ / skill loop(C01)=criteria 検証+content-review / sub-agent(C02)・slash-command(C07)=機能テスト+content-review。
- Goodhart 回避の不変条件: 計画には閾値(min=80)と観点のみを焼き、現状実測値は焼かない。
- ゴールデン fixture 回帰は C7(症状①〜⑦の凍結)・fetch fidelity gate は C2 の機械検証に対応する。

## 成果物
- 全 component の harness テスト実行ログ(kind 別 ≥80%)。
- 症状①〜⑦ゴールデン fixture 回帰テストの実行結果。

## スコープ外
- purpose 受入の判定(P07・カバレッジ緑≠受入充足)。
- criteria 自体の変更(P04 へ差し戻し)。
- 閾値の変更(harness-coverage-spec が正本・plan 側で上書きしない)。

## 完了チェックリスト
- [ ] 全 component の harness_coverage.min≥80 が実測で満たされ、kind_pass の観点が緑になる。
- [ ] 症状①〜⑦を各1件以上再現するゴールデン fixture 回帰(C7)が pytest で緑になる。
- [ ] fetch fidelity gate(C2)が NG 時に fail-closed で漏れ確認処理を停止する挙動がテストで確認できる。

## 参照情報
- harness-coverage-spec(kind 別パス)。
- 対象 component C01-C07。
- 後続 P07(acceptance-criteria)。
