# Phase 09 — 品質保証

## 機械品質 (全緑・P06 参照)
決定論ゲート10本 PASS=10/FAIL=0。vendor parity 195/195・pytest 25・node renderer tests・schema valid・agent/skill lint。

## 非破壊/再現性
- vendor 195 byte 固定(書換禁止)を parity で保証。追加は render-report.js/mermaid-render.js/tests の additive のみ。
- 移植 agent の 7層本文はパス/mode 追記以外 upstream 相当を維持(平均回帰なし)。
- 全実行パス $CLAUDE_PLUGIN_ROOT 起点(portability)。

## cross-agent 契約整合 (並列buildの接合検証)
- schema↔renderer↔sample の3点整合を G3/G7/G8 で三重に閉じた。散文契約(§E)由来のドリフトを schema 正本化で解消。
- 同一ファイル並行書込(私↔mode-edits の C04/C13、私↔renderers の render-report/sample)は last-writer-wins で最終状態を検証し破損なしを確認。

## 視覚品質 (P11)
slide(16:9・Kanagawa・1メッセージ)/report(読み物・4骨格・Mermaid実描画・1項目1ビジュアル)を実HTML+スクショで目視 PASS。

## 現ビルド追随検証 (2026-07-11 update)

> 上記 v1 の「vendor parity 195/195・pytest 25」は現ビルドと不一致。以下は本セッションで実測した機械ゲート数値のみを追記する (数値の発明なし)。

- **vendor byte-parity 191/191 PASS**: schemas subtree の真 schema 4本を plugin-root live へ移し、vendor 側を fixture3 + README = 4 file 化した結果、従来 195 → 191 に変化。
- **pytest 125 passed** (旧 25 から増加)。
- **lint 系全緑**: lint-contract-drift findings=0、lint-reference-attribution ok、validate-plugin-completeness PASS。
- **vendor JS test 全 PASS**: test-render-report / test-mermaid-render / test-cross-deck-consistency。
- **C23 validate-output-mode.py coverage 92%** (旧 63% から in-process test 追加で改善)。
- **C25 validate-report-visual.py (本セッション強化)**: `_check_uiux_shape` (screen 接合トークン・sticky TOC・aria-current・before/afterprint・@media print .report 幅・狭画面 @media・grid minmax card・タイポ --fs-body 16-18px/title比≤2.2 の存在検査) と `--require-structure` (report gate の fail-open 封鎖=structure 欠落で exit2) を追加。現行 report で C25 実行=uiux-shape warn 0・exit0 (実装トークン健在を実証)。
