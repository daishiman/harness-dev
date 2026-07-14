---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C24, C25, C26, C27, C28, C29]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
後段L4 buildが全componentのharness coverageを≥80%まで拡充・実測するためのテスト契約を確定する。本L3 planではテスト実走や実測値を完了条件にせず、min=80、kind_pass、必要fixture、evidence pathを宣言する。

## 背景
harness coverage は品質の最低ラインを機械保証する仕組み。計画段階で現状値を焼くと Goodhart 化する (数値合わせが目的化する) ため、min=80 の閾値と kind 別パス観点のみを契約し、実測は build 後に行う。この二層分離が「≥80% を満たす設計」を要件化しつつ数値水増しを防ぐ。

## 前提条件
- P05で全componentのbuild routeとtest responsibilityが確定している。
- 各 component が harness_coverage ブロック (min/kind_pass) を携帯している。
- kind 別パス観点 (script→行カバレッジ / skill loop→criteria 検証+content-review / agent・command・hook→機能テスト+content-review) を参照できる。

## ドメイン知識
- kind 別カバレッジ観点: script=行カバレッジ / skill loop=criteria 検証+content-review / agent・command・hook=機能テスト+content-review (正本は harness-coverage-spec)。
- Goodhart 回避の不変条件: 計画には閾値 (min=80) と観点のみを焼き、現状実測値は焼かない (数値合わせの目的化を防ぐ)。

## 成果物
- 後段buildが生成すべきkind別harness test matrixと実行ログ/evidence契約。

## スコープ外
- purpose 受入の判定 (P07・カバレッジ緑≠受入充足)。
- criteria 自体の変更 (P04 へ差し戻し)。
- 閾値の変更 (harness-coverage-spec が正本・plan 側で上書きしない)。

## 完了チェックリスト
- [ ] 全componentにharness_coverage.min≥80、kind_pass、後段実測方法が契約として焼かれている。
- [ ] 5 artifact混在分類、confidence境界、199/200/201件partition、migration rollbackのfixtureが定義されている。
- [ ] Claude hook event/security/idempotency、GitHub completion state machine、複数worktree lease/branch convergenceのfixtureが定義されている。
- [ ] 現状値を計画に焼かず、閾値と観点のみを契約として保持している。

### 受入例
- 満たす例: C11 (script) の行カバレッジ実測が 80% 以上で `harness_coverage.min: 80` を満たし、`kind_pass: "content-review-verdict+coverage"` の観点も緑になる。
- 満たす例: C03 (skill loop) が criteria 検証 (OUT1-OUT9) + content-review verdict PASS の両方を満たし kind_pass 観点が緑になる。
- 満たさない例: `component-inventory.json` に実測カバレッジ数値 (例: `"actual_coverage": 92`) が焼き込まれている → Goodhart 化の兆候として本フェーズの契約 (閾値+観点のみ保持) に違反する。

### 事前解決済み判断
- カバレッジ観点は kind 別に固定 (script=行カバレッジ / skill loop=criteria検証+content-review / agent・command・hook=機能テスト+content-review) し、本フェーズで新規観点を発明しない。
- 閾値 (min=80) は harness-coverage-spec が正本であり、plan 側は上書きしない。

## 参照情報
- harness-coverage-spec (6 種別 × 二軸・kind 別パス)。
- 対象 component C01-C19・C24-C29 (計25)。
- 後続 P07 (acceptance-criteria)。
