# リソースマップ（共有 reference 層）

**責務**: plugin-root `references/` の共有デザイン知識を progressive disclosure で読むための案内。component 数、agent 一覧、script 一覧、workflow 依存はここに再掲しない。

## 正本の分担

| 対象 | 正本 |
|---|---|
| plugin surface / component 一覧 | `plugin-composition.yaml` と `.claude-plugin/plugin.json` |
| skill 実行 phase / resources | `skills/<skill>/workflow-manifest.json` |
| agent の詳細 7 層 prompt | `skills/<owner-skill>/prompts/R*.md` |
| agent の Task adapter | `agents/*.md` |
| skill-local 手続き知識 | `skills/<skill>/references/resource-map.yaml` |
| runtime schema | `schemas/*.schema.json` |
| vendor byte parity | `vendor/vendor-digest-manifest.json` + `scripts/lint-vendor-parity.py` |
| package contract | `references/package-contract.json` |

このファイルは上記の inventory を複製しない。重複を避けるため、共有 reference の読込条件だけを保持する。

## 共有 Reference 読込条件

| グループ | 対象ファイル | 読むタイミング |
|---|---|---|
| 仕様レジストリ | `spec-registry.md`, `bp-classification.md`, `v8-spec-fields.md` | SR-ID / V-ID / v8 フィールドの根拠が必要なとき |
| 構成設計 | `structure.md`, `strategy.md`, `slide-type-decision-tree.md`, `slide-types-overview.md`, `slide-types-basic.md`, `slide-types-extended.md` | slide 構成、slideType 選択、構成粒度を決めるとき |
| report 設計 | `report-types.md`, `report-writing-rules.md`, `report-visual-strategy.md`, `mermaid-integration.md` | `output_mode=report` の骨格、文体、visual 三択、Mermaid を扱うとき |
| 図解・チャート | `diagram-chart.md`, `diagram-cycle-flow.md`, `diagram-comparison.md`, `diagram-business.md`, `diagram-fabe.md`, `diagram-visual.md`, `chart-types.md`, `d3-integration.md`, `svg-diagram-primitives.md`, `svg-design-spec.md` | 図解・グラフ・D3・SVG2 の方式選定と実装時 |
| 意匠・レイアウト | `theme-style.md`, `design-quality-guide.md`, `visual-hierarchy-principles.md`, `composition-patterns.md`, `color-strategy.md`, `slide-design-patterns.md`, `layout-visual.md`, `unit-system.md` | 配色、視覚階層、構図、単位、レイアウト調整時 |
| 画像生成 | `ai-image-diagram-workflow.md`, `full-image-deck-method.md`, `style-genome-packaging.md`, `image-format-guide.md` | ユーザーが画像生成・全面画像化・画像差し替えを明示したとき |
| 出力・運用 | `print-layout.md`, `post-generation-evaluation.md`, `llm-script-separation.md`, `agenda-navigation.md`, `icons.md`, `writing-rules.md`, `slide-components.md`, `slide-interactions.md`, `slide-text-guidelines.md` | 印刷、生成後評価、責務分離、ナビ、アイコン、文面、相互作用を確認するとき |
| パッケージ契約 | `package-contract.json` | PKG-001〜017 の package mode / check status を確認するとき |
| 履歴・フィードバック | `changelog.md`, `feedback/*.md` | 既知の失敗・変更履歴・フィードバック反映を確認するとき |

## 検証

- `python3 plugins/slide-report-generator/scripts/validate-plugin-completeness.py`
- `python3 plugins/slide-report-generator/scripts/lint-reference-attribution.py plugins/slide-report-generator`
- `python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py --plugin-dir plugins/slide-report-generator`

上記で agent prompt の配置、skill-local reference の帰属、同一 schema ID の重複を検出する。
