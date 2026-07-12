# schemas/ — 決定論的入力契約

`presentation-slide-generator` スキルにおける構成入力の **JSON Schema 正本**。
`structure.md` の自然言語記述を補完／置換し、LLM 解釈ブレを排除する。

## ファイル

| ファイル | 役割 |
|---------|-----|
| `structure.schema.json` | JSON Schema Draft 2020-12 本体。ルート3要素（meta/theme/slides）＋ slide 配列、`oneOf` で slideType ごとの content を厳密分岐 |
| `example.structure.json` | 5スライドの有効サンプル（hero/message/list/diagram-prep/highlight） |
| `README.md` | 本ファイル。スキーマの読み方・SR-ID参照表・structure.md との関係 |

## structure.md との関係

| 項目 | structure.md（既存） | structure.schema.json（本契約） |
|------|---------------------|-------------------------------|
| 形式 | Markdown + 表 + 自然言語 | JSON Schema |
| 解釈余地 | LLM 依存 | 機械検証 |
| 用途 | 人間レビュー・設計議論 | パイプライン入力・自動生成・CI検証 |
| 関係 | 「何を伝えるか」の説明文書 | 「どう与えるか」の契約 |
| 移行 | 並存。新規生成は schema を一次入力とし、structure.md は説明書きとして併走 | — |

## ルート構造

```
{
  meta:        { title, audience, durationMinutes, keyMessage, ... }
  theme:       { name: "kanagawa-lotus", accentColors[1-2], fontScale }
  globalSpec:  { minSvgFontSize, minGsapScale, maxBulletsPerSlide, ... }  // 通常は空 {}
  sections:    [{ id, title, color, slides:[int] }]
  slides:      [{ id, slideType, purpose, structure, content, layout?, animations?, constraints? }]
}
```

## slide オブジェクト構造

| キー | 説明 |
|-----|-----|
| `id` | `slide-001` 形式（`^slide-[0-9]{3,4}$`） |
| `slideType` | DT-ID に対応する 79+α タイプの enum |
| `purpose` | `P-EMO / P-CON / P-CMP / P-STG / P-WHL / P-NUM / P-CIT` |
| `structure` | `S-SGL / S-DUO / S-LST / S-FLW / S-SYS / S-VIZ / S-COD` |
| `content` | `slideType` ごとに `oneOf` で形が分岐（厳密定義） |
| `layout` | viewBox / vw単位の余白・gap・positions |
| `animations` | GSAP enter/leave、stagger、ease（scale 最小 0.8） |
| `constraints` | このスライド固有の制約上書き（globalSpec と同形） |

## slideType の oneOf 分岐

`$defs/contentDispatch` にて以下のグループで分岐:

### 厳密定義（個別スキーマあり）
- 基本: `slide-hero`, `slide-quote`, `slide-message`, `slide-title`, `slide-list`, `slide-icon-grid`, `slide-grid`, `slide-pyramid`, `slide-circle`, `slide-compare`, `slide-code-compare`, `slide-flow`, `slide-process`, `slide-timeline`, `slide-table`, `slide-code`, `slide-highlight`
- 図解代表: `diagram-cycle / pdca / triangle-cycle`、`diagram-vs / butterfly / slope`、`diagram-prep`、`diagram-fabe-*` 5バリ、`diagram-mindmap / concentric / value-stack / venn-2 / venn-3`
- グラフ: `chart-bar-* / line / pie / clock-pie / radar`
- D3: `d3-cycle / pdca / triangle-cycle / rotating-flow`、`d3-tree / org-chart / sunburst / treemap / packed / dendrogram`、`d3-sankey / force / chord / arc`、`d3-bar / line / pie / donut / radar / gauge / bubble / heatmap / radial-bar / bullet / lollipop / calendar / isotype / wordcloud / pyramid / funnel / waterfall / roadmap / vertical-timeline`

### フォールバック (`content_generic`)
残りの diagram-* および `chart-scatter / chart-gauge` は `content.title` のみ必須とし、追加プロパティ自由（後続段階で個別スキーマ化予定）。

## SR-ID 参照表（主要）

| 制約 | スキーマ表現 | 根拠 SR-ID |
|------|-------------|-----------|
| 16:9 厳守 | `globalSpec.viewBoxDefault` のパターン | SR-1-01, SR-1-02 |
| 単位は vw 系 | `$defs/vwValue`, `$defs/remValue` | SR-1-04 |
| 1スライドのアクセント色は1〜2色 | `theme.accentColors` `minItems:1, maxItems:2` | SR-2-05, SR-2-06 |
| アクセント色は CSS 変数 enum | `$defs/accentColorEnum`, `$defs/colorVar` | SR-2-02, SR-2-08 |
| SVG 最小フォントサイズ 13px | `globalSpec.minSvgFontSize` `minimum:13` | SR-3-05 |
| SVG `<text>` 内 FA unicode 禁止 | `$defs/fontAwesomeIcon` パターン（クラス表記強制） | SR-3-06 |
| 比較は 48-4-48 | `globalSpec.compareRatio` enum 固定 | SR-4-03 |
| GSAP scale 最小 0.8 | `$defs/gsapTween.scale` `minimum:0.8`、`globalSpec.minGsapScale` | SR-6-01 |
| ease は許容セットのみ | `animations.ease` enum | SR-6-05 |
| コード言語は限定 enum | `$defs/langEnum` | SR-10-* |
| 1スライド5-7チャンク | `globalSpec.maxBulletsPerSlide` `maximum:9`、各 list の `maxItems` | SR-3-* / 6.2 |

## V-ID 機械検証（bp-classification.md）との連携

スキーマで強制できないルール（V-* 検証ID）は `scripts/validate-structure.js` で別途検証する想定。本スキーマは静的構造の正しさのみを担保する。

## DT-ID 対応表

`slideType` enum と DT-ID の対応は `references/slide-type-decision-tree.md §2` および `§4` を参照。
DT-001 〜 DT-098 のうち、本スキーマで `slideType` enum に含まれるものは 79 種（FABE 5バリ展開込み 83 ID 中、エイリアス DT-097/DT-098 を除く実体）。

## 使い方

### LLM／生成パイプライン
1. `structure.md`（説明文書）と本スキーマを並行して読む
2. 各 slide を `slide-type-decision-tree.md` に従い `slideType` 確定
3. `oneOf` 分岐に従い `content` を埋める
4. 出力 JSON を AJV 等で `structure.schema.json` 検証

### 検証コマンド例
```bash
npx ajv validate -s schemas/structure.schema.json -d schemas/example.structure.json --spec=draft2020 --strict=false
```

## 改訂履歴

| Version | Date       | 変更 |
|---------|-----------|------|
| 1.0.0   | 2026-05-03 | 初版。slideType 79+α、$defs 35個、example 5スライド |
