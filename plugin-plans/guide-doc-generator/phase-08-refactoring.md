---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: [C11, C14, C16, C17, C18, C20, C22]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P08 — refactoring (改善)

## 目的

受入を満たしたうえで、規模が大きくなりやすい決定論 script の内部構造を整理する。振る舞いを変えずに、レンダラと逆抽出器で重複しがちな部品知識、検証器 3 本で重複しがちな HTML 走査処理を共通化の判断にかける。

## 背景

レンダラは部品カタログ全点を扱うため肥大しやすく、逆抽出器はその逆写像として同じ部品知識を持つ。検証器も同じ HTML を別観点で走査する。放置すると部品を 1 つ足すたびに複数箇所を直す構造になる。

## 前提条件

- P07 の受入判定が合格している
- 振る舞いを固定するテストが揃っている

## ドメイン知識

- **tdd-refactor**: テスト green を維持したまま内部構造のみ変更する。振る舞いが変わったらそれは refactoring ではない
- **共通化の判断基準**: 重複が 2 箇所なら様子見、3 箇所以上または部品追加のたびに同期が要るなら共通化する
- **分割の閾値**: 単一ファイルが大きくなりすぎ、責務が読み取れなくなった時点で分割を検討する (行数そのものを目標化しない)

## 成果物

- 部品知識の共通化判断と適用結果
- HTML 走査処理の整理
- refactoring 前後でテストが green のままであることの記録

## スコープ外

- 新機能の追加 (振る舞い変更は refactoring ではない)
- 品質保証の実施 (P09)

## 完了チェックリスト

- [ ] refactoring 前後で全テストが green のままである
- [ ] 生成 HTML がバイト一致で不変である
- [ ] 部品追加時の同期箇所が減っている
- [ ] 公開インターフェイス (argv と exit code) が変わっていない

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 重複していた部品定義が 1 箇所へ寄り、公開インターフェイス (argv と exit code) は不変で、生成 HTML がバイト一致のまま保たれている。
- 満たさない例: 整理の過程で argv の名前が変わり、slash-command 側の呼び出しが黙って壊れている。

### 事前解決済み判断

- 公開インターフェイス (argv と exit code) は refactoring の対象外とする。整理は内部構造に限り、生成 HTML のバイト一致で不変性を確認する。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

