# リソースマップ（共有 reference 層）

**責務**: plugin-root `references/` の共有デザイン知識を progressive disclosure で読むための案内。component 数、agent 一覧、script 一覧、workflow 依存はここに再掲しない。

## 正本の分担

| 対象 | 正本 |
|---|---|
| plugin capability 構成 | `plugin-composition.yaml` |
| 配布 entry point / 依存 / 配布先 | `references/package-contract.json` |
| native plugin メタ情報 / hook 参照 | `.claude-plugin/plugin.json` |
| skill 実行 phase / resources | `skills/<skill>/workflow-manifest.json` |
| agent の詳細 7 層 prompt | `skills/<owner-skill>/prompts/R*.md` |
| agent の Task adapter | `agents/*.md` |
| skill-local 手続き知識 | `skills/<skill>/references/resource-map.yaml` |
| runtime schema | `schemas/*.schema.json` |
| vendor integrity（upstream byte-pin + managed overlay） | `vendor/vendor-digest-manifest.json` + `scripts/lint-vendor-parity.py` |
| 資料作成の大原則（考え方層）の本文・閾値 | `references/deck-principles/principles.json` |
| 原則 → agent / 検査器 / 既存 reference の写像 | `references/deck-principles/binding.json` |
| consumer 宣言・取得・受渡しの共通契約 | `references/deck-principles/consumer-bootstrap.md` |
| tool-neutral rule → 製品固有操作の adapter | `references/deck-principles/tool-adapters.json` |
| consumer binding の構造契約 | `schemas/deck-principles-binding.schema.json` |
| standalone plugin へ複製するartifact set | `references/deck-principles/vendor-manifest.json` |

このファイルは上記の inventory を複製しない。重複を避けるため、共有 reference の読込条件だけを保持する。

図解 1 枚を描く手続き（どの順に何を決めるか）の索引は参照専用 skill `skills/ref-diagram-system/SKILL.md` にあり、その skill-local 正本は上表のとおり skill 自身の `references/` 配下に置かれる。ここでは内容を複製せずポインタだけ持つ（値・閾値・列挙の正本は依然として `spec-registry.md` / `diagram-layout-contract.md` / `schemas/` 側にある）。

## 共有 Reference 読込条件

