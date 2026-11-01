---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P08 — refactoring

## 目的
重複文言と環境固有パスを除去する。

## 背景
素材パスや紙面中央の計算を複製すると別案・別ホストで再発する。同じ事実はschemaとcatalogに集約する。

## 前提条件
P06の試験が通り、P07で未検証範囲が記録されている。

## ドメイン知識
runtimeはinstall先のskill位置からplugin rootを解決し、元のObsidian絶対パスや他pluginのcacheに依存しない。

## 成果物
重複削除の差分、scripts/package.pyの自己完結検査と再試験結果。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] 中央計算とsemantic group対応はproject.cjs/schema、素材履歴はcatalogへ集約し、SKILLには正本参照を置く。
- [ ] python3 scripts/package.py --checkが外部symlink/不整合素材/必要資材欠落を拒否し、変更後のnpm testが通る。
- [ ] 旧専門役3本の観点はdesign-knowledge-index.jsonのlensだけに置き、stage agent・SKILL・promptsの本文へ複製しない。整理で規則を消す/足す時もessence-checkを通し、本質成果IDの無い規則を残さない。

### 受入例
- 満たす例: 別ディレクトリへコピーしたkitが元のrepoを参照せずdoctorと検査を実行する。
- 満たさない例: コピー先でも元の個人絶対パスを読み込み成功する。

### 事前解決済み判断
domain rendererは4skillが使うため共有script C12の背後に置き、入口はflyer.pyの1本に保つ。利用者が1skillに限られるscriptは独立componentに増やさない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
