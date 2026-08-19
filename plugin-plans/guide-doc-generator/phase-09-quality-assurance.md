---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P09 — quality-assurance (品質)

## 目的

component ごとの品質ゲート (静的検査・build trace・レビュー・評価) を全て通し、qa gate を成立させる。個別テストでは見えない横断的な品質面 (命名規約・依存方向・実行時可搬性) をここで潰す。

## 背景

テストが通ることと、plugin として配布可能な品質にあることは別である。命名規約違反や依存方向の逆流、絶対パス直書きは実行時ではなく静的検査でしか見つからない。

## 前提条件

- P08 まで完了し全テストが green である

## ドメイン知識

- **p0_lint**: component_kind ごとに必須の静的検査集合が決まっている
- **build trace**: 各 component が計画のどの項目から生まれたか追跡可能であること
- **実行時可搬性**: 環境固有の絶対パスを持たず、専用 env / 自己解決 / 相対パスのみで動くこと
- **harness カバレッジ**: 各 component が閾値以上のカバレッジと kind 別の合格条件を満たすこと

## 成果物

- component 別 p0_lint の実行結果
- build trace の記録
- 実行時可搬性の検査結果
- harness カバレッジの計測結果

## スコープ外

- 最終レビュー判定 (P10)
- 証跡の集約 (P11)

## 完了チェックリスト

- [ ] 全 component の p0_lint が合格している
- [ ] 全 component の build trace が取れている
- [ ] 環境固有の絶対パス直書きが 0 件である
- [ ] harness カバレッジが全 component で閾値以上である
- [ ] qa gate が PASS である

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 全 component の p0_lint と build trace が揃い、環境固有の絶対パス直書きが 0 件で、harness カバレッジが全 component で閾値以上になっている。
- 満たさない例: 一部 script のカバレッジ不足を「検証器だから」と免除しており、閾値未達のまま PASS 扱いになっている。

### 事前解決済み判断

- カバレッジ閾値に例外は設けない。検証系 script も同じ閾値で測る。
- 環境固有の絶対パスは直書きせず {{PROJECT_ROOT}} / $CLAUDE_PLUGIN_ROOT / self-relative で表す。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