| グループ | 対象ファイル | 読むタイミング |
|---|---|---|
| 資料作成の大原則（全モード共通） | `deck-principles/consumer-bootstrap.md`, `deck-principles/binding.json`, `deck-principles/principles.json` | 資料作成の判断前。prompt の marker に従い `scripts/extract-deck-principles.py --consumer <id> --format json` を実行または brief で受領する。件数・selected/xref内訳は実出力から導出し、checklistは別返却型として扱う。JSON正本を直接読まず、既存referenceとの優先関係・単位規則はbootstrapへ一本化する |
| PowerPoint / Google Slides / HTML のtool adapter | `deck-principles/tool-adapters.json` | selectorが返すtool-neutralな `rule` / `tool_intent` を製品固有操作へ変換するときだけ読む。共通selection envelopeへ製品名や操作手順を焼き付けない |
| binding schema / vendor artifact set | `../schemas/deck-principles-binding.schema.json`, `deck-principles/vendor-manifest.json` | consumer追加・run_by変更・vendoring更新時。bindingの構造と配布artifact集合を検査器へ委ね、promptや更新手順へ一覧を複製しない |
| 仕様レジストリ | `spec-registry.md`, `bp-classification.md`, `v8-spec-fields.md` | SR-ID / V-ID / v8 フィールドの根拠が必要なとき |
| 構成設計 | `structure.md`, `strategy.md`, `slide-type-decision-tree.md`, `slide-types-basic.md`, `slide-types-extended.md` | slide 構成、slideType 選択、構成粒度を決めるとき |
| report 設計 | `report-types.md`, `report-writing-rules.md`, `report-visual-strategy.md`, `mermaid-integration.md` | `output_mode=report` の骨格、文体、visual 三択、Mermaid を扱うとき |
| 図解・チャート | `diagram-layout-contract.md`, `diagram-*.md`（型カタログ）, `chart-types.md`, `d3-integration.md`, `svg-diagram-primitives.md` | 図解・グラフ・D3・SVG2 の方式選定と実装時。**どの節番号がどの `diagram-*.md` に載るかは `diagram-type-crosswalk.md` §0 の対応表が正本**で、ここにファイル名を列挙しない（列挙すると型カタログを 1 本増やすたびに 2 箇所を直す必要が生まれ、片方が必ず腐る）。合否の契約と D 系検査の説明は `diagram-layout-contract.md`（範囲はここに書かない。検査器が増えるたびに腐る） |
| 作図文法の数値契約（第 4 次 update） | `diagram-layout-contract.md` §D-1〜§D-6 | 図解を描くとき・検証するときに読む。§D-1 4px グリッド（座標・寸法・間隔の許可値）、§D-2 複雑度予算、§D-3 コネクタ 5 原則、§D-4 R9 溶け込み契約（§D-4-1 占有率 / §D-4-2 重複禁止 / §D-4-3 文脈適合 / §D-4-4 配置と型の接続）、§D-5 annotation の文法、§D-6 検査 owner 一覧。数値の正本は本ファイルで、prompt 側へ写さない。読み手は `html-generator` / `report-composer`（作図時）、`visual-strategist`（§D-4-4 の配置）、`ui-quality-reviewer` / `report-quality-reviewer`（§D-4 の検証観点）、`report-structure-designer`（§D-4-2 を満たす narrative 設計） |
| 図解の情報下限契約 | `diagram-information-contract.md` | 図解を描く前と検証時に読む。出所・時点、caption と図の一致、凡例、軸、完了条件など「正しく配置されていても情報が足りない図」を防ぐ意味契約。作成者は事前に読み、`validate-diagram-information.py` は生成後にその機械判定可能部分を検査する |
| 図解型の選定（両モード・図解を描くとき最初に読む） | `diagram-type-crosswalk.md` | 図解を 1 枚でも描く前に**必ず**読む。「何を見せたいか」から決定論ビルダー / CSS 型（`diagram-*.md` の節番号）/ slide tpl / 推奨経路 / 推奨配置を引く索引。読む順は §0（表の読み方と CSS 型節番号→ファイル）→ 該当の §1-§9 → §10（決定論 or tpl or 手書きの判断順序）。読み手は `visual-strategist`（型選定）、`html-generator` / `report-composer`（描画前）、`d3-diagram-designer`（D3 の代替型検討時）、`ui-quality-reviewer` / `report-quality-reviewer`（型と配置の整合検証時） |
| 図解の色ロール（両モード・SVG/CSS に色を書く直前） | `diagram-style-tokens.md` | 図解へ色・線幅・書体を与えるときに読む。hex 直書きの代わりに引くセマンティックロール名の索引で、値の正本は `vendor/scripts/svg-kit.cjs`（`TOKENS` / `STROKE`）と `vendor/scripts/style-builder.cjs`（`SPEC.colors`）。読む順は §1（ロール表）→ §2（系列色と使用制限）→ §3（focal rule）→ §4（ノード種別）→ §5（線幅・角丸・影の禁止事項）→ §6（書体）。読み手は `html-generator` / `report-composer`（手書き経路）、`visual-strategist`（色数の見積り）、両 quality-reviewer（色数と焦点の検証） |
| 図解の骨格テンプレート（手書き経路の白紙をなくす） | `../assets/diagram-templates/README.md`, `../assets/diagram-templates/diagram-skeleton-slide.html`, `../assets/diagram-templates/diagram-skeleton-report.html` | `diagram-type-crosswalk.md` §10 の判断で**手書き経路**に落ちたときだけ読む（決定論ビルダー / slide tpl があるならそちらが優先）。成果物へ埋め込む HTML 断片で、単体ページ用ではない。slide 面内は `diagram-skeleton-slide.html`、report 本文中は `diagram-skeleton-report.html` をコピーし、編集マーカーで囲われた図解本体だけを書く。読み手は `html-generator`（slide）と `report-composer`（report）、および両 quality-reviewer（骨格が埋め込み用かの検証） |
| スライド面のページひな形（slide の面を組む直前に**必ず**読む） | `../assets/slide-templates/README.md`, `../assets/slide-templates/registry.json`, `../assets/slide-templates/frame-contract.json` | slide の面を 1 枚でも書く前に読む。面の配置は <!-- count: slideSkeleton -->22 種のひな形（id は `layout-<役割>`。通し番号ではないので deck のページ数とは無関係）へ固定され、107 種の slideType は `registry.json` の `map` からひな形と media 種別を引く（推測でひな形を選ばない）。slideType を持たない面のうち、表紙・目次・章扉・締めは `structural_pages`、自己紹介・登壇者一覧・KPI・想定質問・連絡先は `role_pages` から役割名で引く。visual-strategist が差し込み物を codex-image に決めた面だけ `media_override` に従い `layout-image-full`/`layout-image-side`/`layout-image-grid` へ載せ替える。寸法の正本は `frame-contract.json` 1 つで、面ごとに座標を直書きしない。ひな形 HTML と `slide-skeleton.css` / `slide-skeleton.js` は生成物なので手で編集しない（`scripts/validate-slide-skeleton.py` の S4 が落とす）。色は `vendor/scripts/style-builder.cjs` の `SPEC.colors` が正本で、面や CSS 使用箇所への 16 進直書きは S11 が落とす。決定論経路の `render-slide.cjs` はこの契約を読まないので、ひな形が効くのは手書き経路の面だけ。読み手は `html-generator`（面の組立て）、`slide-renderer`（純手書きdeckでのみsrgひな形を使い、engine deckには混ぜない。成果物排他検査は `validate-slide-layout.js <index.html> --strict`）、`structure-designer`（slideType 選定時の受け皿確認）、`layout-optimizer` / `ui-quality-reviewer`（空白・chrome 位置・印刷ズレの検証） |
| 図種導出（report） | `../schemas/visual-derivation-table.json` | report の section から svg 図種（variant）を決めるときに**必ず**読む。図種選定の正本はこの決定表 1 つで、`rows[]` を `order` 昇順に first-match-wins で引く。agent プロンプト側に写像表を置かない（正本が 2 箇所あると同じ節でも図種が揺れるため） |
| 意匠・レイアウト | `theme-style.md`, `design-quality-guide.md`, `visual-hierarchy-principles.md`, `composition-patterns.md`, `color-strategy.md`, `slide-design-patterns.md`, `layout-visual.md`, `unit-system.md` | 配色、視覚階層、構図、単位、レイアウト調整時 |
| 画像生成 | `ai-image-diagram-workflow.md`, `full-image-deck-method.md`, `style-genome-packaging.md`, `image-format-guide.md` | ユーザーが画像生成・全面画像化・画像差し替えを明示したとき |
| 出力・運用 | `print-layout.md`, `post-generation-evaluation.md`, `agenda-navigation.md`, `icons.md`, `writing-rules.md`, `slide-components.md`, `slide-interactions.md`, `slide-text-guidelines.md` | 印刷、生成後評価、責務分離、ナビ、アイコン、文面、相互作用を確認するとき |
| パッケージ契約 | `package-contract.json` | PKG-001〜017 の package mode / check status を確認するとき |
| 履歴・フィードバック | `feedback/*.md` | 既知の失敗・フィードバック反映を確認するとき（変更履歴の正本は git） |

## 検証

- `python3 plugins/slide-report-generator/scripts/validate-plugin-completeness.py`
- `python3 plugins/slide-report-generator/scripts/lint-reference-attribution.py plugins/slide-report-generator`
- `python3 plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py --plugin-dir plugins/slide-report-generator`
- `python3 plugins/slide-report-generator/scripts/validate-deck-principles.py --vendor-target ../guide-doc-generator/assets/deck-principles/principles.json`

上記で agent prompt の配置、skill-local reference の帰属、同一 schema ID の重複を検出する。
