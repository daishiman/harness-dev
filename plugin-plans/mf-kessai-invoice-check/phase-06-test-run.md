---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
C01 (skill loop)・C05・C06 (script) の harness coverage を ≥80% (kind 別) まで拡充し、テストを実行して緑にする。計画段階では現状カバレッジ数値を焼かず、min=80 の閾値と kind_pass の見方のみを契約する。

## 背景
harness coverage は品質の最低ラインを機械保証する仕組み。C05/C06 は決定論スクリプトゆえ行カバレッジ、C01 は skill loop ゆえ criteria 検証テスト (inner/outer) + content-review verdict の二軸で観点が異なる。計画段階で現状値を焼くと Goodhart 化する (数値合わせが目的化する) ため、min=80 の閾値と kind 別パス観点のみを契約し実測は build 後に行う。

## 前提条件
- P05 で C01/C05/C06 が build_target に実体化されている。
- 各 component が harness_coverage ブロック (min/kind_pass) を携帯している。
- kind 別パス観点 (script→行カバレッジ / skill loop→criteria 検証+content-review) を参照できる。

## ドメイン知識
kind 別カバレッジ観点と Goodhart 回避の不変条件は index `## ドメイン知識` / 環境ポリシー節を参照。本フェーズ固有の差分: C06 (`test_notion_report_sink`) の行カバレッジは upsert 主キー判定・find-or-create・非破壊書込の分岐を含める。

## 成果物
- C01/C05/C06 の harness テスト実行ログ (kind 別 ≥80%)。

## スコープ外
- purpose 受入の判定 (P07・カバレッジ緑≠受入充足)。
- criteria 自体の変更 (P04 へ差し戻し)。
- 閾値の変更 (harness-coverage-spec が正本・plan 側で上書きしない)。

## 完了チェックリスト
- [ ] C05/C06 の `harness_coverage.min>=80` が実測 (行カバレッジ) で満たされている。
- [ ] C01 の `harness_coverage.min>=80` が criteria 検証テスト (inner/outer) + content-review verdict で満たされている。
- [ ] 現状値を計画に焼かず、閾値と観点のみを契約として保持している。

## 参照情報
- harness-coverage-spec (kind 別パス観点)。
- 対象 component C01/C05/C06。後続 P07 (acceptance-criteria)。
