# Phase 08 — リファクタリング

> 実装後、DRY/単一責務/非破壊の観点で構造を整える。実コードへ適用した変更を記録する。

## 適用したリファクタリング
1. **意匠 SSOT の単一化 (DRY)**: render-report.js は独自に配色/フォントを再定義せず、vendored `style-builder.cjs` の SPEC を唯一のソースとして `:root` を再構築。slide/report で意匠トークンを重複させない (契約 §D/§I)。
2. **agent frontmatter の統一 (一貫性)**: 13 移植 agent の frontmatter を決定論スクリプトで同一テンプレート化 (name/description/kind/tools/owner_skill/prompt_layer/since)。手作業のばらつきを排除。
3. **パス参照の $CLAUDE_PLUGIN_ROOT 集約 (portability)**: `node scripts/…` → `node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/…"` を機械書換で統一。install 先非依存。
4. **規約セクションの冪等付与**: `## Prompt Templates`/`## Self-Evaluation` を既存本文末尾へ冪等 append (既存があれば skip)。二重化を防止。
5. **vendor manifest の plugin 内携行 (自己完結)**: parity 比較基準 `vendor-digest-manifest.json` を plugin vendor/ 内へ携行し、`verify-vendor-parity.py` が移植元 live tree 非依存で照合できるようにした。
6. **cross-agent 契約の schema 正本化**: visual.spec 語彙のドリフトを、良設計側 (schema: common core 共有・aiVisualSpec は validate-ai-image-assets.js と同期) を正本に統一し、consumer(render-report.js) を conform (平均回帰でなく上方整合)。

## 非破壊の検証
- vendor 195 files: リファクタ後も byte-parity PASS (書換は additive のみ)。
- 移植 agent 7層本文: パス/mode 追記以外は upstream 相当を維持 (行数保存: 例 slide-renderer 339 body lines)。
