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
