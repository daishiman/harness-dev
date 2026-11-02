---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P06 — test-run

## 目的
正例と異常系の試験を実行する。

## 背景
入力検証だけではPDF化時のSVGロゴ崩れ・日本語文字欠け・QR読取を検出できない。実レンダリングを含む試験を分ける。

## 前提条件
npm ci --ignore-scripts後、python3 scripts/flyer.py doctorがブラウザとPDFツールの利用可否を返す。

## ドメイン知識
browser screenshotはPDF由来PNGの代わりにならない。SVGロゴはraster記録も確認する。再利用背景の試験は新生成の証拠にはならない。

## 成果物
verification/test-results.txt・render-checks.json・svg-logo.json。生成済みprojectの絶対場所はresults.jsonの証拠参照に記録する。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] npm testの実行結果を保存し、skipがある場合は対象を未実施と明示する。
- [ ] node tests/render-acceptance.cjs <新規証拠dir>で黒/白2案を描画し、実見後FLYER_ACCEPTANCE_PROJECT=<証拠dir> npm testが失敗0となる。
- [ ] verifyが両案のQR/白外縁/紙面中心/安全域/埋込font/鮮度を検査し、各異常系の拒否理由が試験結果に残る。
- [ ] python3 -m unittest tests/test_essence_check.pyの結果をverification/test-results.txtへ保存し、python3 scripts/flyer.py essence-checkと、描画した証拠projectへの--project指定がともにexit 0である(C15-C17)。

### 受入例
- 満たす例: PNGロゴとSVGロゴを各1案で描画し、PDF由来PNGも確認する。
- 満たさない例: 統合試験skipを含む結果を「全経路実行」とする。

### 事前解決済み判断
失敗は原因修正後に関連範囲を再実行。render実装変更は全対象を再描画してreview SHAも更新する。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
